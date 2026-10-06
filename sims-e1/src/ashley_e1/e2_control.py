"""E2 session control: commands, lineage, experiments, pause (plan E2 §6–§8).

Game thread only. All world actions go through e2_actuator; all reads through
observers/e2_actuator read helpers; all file I/O through the writer queue.
The host supplies emit/state callables so this module never imports probe.
"""

import time

from . import e2_admission
from . import e2_cards
from . import e2_lineage
from . import e2_registry
from . import e2_trial
from . import schema
from . import snapshot

try:
    from . import e2_actuator  # TARGET_BYTECODE 1.128 bindings; RUNTIME first-load gate.
except ImportError:
    e2_actuator = None
try:
    from . import observers
except ImportError:
    observers = None
try:
    import services  # PRIOR_ART|TARGET_BYTECODE: sim_info_manager read surface.
except ImportError:
    services = None
try:
    # TARGET_BYTECODE: Distributor.add_event(immediate=True) is append + process_events().
    from distributor.system import Distributor
except ImportError:
    Distributor = None
try:
    # TARGET_BYTECODE: camera.focus_on_sim(sim, follow, client) / focus_on_object(object, follow)
    # send FocusCamera(id, follow_mode) to the client; they move only the view.
    from camera import focus_on_sim, focus_on_object
except ImportError:
    focus_on_sim = focus_on_object = None
CAMERA_MIN_GAP_S = 1.5

def _send_queued_events():
    """2.20.1 (live 2026-10-06: after her answer the recipe picker stayed on screen and the game
    stayed paused): dialog_respond queues the client's close (MSG_UI_DIALOG_CLOSE) for the next
    distributor pass; send it now, as the game's own add_event(immediate=True) does. Never
    changes the answer's outcome."""
    if Distributor is None:
        return False
    try:
        Distributor.instance().process_events()
        return True
    except Exception:
        return False


# E1 LAB sofa (target of the E1 Owner-sit witness): never an E2 experiment target.
EXCLUDED_OBJECT_IDS = frozenset(("118245043789434044",))
# 2.19.1: samples (about one a second) a pushed act may be missing from her queue before it
# is recorded as gone (UNKNOWN, LEFT_QUEUE).
LEFT_QUEUE_SAMPLES = 5


def _now():
    return time.perf_counter()


def _hunger_span(experiment):
    return _motive_span(experiment, "hunger")


def _motive_span(experiment, motive_id):
    """D7: start, peak and end. The end of a long window hides a meal (31->80->40)."""
    before = None
    after = None
    peak = None
    for row in experiment._rows_since:
        item = None
        for motive in row.get("motives") or []:
            if isinstance(motive, dict) and motive.get("id") == motive_id:
                item = motive
                break
        if item is None:
            continue
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if before is None:
            before = value
        after = value
        if peak is None or value > peak:
            peak = value
    return _num(before), _num(peak), _num(after)


RISE_AT = 5


def _risen(experiment, skip):
    """D28 (live shower_TakeShower PASS, hygiene 82->100, detail silent): the needs
    that rose by RISE_AT or more during a trial, largest rise first."""
    spans = {}
    for row in experiment._rows_since:
        for motive in row.get("motives") or []:
            if not isinstance(motive, dict):
                continue
            motive_id = motive.get("id")
            value = motive.get("value")
            if (not isinstance(motive_id, str) or motive_id in skip or
                    isinstance(value, bool) or not isinstance(value, (int, float))):
                continue
            span = spans.get(motive_id)
            if span is None:
                spans[motive_id] = [value, value, value]
                continue
            span[2] = value
            if value > span[1]:
                span[1] = value
    risen = [(span[1] - span[0], motive_id, span) for motive_id, span in spans.items()
             if span[1] - span[0] >= RISE_AT]
    risen.sort(key=lambda item: (-item[0], item[1]))
    return [(motive_id, span) for _rise, motive_id, span in risen]


def _num(value):
    if value is None:
        return "?"
    return format(value, "g")


def _food_hold(experiment):
    """A31/D11: a running food or relief family is never cancelled. Hunger does not
    rise while she cooks, so "still rising" would cancel a cook halfway (R-PICK §5).
    D13: a sleep pushed for low energy is the cure; cutting it at 180 s defeats it."""
    rows = list(experiment._rows_since)
    if not rows:
        return False
    ids = set(experiment.children)
    ids.add(experiment.interaction_id)
    for entry in (rows[-1].get("interactions") or {}).get("observed") or []:
        if (entry.get("interaction_id") in ids and
                entry.get("membership") in e2_registry.RUNNING_MEMBERSHIPS):
            return True
    return False


def _queued_never_started(experiment):
    """The push itself is still only queued. A running child does not count."""
    for entry in (experiment._rows_since[-1].get("interactions") or {}).get("observed") or []:
        if (entry.get("interaction_id") == experiment.interaction_id and
                entry.get("membership") == "QUEUED"):
            return True
    return False


def _tuning_name(affordance):
    target = affordance if isinstance(affordance, type) else type(affordance)
    try:
        name = target.__name__
    except Exception:
        name = ""
    return str(name)[:128]


