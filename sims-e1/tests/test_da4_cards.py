"""DA4 class cards: posture stays the sit ladder; other classes stay conservative."""
import json
import os
import unittest

from test_e2 import CHAIR, _entry, _load_pure, _row

PIE = "InteractionSource.PIE_MENU"
SCRIPT = "InteractionSource.SCRIPT_WITH_USER_INTENT"
POSTURE = "InteractionSource.POSTURE_GRAPH"
AUTO = "InteractionSource.AUTONOMY"


def _evidence(folder):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    directory = os.path.join(root, "sims-e1", "evidence", folder)
    name = "ashley_e1_863ffab5-edd0-44c2-b74b-5ce9b2d352a3.jsonl"
    return os.path.join(directory, name)


def _hunger(mono_s, entries, value, complete=True, age=0):
    return {"monotonic_ns": int(mono_s * 1e9), "observation_complete": complete,
            "interactions": {"observed": [dict(e) for e in entries]},
            "motives": [{"id": "hunger", "value": value, "band": "FINE", "age_ticks": age}],
            "body": {"posture": {}}}


class CardTests(unittest.TestCase):
    def setUp(self):
        _, _, self.reg, _, _ = _load_pure()
        from ashley_e1 import e2_cards
        self.cards = e2_cards

    def _posture(self, signature="sit", object_id=CHAIR):
        return self.cards.posture_card(object_id, signature)

    def _experiment(self, card, control_rows=(), signature="sit", interaction_id="100",
                    pushed=0, baseline=()):
        return self.reg.Experiment(
            "e-1", "t" * 16, CHAIR, "s", interaction_id, pushed, signature, list(baseline),
            card=card, control_rows=control_rows)

    def test_validate_four_classes_and_rejects_bad(self):
        accepted = [
            self._posture(),
            {"card_class": "interaction", "affordance_guid64": 31564, "object_id": CHAIR,
             "signature": None, "motive": None, "direction": None, "min_net_delta": 5.0},
            {"card_class": "need", "affordance_guid64": None, "object_id": None,
             "signature": None, "motive": "hunger", "direction": 1, "min_net_delta": 5.0},
            {"card_class": "need", "affordance_guid64": None, "object_id": None,
             "signature": None, "motive": "energy", "direction": -1, "min_net_delta": 5},
            {"card_class": "social", "affordance_guid64": None, "object_id": "sim-b",
             "signature": None, "motive": None, "direction": None, "min_net_delta": 5.0},
        ]
        for card in accepted:
            self.cards.validate_card(card)
        bad = [
            {},
            dict(accepted[0], card_class="mood"),
            dict(accepted[0], extra=1),
            dict(accepted[2], motive="thirst"),
            dict(accepted[2], direction=2),
            dict(accepted[2], direction=True),
            dict(accepted[1], affordance_guid64=True),
            dict(accepted[0], signature=None),
            dict(accepted[1], signature="sit"),
            dict(accepted[0], min_net_delta="5"),
        ]
        # signature None is legal for an unlearned posture card; reject a non-string.
        bad[-3] = dict(accepted[0], signature=1)
        for card in bad:
            with self.assertRaises(ValueError):
                self.cards.validate_card(card)

    def test_posture_card_matches_signature_claims_and_verdict(self):
        ours_q = _entry("100", SCRIPT, "QUEUED", CHAIR)
        ours_r = dict(ours_q, membership="RUNNING")
        queued = _entry("200", AUTO, "QUEUED", CHAIR, "14244")
        running = dict(queued, membership="RUNNING")
        sequences = [
            [_row(1, [ours_q]), _row(2, [ours_r], "sit", CHAIR),
             _row(8, [ours_r], "sit", CHAIR), _row(12.5, [ours_r], "sit", CHAIR)],
            [_row(1, [ours_r], "sit", CHAIR), _row(2, [ours_r, queued], "sit", CHAIR),
             _row(3, [ours_r, running], "sit", CHAIR), _row(13, [ours_r, running], "sit", CHAIR)],
        ]
        for rows in sequences:
            plain = self.reg.Experiment(
                "e-1", "t" * 16, CHAIR, "s", "100", 0, "sit", ["1", "2"],
                continuation=("14244",))
            via = self.reg.Experiment(
                "e-1", "t" * 16, CHAIR, "s", "100", 0, "sit", ["1", "2"],
                continuation=("14244",), card=self._posture())
            for row in rows:
                self.assertEqual(plain.observe(row), via.observe(dict(row)))
            self.assertEqual(plain.claims, via.claims)
            self.assertEqual(plain.close(), via.close())
            self.assertEqual(plain.foreign_roots, via.foreign_roots)
            self.assertEqual(plain.continuation_entries, via.continuation_entries)
            self.assertEqual(plain.started_ns, via.started_ns)
            self.assertEqual(plain.effect_since_ns, via.effect_since_ns)
            self.assertEqual(plain.attributed_ns, via.attributed_ns)
            self.assertEqual(via.ambiguous, [])

    def test_interaction_pass_and_foreign_root(self):
        card = {"card_class": "interaction", "affordance_guid64": 1, "object_id": CHAIR,
                "signature": None, "motive": None, "direction": None, "min_net_delta": 5.0}
        ours = _entry("100", SCRIPT, "RUNNING", CHAIR)
        good = self._experiment(card, signature=None)
        good.observe(_row(1, [ours], "stand", None))
        good.observe(_row(11, [ours], "stand", None))
        self.assertEqual(good.close(), self.reg.PASS)
        foreign = self._experiment(card, signature=None)
        other = _entry("9", PIE, "RUNNING", "elsewhere")
        foreign.observe(_row(1, [ours, other]))
        foreign.observe(_row(11, [ours, other]))
        self.assertEqual(foreign.close(), self.reg.OUTCOME_UNKNOWN)
        self.assertTrue(foreign.foreign_roots)

    def _need_card(self):
        return {"card_class": "need", "affordance_guid64": None, "object_id": None,
                "signature": None, "motive": "hunger", "direction": 1, "min_net_delta": 5.0}

    def _control(self):
        return [_hunger(10, [], 10), _hunger(20, [], 10)]

    def test_need_pass_against_flat_control(self):
        card = self._need_card()
        ours = _entry("100", SCRIPT, "RUNNING", CHAIR)
        pushed = int(30 * 1e9)
        exp = self._experiment(card, self._control(), signature=None, pushed=pushed)
        exp.observe(_hunger(31, [ours], 10))
        exp.observe(_hunger(35, [ours], 40))
        exp.observe(_hunger(39, [ours], 40))
        exp.observe(_hunger(43, [ours], 40))
        exp.observe(_hunger(45, [ours], 40))
        self.assertEqual(exp.ambiguous, [])
        self.assertEqual(exp.close(), self.reg.PASS)

    def test_need_ambiguities_block_and_are_recorded(self):
        card = self._need_card()
        ours = _entry("100", SCRIPT, "RUNNING", CHAIR)
        pushed = int(30 * 1e9)
        cases = {
            "no_control": dict(control=[_hunger(20, [], 10)]),
            "missing_motive": dict(drop_motive=True),
            "stale_value": dict(age=self.cards.NEED_FRESH_TICKS + 1),
            "incomplete_row": dict(complete=False),
            "gap": dict(gap=True),
            "overlapping_si": dict(overlap=True),
        }
        for reason, options in cases.items():
            exp = self._experiment(card, options.get("control", self._control()),
                                   signature=None, pushed=pushed)
            overlap = [_entry("9", SCRIPT, "RUNNING", "other")] if options.get("overlap") else []
            first = _hunger(31, [ours] + overlap, 10, age=options.get("age", 0),
                            complete=options.get("complete", True))
            if options.get("drop_motive"):
                first["motives"] = []
            exp.observe(first)
            if options.get("gap"):
                exp.observe(_hunger(31 + 6, [ours], 40))
            else:
                exp.observe(_hunger(35, [ours] + overlap, 40, age=options.get("age", 0),
                                    complete=options.get("complete", True)))
                exp.observe(_hunger(45, [ours] + overlap, 40, age=options.get("age", 0),
                                    complete=options.get("complete", True)))
            self.assertIn(reason, exp.ambiguous, reason)
            self.assertEqual(exp.close(), self.reg.OUTCOME_UNKNOWN, reason)

    def test_social_target_is_unobserved(self):
        """schema social entries have no participant identity, only a target."""
        card = {"card_class": "social", "affordance_guid64": None, "object_id": "sim-b",
                "signature": None, "motive": None, "direction": None, "min_net_delta": 5.0}
        ours = _entry("100", SCRIPT, "RUNNING", "sim-b")
        social = {"entry_key": "k", "interaction_id": "100", "affordance_id": "1",
                  "affordance_text": "chat", "target_id": "sim-b", "source_raw": SCRIPT,
                  "source_norm": "USER", "source_confidence": "LITERAL", "present": True,
                  "membership": "RUNNING"}
        row = _row(1, [ours])
        row["social"] = [social]
        effect, reason = self.cards.evaluate_effect(
            card, {"interaction_id": "100", "foreign_roots": []}, row)
        self.assertEqual((effect, reason), (False, "social_target_unobserved"))
        exp = self._experiment(card, signature=None)
        exp.observe(row)
        exp.observe(_row(11, [ours]))
        self.assertEqual(exp.ambiguous, ["social_target_unobserved"])
        self.assertEqual(exp.close(), self.reg.OUTCOME_UNKNOWN)

    def test_learner_alias_and_cards(self):
        self.assertIs(self.reg.SignatureLearner, self.reg.CardLearner)
        path = _evidence("E2_N5_BOOTSTRAP_2026-09-30_02")
        if not os.path.isfile(path):
            self.skipTest("missing N5 evidence file")
        learner = self.reg.CardLearner()
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("event_kind") != "presence_snapshot":
                    continue
                learner.observe(row, set())
        chair = "118245043789434055"
        self.assertEqual(learner.signatures.get(chair), "sit")
        self.assertEqual(learner.continuation.get(chair), {"14244"})
        found = learner.cards()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["card_class"], "posture")
        self.assertEqual(found[0]["object_id"], chair)
        self.assertEqual(found[0]["signature"], "sit")

    def test_t1_and_n5_posture_card_verdicts_match(self):
        path = _evidence("E2_T1_T3_2026-09-30_01")
        if not os.path.isfile(path):
            self.skipTest("missing T1 evidence file")
        rows = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        chair = "118245043789434055"
        pushed = None
        before = None
        after = []
        for row in rows:
            if row.get("event_kind") == "presence_snapshot":
                if pushed is None:
                    before = row
                else:
                    after.append(row)
            e2 = row.get("e2") or {}
            if (row.get("event_kind") == "experiment_event" and
                    e2.get("phase") == "PUSHED" and e2.get("interaction_id") == "7223"):
                pushed = row
        self.assertIsNotNone(pushed)
        baseline = [e.get("interaction_id")
                    for e in (before.get("interactions") or {}).get("observed") or []]
        card = self._posture("sit", chair)

        def run(continuation):
            plain = self.reg.Experiment(
                "t1", "t" * 16, chair, "s", "7223", pushed["monotonic_ns"],
                "sit", baseline, continuation=continuation)
            via = self.reg.Experiment(
                "t1", "t" * 16, chair, "s", "7223", pushed["monotonic_ns"],
                "sit", baseline, continuation=continuation, card=card)
            for row in after:
                self.assertEqual(plain.observe(row), via.observe(row))
                if plain.closed:
                    break
            self.assertEqual(plain.close(), via.close())
            return via

        attributed = run(frozenset(("14244",)))
        self.assertEqual(attributed.verdict, self.reg.PASS)
        unknown = run(frozenset())
        self.assertEqual(unknown.verdict, self.reg.OUTCOME_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