class E2Control:
    def __init__(self, emit, get_state, get_session_id, get_armed_snapshot,
                 get_writer, output, get_armed_name=None):
        self._emit_row = emit
        self._state = get_state
        self._session_id = get_session_id
        self._armed_snapshot = get_armed_snapshot
        self._writer = get_writer
        self._output = output
        self._armed_name = get_armed_name or (lambda: None)
        self._camera_at = None
        self._reset_state()

    # ------------------------------------------------------------------ state
    def _reset_state(self):
        self.last_prepared_token = None
        self.tokens = e2_admission.TokenBook()
        self.learner = e2_registry.CardLearner()
        self.experiments = {}
        self.open_ids = set()
        self.lineage_class = None
        self.load_ticks = None
        self.live_slot = None
        self.designated_sim_id = None
        self.save_subscribed = False
        self.pause_request = None
        self.experiment_counter = 0
        self.storm = e2_trial.StormCounter()
        self.presence = []
        self.act_ids = set()
        # 2.19.1: her pushed acts not yet finished, by interaction id: {act_id, base,
        # tuning_name, seen, misses}.
        self.pushed = {}

    def available(self):
        return (e2_actuator is not None and observers is not None and
                services is not None)

    # --------------------------------------------------------------- emitting
    def _event(self, kind, payload):
        keys = schema.E2_PAYLOAD_KEYS[kind]
        body = dict((key, None) for key in keys)
        body.update(payload)
        try:
            row = schema.make_record(
                kind, telemetry_session_id=self._session_id(),
                wall_timestamp_ms=int(time.time() * 1000),
                monotonic_ns=time.perf_counter_ns(), e2=body)
        except schema.SchemaError:
            return False
        return self._emit_row(row)

    def _experiment_event(self, phase, **payload):
        payload["phase"] = phase
        return self._event("experiment_event", payload)

    def _speed_event(self, phase, code=None, detail=None):
        return self._event("speed_event", {"phase": phase, "code": code, "detail": detail})

    def _lineage_event(self, record, **payload):
        payload["record"] = record
        payload["session_uuid"] = self._session_id()
        return self._event("lineage_event", payload)

    def _say(self, connection, text):
        try:
            self._output(text, connection)
        except Exception:
            pass

    # ------------------------------------------------------------- lifecycle
    def on_arm(self):
        self._reset_state()
        if not self.available():
            return
        try:
            e2_actuator.subscribe_saves(self.on_manual_save)
            self.save_subscribed = True
        except Exception:
            self.save_subscribed = False

    def on_stop(self, reason):
        """Called after a successful STOP (and by DISARM). Fail-safe cleanup."""
        self._release_pause(reason)
        for experiment in list(self.experiments.values()):
            if not experiment.closed:
                self._close_experiment(experiment)
        self.tokens.clear()

    def on_disarm(self):
        self.on_stop("DISARM")
        if self.save_subscribed and e2_actuator is not None:
            try:
                e2_actuator.unsubscribe_saves(self.on_manual_save)
            except Exception:
                pass
        self.save_subscribed = False

    # --------------------------------------------------------------- lineage
    def on_poll_row(self, row):
        """Feed every emitted presence row (game thread, after emit)."""
        if row.get("event_kind") == "presence_snapshot":
            self.presence.append(row)
            if len(self.presence) > 120:
                del self.presence[:-120]
            self._reconcile_pushed(row)
        if self.lineage_class is None:
            self._try_classify(row)
        learned = self.learner.observe(row, self.open_ids)
        if learned is not None:
            self._experiment_event("SIGNATURE_LEARNED", object_id=learned[0],
                                   detail=learned[1][:schema.MAX_DETAIL_LENGTH])
        for object_id, detail in self.learner.continuation_events:
            self._experiment_event("CONTINUATION_LEARNED", object_id=object_id,
                                   detail=detail[:schema.MAX_DETAIL_LENGTH])
        for experiment in list(self.experiments.values()):
            if experiment.closed:
                continue
            for claim in experiment.observe(row):
                self._experiment_event("CLAIM", experiment_id=experiment.experiment_id,
                                       object_id=experiment.object_id,
                                       interaction_id=experiment.interaction_id,
                                       code=claim, claims=dict(experiment.claims))
            if experiment.closed:
                self._emit_verdict(experiment)

    def _try_classify(self, row):
        writer = self._writer()
        if writer is None:
            return
        try:
            state, records = writer.ledger_snapshot()
        except AttributeError:
            return
        if state == "PENDING":
            return
        save = row.get("save") or {}
        body = row.get("body") or {}
        try:
            ticks = observers._saved_world_ticks()
        except Exception:
            ticks = None
        guid, slot, sim_id = save.get("save_slot_guid"), save.get("slot_id"), body.get("sim_id")
        if state != "OK":
            lineage_class = e2_lineage.FOREIGN_OR_UNKNOWN
        else:
            lineage_class = e2_lineage.classify(records, guid, slot, sim_id, ticks)
            designated = e2_lineage.designated_body(records, guid)
            self.designated_sim_id = None if designated is None else designated.get("sim_id")
        self.lineage_class = lineage_class
        self.load_ticks = ticks
        self.live_slot = slot
        self._lineage_event("LOAD_OBSERVED", guid=guid, slot_id=slot, sim_id=sim_id, ticks=ticks)
        self._lineage_event("CLASSIFIED", guid=guid, slot_id=slot, sim_id=sim_id, ticks=ticks,
                            lineage_class=lineage_class)

    def on_manual_save(self, *args, **kwargs):
        """Persistence-service callback (no arguments on 1.128). Armed only."""
        if self._state() not in ("ARMED", "SAMPLING") or observers is None:
            return
        try:
            save = observers._save_snapshot()
            saved_ticks = observers._saved_world_ticks()
        except Exception as error:
            self._lineage_event("SAVE_OBSERVED", lineage_class="READ_FAILURE:%s" %
                                type(error).__name__)
            return
        snap = self._armed_snapshot() or {}
        self._lineage_event("SAVE_OBSERVED", guid=save.get("save_slot_guid"),
                            slot_id=save.get("slot_id"), sim_id=snap.get("sim_id"),
                            ticks=saved_ticks, loaded_from_slot_id=self.live_slot)
        self.live_slot = save.get("slot_id")
        if self.lineage_class is not None:
            self.lineage_class = e2_lineage.reclassify_after_save(self.lineage_class)
            self._lineage_event("CLASSIFIED", guid=save.get("save_slot_guid"),
                                slot_id=save.get("slot_id"), sim_id=snap.get("sim_id"),
                                ticks=saved_ticks, lineage_class=self.lineage_class)

    # ------------------------------------------------------------- admission
    def _view(self, object_id):
        """Fresh plain-data admission view (game-thread reads only)."""
        view = {"sampling": self._state() == "SAMPLING",
                "lineage_class": self.lineage_class,
                "designated_sim_id": self.designated_sim_id}
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        save = observers._save_snapshot()
        game = observers._game_snapshot()
        queued = () if sim.queue is None else sim.queue
        running = () if sim.si_state is None else sim.si_state
        entries, _, _ = snapshot.merge_interactions(
            queued, running, observers._describe_interaction)
        posture = observers._posture_snapshot(sim) or {}
        obj = e2_actuator.find_object(object_id)
        offers = []
        context = e2_actuator.build_context(sim)
        if obj is not None:
            offers = e2_actuator.sit_offers(obj, context)
        view.update({
            "guid": save.get("save_slot_guid"), "slot_id": save.get("slot_id"),
            "sim_id": None if sim_info.id is None else str(sim_info.id),
            "body_available": sim is not None, "ticks": game.get("ticks"),
            "paused": game.get("paused"), "posture_target_id": posture.get("target_id"),
            "entries": entries,
            "object": {"exists": obj is not None, "sit_offer_count": len(offers)},
        })
        return view, sim, obj, offers, context

    def cmd_prepare(self, object_id, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        try:
            view, _, _, _, _ = self._view(object_id)
            code = e2_admission.check(view, object_id, EXCLUDED_OBJECT_IDS,
                                      self.learner.signatures, self.open_ids)
            if code is not None:
                self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
                self._say(connection, "PREPARE_REJECT %s" % code)
                return False
            token, code = self.tokens.issue(object_id, view, _now())
            if token is None:
                self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
                self._say(connection, "PREPARE_REJECT %s" % code)
                return False
            if self.designated_sim_id is None:
                self.designated_sim_id = view["sim_id"]
                self._lineage_event("DESIGNATED_BODY", guid=view["guid"], slot_id=view["slot_id"],
                                    sim_id=view["sim_id"], ticks=view["ticks"],
                                    lineage_class=self.lineage_class)
            self._experiment_event("PREPARE_OK", object_id=object_id, token=token)
            self.last_prepared_token = token
            self._say(connection, "PREPARE_OK token %s (30 s)" % token)
            return True
        except observers.LabIdentityAmbiguous:
            code = e2_admission.BODY_UNAVAILABLE
            self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
            self._say(connection, "PREPARE_REJECT %s" % code)
            return False
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code[:64])
            self._say(connection, "PREPARE_REJECT %s" % code)
            return False

    def cmd_sit(self, token, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        try:
            bound, code = self.tokens.consume(token, _now())
            if bound is None:
                self._experiment_event("ADMIT_REJECT", token=token, code=code)
                self._say(connection, "ADMIT_REJECT %s" % code)
                return False
            object_id = bound["object_id"]
            view, sim, obj, offers, context = self._view(object_id)
            code = e2_admission.admit(bound, view, object_id, EXCLUDED_OBJECT_IDS,
                                      self.learner.signatures, self.open_ids)
            if code is not None:
                extra = {}
                if code == e2_admission.STALE_SNAPSHOT:
                    underlying = e2_admission.check(
                        view, object_id, EXCLUDED_OBJECT_IDS,
                        self.learner.signatures, self.open_ids)
                    if underlying is not None:
                        extra["detail"] = underlying[:schema.MAX_DETAIL_LENGTH]
                self._experiment_event("ADMIT_REJECT", token=token, object_id=object_id,
                                       code=code, **extra)
                self._say(connection, "ADMIT_REJECT %s" % code)
                return False
            self.experiment_counter += 1
            experiment_id = "%s-%d" % (self._session_id()[:8], self.experiment_counter)
            pushed_ns = time.perf_counter_ns()
            interaction, detail = e2_actuator.push_sit(sim, obj, offers[0], context)
            if interaction is None:
                self._experiment_event("PUSH_FAILED", experiment_id=experiment_id,
                                       token=token, object_id=object_id,
                                       detail=(detail or "")[:schema.MAX_DETAIL_LENGTH])
                self._say(connection, "PUSH_FAILED")
                return False
            interaction_id = str(interaction.id)
            experiment = e2_registry.Experiment(
                experiment_id, token, object_id, view["sim_id"], interaction_id, pushed_ns,
                self.learner.signatures.get(object_id),
                [entry.get("interaction_id") for entry in view["entries"]],
                continuation=frozenset(self.learner.continuation.get(object_id, ())))
            self.experiments[experiment_id] = experiment
            self.open_ids.add(interaction_id)

            self._watch_finish(experiment, interaction)
            self._experiment_event("PUSHED", experiment_id=experiment_id, token=token,
                                   object_id=object_id, interaction_id=interaction_id,
                                   claims=dict(experiment.claims))
            self._say(connection, "PUSHED %s interaction %s" % (experiment_id, interaction_id))
            return True
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("ADMIT_REJECT", token=token, code=code[:64])
            self._say(connection, "ADMIT_REJECT %s" % code)
            return False

    def cmd_trial(self, object_id, guid64, connection):
        """Push one parameter-free affordance and judge it with an interaction card."""
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        if self.storm.latched():
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                   code=e2_trial.TRIAL_STORM)
            self._say(connection, "TRIAL_REJECT %s" % e2_trial.TRIAL_STORM)
            return False
        try:
            view, sim, obj, offers, context = self._trial_view(object_id, guid64)
            code = e2_trial.trial_check(view)
            if code is not None:
                self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                       code=code)
                self._say(connection, "TRIAL_REJECT %s" % code)
                return False
            self.experiment_counter += 1
            experiment_id = "%s-%d" % (self._session_id()[:8], self.experiment_counter)
            pushed_ns = time.perf_counter_ns()
            interaction, detail, kind = e2_actuator.push_affordance(
                sim, obj, offers[0], context)
            if interaction is None and kind == "refused":
                reason = (detail or "")[:schema.MAX_DETAIL_LENGTH]
                self._experiment_event("PUSH_REFUSED", experiment_id=experiment_id,
                                       object_id=object_id, guid64=guid64, detail=reason)
                self._say(connection, "PUSH_REFUSED %s" % reason)
                return False
            if interaction is None:
                self.storm.fail()
                self._experiment_event("PUSH_FAILED", experiment_id=experiment_id,
                                       object_id=object_id, guid64=guid64,
                                       detail=(detail or "")[:schema.MAX_DETAIL_LENGTH])
                self._say(connection, "PUSH_FAILED")
                return False
            self.storm.clear()
            interaction_id = str(interaction.id)
            tuning_name = _tuning_name(offers[0])
            route = e2_actuator.food_route(offers[0])
            if route is not None:
                card = e2_cards.need_card(object_id, guid64, motive="hunger", direction=1)
                control_rows = self._food_control(pushed_ns)
                window = e2_registry.FOOD_TRIAL_WINDOW_SECONDS
            else:
                card = e2_cards.interaction_card(object_id, guid64)
                control_rows = None
                window = e2_registry.TRIAL_WINDOW_SECONDS
            experiment = e2_registry.Experiment(
                experiment_id, None, object_id, view["sim_id"], interaction_id, pushed_ns,
                None, [entry.get("interaction_id") for entry in view["entries"]],
                continuation=(), card=card, control_rows=control_rows,
                window_seconds=window, food_route=route)
            experiment.tuning_name = tuning_name
            experiment.relief = e2_trial.relief_motives(view["motives"], tuning_name, route)
            experiment.interaction_ref = interaction
            self.experiments[experiment_id] = experiment
            self.open_ids.add(interaction_id)

            experiment.sim_ref = sim
            self._watch_finish(experiment, interaction)
            self._experiment_event("PUSHED", experiment_id=experiment_id,
                                   object_id=object_id, interaction_id=interaction_id,
                                   detail=("relief=%s" % ",".join(experiment.relief)
                                           if experiment.relief else None),
                                   guid64=guid64, card_class=card["card_class"],
                                   tuning_name=tuning_name, claims=dict(experiment.claims))
            self._say(connection, "TRIAL_PUSHED %s interaction %s" %
                      (experiment_id, interaction_id))
            return True
        except observers.LabIdentityAmbiguous:
            code = e2_admission.BODY_UNAVAILABLE
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64, code=code)
            self._say(connection, "TRIAL_REJECT %s" % code)
            return False
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                   code=code[:64])
            self._say(connection, "TRIAL_REJECT %s" % code)
            return False

    # ------------------------------------------------------------ acts (8f)
    def _act_event(self, act_id, phase, **payload):
        payload["act_id"] = act_id
        payload["phase"] = phase
        return self._event("act_event", payload)

    def _act_check(self, object_id, guid64):
        """None when her chosen action may be pushed now, else (code, detail).

        Unlike a trial there is no lab-only gate, no busy gate (it queues like a
        player's click) and no distress gate (her body's reflexes still act): she
        chose it. Lineage refuses only a different body."""
        if self._state() != "SAMPLING":
            return ("NOT_SAMPLING", None), None
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            return ("BODY_MISMATCH", None), None
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        if sim is None:
            return ("BODY_UNAVAILABLE", None), None
        if self.designated_sim_id is not None and str(sim_info.id) != self.designated_sim_id:
            return ("BODY_MISMATCH", None), None
        if object_id in EXCLUDED_OBJECT_IDS:
            return (e2_admission.OBJECT_EXCLUDED, None), None
        obj = e2_actuator.find_object(object_id)
        if obj is None:
            return ("NO_OBJECT", None), None
        context = e2_actuator.build_context(sim)
        offers = e2_actuator.offers_for(obj, context, guid64)
        if not offers:
            return ("NOT_OFFERED", None), None
        affordance = offers[0]
        try:
            person = obj.is_sim is True and obj is not sim
        except Exception:
            person = False
        excluded = e2_actuator.act_excluded(affordance, person)
        if excluded is not None:
            return ("EXCLUDED", excluded), None
        if not e2_actuator.user_directed(affordance):
            return ("NOT_USER_DIRECTED", None), None
        ok, reason = e2_actuator.preflight_test(sim, obj, affordance, context)
        if not ok:
            return ("GAME_REFUSED", reason), None
        return None, (sim, obj, affordance, context)

    def cmd_act(self, act_id, object_id, guid64, connection):
        """8f: push exactly the game action Ashley chose; never another, never twice.

        ACCEPTED is written before the push, so a failure in between leaves
        dispatched-but-unknown evidence (UNKNOWN), never nothing."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": object_id, "guid64": guid64}
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal, bound = self._act_check(object_id, guid64)
            if refusal is not None:
                code, detail = refusal
                self._act_event(act_id, "REJECTED", code=code,
                                detail=None if detail is None else str(detail)[:schema.MAX_DETAIL_LENGTH],
                                **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            sim, obj, affordance, context = bound
            tuning_name = _tuning_name(affordance)
            self._act_event(act_id, "ACCEPTED", tuning_name=tuning_name, **base)
            accepted = True
            interaction, detail, kind = e2_actuator.push_affordance(sim, obj, affordance, context)
            if interaction is None:
                code = "PUSH_REFUSED" if kind == "refused" else "PUSH_FAILED"
                self._act_event(act_id, "REJECTED", code=code, tuning_name=tuning_name,
                                detail=(detail or "")[:schema.MAX_DETAIL_LENGTH] or None, **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            interaction_id = str(interaction.id)
            self._act_event(act_id, "PUSHED", interaction_id=interaction_id,
                            tuning_name=tuning_name, **base)
            self._watch_act(act_id, base, interaction_id, tuning_name, interaction)
            self._say(connection, "ACT_PUSHED %s interaction %s" % (act_id, interaction_id))
            return True
        except observers.LabIdentityAmbiguous:
            phase, code = ("UNKNOWN", "BODY_UNAVAILABLE") if accepted else ("REJECTED", "BODY_UNAVAILABLE")
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    def _answer_check(self, dialog_id, pick):
        """None when her answer may be given now, else (code, detail). The dialog must be open
        and hers (or the game's own, with no owner); a row must be one it offers, enabled."""
        if self._state() != "SAMPLING":
            return ("NOT_SAMPLING", None), None
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            return ("BODY_MISMATCH", None), None
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        if sim is None:
            return ("BODY_UNAVAILABLE", None), None
        service = services.ui_dialog_service()
        dialog = service._active_dialogs.get(int(dialog_id))
        if dialog is None:
            return ("NO_DIALOG", None), None
        try:
            owner = dialog._owner()
        except Exception:
            owner = None
        if owner is not None and owner.id != sim_info.id:
            return ("NOT_HERS", None), None
        if pick.isdigit():
            rows = [row for row in observers._dialog_rows(dialog) if row["option_id"] == pick]
            if not rows:
                return ("NO_ROW", None), None
            if not rows[0]["enabled"]:
                return ("ROW_DISABLED", None), None
            return None, (service, dialog, int(pick), observers.RESPONSE_IDS["ok"])
        response = observers.RESPONSE_IDS.get(pick)
        offered = [item["response"] for item in observers._dialog_responses(dialog)]
        if response is None or (pick not in offered and pick not in ("ok", "cancel")):
            return ("NO_RESPONSE", pick), None
        return None, (service, dialog, None, response)

    def cmd_answer(self, act_id, dialog_id, pick, connection):
        """2.18.0: answer a game dialog as she chose, the way the client does: pick the row
        (dialog_pick_result), then respond (dialog_respond). Once per act id."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": dialog_id, "guid64": pick if pick.isdigit() else None}
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal, bound = self._answer_check(dialog_id, pick)
            if refusal is not None:
                code, detail = refusal
                self._act_event(act_id, "REJECTED", code=code,
                                detail=None if detail is None else str(detail)[:schema.MAX_DETAIL_LENGTH], **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            service, dialog, row, response = bound
            kind = _tuning_name(dialog)
            self._act_event(act_id, "ACCEPTED", tuning_name=kind, **base)
            accepted = True
            if row is not None:
                service.dialog_pick_result(int(dialog_id), [row])
            service.dialog_respond(int(dialog_id), response)
            _send_queued_events()
            self._act_event(act_id, "FINISHED", tuning_name=kind, finishing_type="ANSWERED", **base)
            self._say(connection, "ACT_ANSWERED %s" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    def cmd_cancel(self, act_id, interaction_id, connection):
        """2.20.0 (live 2026-10-06: her meal waited behind an open-ended piano song she had no
        way to stop): she stops one of her own actions, running or queued, the way the client's
        X does (interactions.cancel_si: find it on her Sim, or its continuation, then
        cancel_user). The game may refuse. Once per act id."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": interaction_id, "guid64": None}
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal = None
            sim = None
            if self._state() != "SAMPLING":
                refusal = "NOT_SAMPLING"
            elif self.lineage_class == e2_lineage.BODY_MISMATCH:
                refusal = "BODY_MISMATCH"
            else:
                _sim_info, sim = observers.select_lab_body(
                    services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
                if sim is None:
                    refusal = "BODY_UNAVAILABLE"
            interaction = None
            if refusal is None:
                interaction = sim.find_interaction_by_id(int(interaction_id))
                if interaction is None:
                    interaction = sim.find_continuation_by_id(int(interaction_id))
                if interaction is None:
                    refusal = "NO_INTERACTION"
            if refusal is not None:
                self._act_event(act_id, "REJECTED", code=refusal, **base)
                self._say(connection, "ACT_REJECT %s" % refusal)
                return False
            tuning_name = _tuning_name(interaction)
            self._act_event(act_id, "ACCEPTED", tuning_name=tuning_name, **base)
            accepted = True
            if not interaction.cancel_user(cancel_reason_msg="Ashley stopped it."):
                self._act_event(act_id, "REJECTED", code="GAME_REFUSED", tuning_name=tuning_name, **base)
                self._say(connection, "ACT_REJECT GAME_REFUSED")
                return False
            self._act_event(act_id, "FINISHED", tuning_name=tuning_name, finishing_type="STOPPED", **base)
            self._say(connection, "ACT_STOPPED %s" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    def cmd_camera(self, op, target_id, connection):
        """2.21.0 (E5): the overlay's camera director looks at her Sim (following) or at one
        object. It moves only the view: no act id, no act_event, nothing in her ledger. Refused
        unless sampling her own body, and at most one op per CAMERA_MIN_GAP_S."""
        if not self.available() or focus_on_sim is None or focus_on_object is None:
            self._say(connection, "CAMERA_REJECT UNAVAILABLE")
            return False
        if self._state() != "SAMPLING":
            self._say(connection, "CAMERA_REJECT NOT_SAMPLING")
            return False
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            self._say(connection, "CAMERA_REJECT BODY_MISMATCH")
            return False
        now = time.monotonic()
        if self._camera_at is not None and now - self._camera_at < CAMERA_MIN_GAP_S:
            self._say(connection, "CAMERA_REJECT TOO_SOON")
            return False
        try:
            if op == "follow_sim":
                sim_info = services.sim_info_manager().get(int(target_id))
                sim = sim_info.get_sim_instance() if sim_info is not None else None
                if sim is None:
                    self._say(connection, "CAMERA_REJECT NO_TARGET")
                    return False
                focus_on_sim(sim=sim, follow=True)
            else:
                obj = services.object_manager().get(int(target_id))
                if obj is None:
                    self._say(connection, "CAMERA_REJECT NO_TARGET")
                    return False
                focus_on_object(object=obj, follow=False)
            _send_queued_events()
            self._camera_at = now
            self._say(connection, "CAMERA_OK %s %s" % (op, target_id))
            return True
        except Exception as error:
            self._say(connection, ("CAMERA_REJECT E2_EXCEPTION:%s" % type(error).__name__)[:64])
            return False

    def _reconcile_pushed(self, row):
        """2.19.1 (live 2026-10-06: a quick meal pushed while she was in the bath never
        appeared in her queue and never finished, so she believed it was still waiting):
        a pushed act whose interaction is missing from her queue for LEFT_QUEUE_SAMPLES
        samples in a row, with no finish from the game, is UNKNOWN (LEFT_QUEUE): it is gone
        and nobody can tell how it ended."""
        if not self.pushed:
            return
        observed = ((row.get("interactions") or {}).get("observed")) or []
        present = set(str(entry.get("interaction_id")) for entry in observed if isinstance(entry, dict))
        for interaction_id in list(self.pushed):
            item = self.pushed[interaction_id]
            if interaction_id in present:
                item["seen"], item["misses"] = True, 0
                continue
            item["misses"] += 1
            if item["misses"] < LEFT_QUEUE_SAMPLES:
                continue
            del self.pushed[interaction_id]
            self._act_event(item["act_id"], "UNKNOWN", code="LEFT_QUEUE", interaction_id=interaction_id,
                            tuning_name=item["tuning_name"],
                            detail="ran, then left" if item["seen"] else "never seen in her queue",
                            **item["base"])

    def _watch_act(self, act_id, base, interaction_id, tuning_name, interaction):
        self.pushed[interaction_id] = {"act_id": act_id, "base": base, "tuning_name": tuning_name,
                                       "seen": False, "misses": 0}

        def _finished(finished_interaction, _act_id=act_id):
            if self.pushed.pop(interaction_id, None) is None:
                return  # already recorded as gone
            try:
                finishing = str(finished_interaction.finishing_type)
            except Exception:
                finishing = "UNREADABLE"
            self._act_event(_act_id, "FINISHED", interaction_id=interaction_id,
                            tuning_name=tuning_name,
                            finishing_type=finishing[:schema.MAX_DISPLAY_TEXT_LENGTH], **base)

        try:
            e2_actuator.watch_finish(interaction, _finished)
        except Exception:
            return

    def _trial_view(self, object_id, guid64):
        view, sim, obj, _sit_offers, context = self._view(object_id)
        offers = []
        if obj is not None:
            offers = e2_actuator.offers_for(obj, context, guid64)
        excluded = bool(offers) and e2_actuator.excluded(offers[0]) is not None
        motives = []
        try:
            sim_info, _sim = observers.select_lab_body(
                services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
            motives = observers.read_motives(sim_info, view.get("ticks") or 0) or []
        except Exception:
            motives = []
        view["armed_name"] = self._armed_name()
        view["object_id"] = object_id
        view["excluded_ids"] = EXCLUDED_OBJECT_IDS
        view["own_open_ids"] = self.open_ids
        view["motives"] = motives
        view["tuning_name"] = _tuning_name(offers[0]) if offers else None
        view["food_route"] = e2_actuator.food_route(offers[0]) if offers else None
        view["object"] = {"exists": obj is not None, "offer_count": len(offers),
                          "excluded": excluded, "sit_offer_count": view["object"]["sit_offer_count"]}
        return view, sim, obj, offers, context

    def _food_control(self, pushed_ns):
        """Presence rows from the last 60 s before this push."""
        window = int(60 * 1e9)
        found = []
        for row in self.presence:
            mono = row.get("monotonic_ns")
            if type(mono) is int and 0 <= pushed_ns - mono <= window:
                found.append(row)
        return found

    def _watch_finish(self, experiment, interaction):
        def _finished(finished_interaction, _experiment=experiment):
            try:
                finishing = str(finished_interaction.finishing_type)
            except Exception:
                finishing = "UNREADABLE"
            mono = None
            if observers is not None:
                try:
                    mono = observers._monotonic_ns()
                except Exception:
                    mono = None
            _experiment.finish(finishing[:schema.MAX_DISPLAY_TEXT_LENGTH], mono)
            self._experiment_event("FINISHED_CALLBACK",
                                   experiment_id=_experiment.experiment_id,
                                   interaction_id=_experiment.interaction_id,
                                   finishing_type=_experiment.finishing_type,
                                   claims=dict(_experiment.claims))

        try:
            e2_actuator.watch_finish(interaction, _finished)
        except Exception:
            return

    def _close_experiment(self, experiment):
        experiment.close()
        self._emit_verdict(experiment)

    def _end_trial_action(self, experiment):
        """A25: a trial's own action does not outlive its verdict.

        A TV watch keeps running with autonomy off, so the next trial would be
        BODY_BUSY forever. Only the interaction this probe pushed is cancelled.
        """
        try:
            interaction = experiment.interaction_ref
        except AttributeError:
            interaction = None
        experiment.interaction_ref = None
        try:
            children = list(experiment.children)
        except AttributeError:
            children = []
        try:
            sim = experiment.sim_ref
        except AttributeError:
            sim = None
        if interaction is None and not children:
            return
        if (experiment.food_route or experiment.relief) and _food_hold(experiment):
            if _queued_never_started(experiment) and interaction is not None:
                try:
                    e2_actuator.cancel_own(interaction)
                except Exception:
                    pass
            self._experiment_event("TRIAL_CLEANUP", experiment_id=experiment.experiment_id,
                                   object_id=experiment.object_id,
                                   interaction_id=experiment.interaction_id,
                                   detail=("food_left_running" if experiment.food_route
                                           else "relief_left_running"))
            return
        if experiment.claims["FINISHED"] or interaction is None:
            result = "ALREADY_FINISHED" if interaction is None or experiment.claims["FINISHED"] else "CANCELLED"
        else:
            try:
                e2_actuator.cancel_own(interaction)
                result = "CANCELLED"
            except Exception as error:
                result = ("CANCEL_FAILED:%s" % type(error).__name__)[:schema.MAX_DETAIL_LENGTH]
        if interaction is None:
            result = "ALREADY_FINISHED"
        try:
            cancelled = e2_actuator.cancel_ids(sim, children)
        except Exception:
            cancelled = 0
        if cancelled:
            result = ("%s children=%d" % (result, cancelled))[:schema.MAX_DETAIL_LENGTH]
        self._experiment_event("TRIAL_CLEANUP", experiment_id=experiment.experiment_id,
                               object_id=experiment.object_id,
                               interaction_id=experiment.interaction_id, detail=result)

    def _emit_verdict(self, experiment):
        self.open_ids.discard(experiment.interaction_id)
        detail = ""
        if experiment.food_route:
            before, peak, after = _hunger_span(experiment)
            detail = "route=%s hunger=%s->%s->%s " % (
                experiment.food_route, before, peak, after)
        for motive_id in experiment.relief:
            # D26 (live sleep PASS said nothing about energy): a relief trial reports
            # what the cure did to the need it relieves.
            if motive_id == "hunger" and experiment.food_route:
                continue
            before, peak, after = _motive_span(experiment, motive_id)
            detail += "relief=%s %s=%s->%s->%s " % (motive_id, motive_id, before, peak, after)
        detail += "foreign_roots=%d incomplete_rows=%d continuation=%d mixers=%d family=%d" % (
            len(experiment.foreign_roots), experiment.incomplete_rows,
            len(experiment.continuation_entries), len(experiment.child_mixers),
            len(experiment.children))
        skip = set(experiment.relief)
        if experiment.food_route:
            skip.add("hunger")
        for motive_id, span in _risen(experiment, skip):
            # After the counts: if the detail is too long, these are cut first.
            detail += " rose=%s %s->%s->%s" % (
                motive_id, _num(span[0]), _num(span[1]), _num(span[2]))
        finishing = experiment.finishing_type
        natural = finishing == "FinishingType.NATURAL"
        user_cancel = finishing == "FinishingType.USER_CANCEL"
        if finishing is not None and not natural and not user_cancel:
            detail += " interrupted=%s" % finishing
        if (experiment.verdict == e2_registry.OUTCOME_UNKNOWN and
                not experiment.claims["STARTED"]):
            detail += " never_started=1"
        detail = detail[:schema.MAX_DETAIL_LENGTH]
        extra = {}
        card = experiment.card
        if card.get("card_class") in ("interaction", "need"):
            guid = card.get("affordance_guid64")
            extra["guid64"] = None if guid is None else str(guid)
            extra["card_class"] = card.get("card_class")
            try:
                tuning_name = experiment.tuning_name
            except AttributeError:
                tuning_name = None
            extra["tuning_name"] = tuning_name
            extra["ambiguous"] = list(experiment.ambiguous)[:16]
        self._experiment_event("VERDICT", experiment_id=experiment.experiment_id,
                               object_id=experiment.object_id,
                               interaction_id=experiment.interaction_id,
                               code=experiment.verdict, claims=dict(experiment.claims),
                               finishing_type=experiment.finishing_type, detail=detail,
                               **extra)
        self._end_trial_action(experiment)

    # ----------------------------------------------------------------- speed
    def cmd_pause(self, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        if self._state() != "SAMPLING":
            self._speed_event("REJECT", code="NOT_SAMPLING")
            self._say(connection, "PAUSE_REJECT NOT_SAMPLING")
            return False
        if self.pause_request is not None:
            self._speed_event("REJECT", code="ALREADY_REQUESTED")
            self._say(connection, "PAUSE_REJECT ALREADY_REQUESTED")
            return False
        try:
            self.pause_request = e2_actuator.push_pause()
        except Exception as error:
            self.pause_request = None
            self._speed_event("REJECT", code="E2_EXCEPTION:%s" % type(error).__name__)
            self._say(connection, "PAUSE_REJECT EXCEPTION")
            return False
        self._speed_event("REQUEST_PUSHED")
        self._say(connection, "PAUSE_REQUESTED")
        return True

    def cmd_release(self, connection):
        if self.pause_request is None:
            self._speed_event("REJECT", code="NO_REQUEST")
            self._say(connection, "RELEASE_REJECT NO_REQUEST")
            return False
        if not self._remove_request():
            self._speed_event("RELEASE_FAILED", code="REMOVE_FAILED")
            self._say(connection, "RELEASE_FAILED")
            return False
        self._speed_event("REQUEST_REMOVED")
        self._say(connection, "RELEASED")
        return True

    def _remove_request(self):
        try:
            e2_actuator.remove_pause(self.pause_request)
        except Exception:
            return False
        self.pause_request = None
        return True

    def _release_pause(self, reason):
        if self.pause_request is None:
            return
        if self._remove_request():
            self._speed_event("RELEASED_ON_DISARM" if reason == "DISARM" else
                              "RELEASED_ON_STOP", detail=reason)
        else:
            self._speed_event("RELEASE_FAILED", code="REMOVE_FAILED", detail=reason)
