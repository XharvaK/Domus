"""AST-only shipped-source and artifact checks for the E1/E2 build."""

import ast
import hashlib
import os
import zipfile


APPROVED_STDLIB_IMPORTS = {
    # "math": 2.40.0 (W13 P2 fix, HOME-5): the yaw angle of a facing (e2_actuator's search); pure arithmetic.
    "hashlib", "json", "math", "os", "pathlib", "queue", "struct", "sys",
    "threading", "time", "uuid",
}
APPROVED_GAME_ROOTS = {
    "alarms", "clock", "date_and_time", "interactions", "objects",
    "placement", "scheduling", "server", "services", "sims", "sims4",
}
PRODUCTION_MODULES = (
    "__init__", "probe", "observers", "snapshot", "schema", "writer",
    "e2_admission", "e2_lineage", "e2_registry", "e2_cards", "e2_actuator", "e2_control", "cmdbox",
    "e2_trial", "preflight", "food", "situation",
    # 2.40.0 (W13 P1): her reach (discovery and lists; pure).
    "reach",
    # 2.40.0 (W13 P2): the home verbs and the things and catalogue lists.
    "home",
    # 2.40.0 (W13 P2 fix, CORE-16): the build tables, the atlas and the menu, which the shipped build also carries.
    "atlas", "tuned", "act_menu",
)
# DS3: build_buy also holds world mutators; only its read-only room lookup may be
# imported, and only by name (never `import build_buy`).
NARROW_GAME_IMPORTS = {"build_buy": {"get_room_id", "is_location_pool",
                                     # 2.40.0 (W13 P2 fix, HOME-3): the read-only flag getters a definition's
                                     # buy categories and placement come from (e2_actuator only).
                                     "get_object_buy_category_flags", "get_object_placement_flags"},
                       # 2.20.1: only the Distributor, to send the game's queued events now.
                       "distributor.system": {"Distributor"},
                       # 2.21.0: only the two view calls; they move the camera, never the world.
                       "camera": {"focus_on_sim", "focus_on_object"},
                       # 2.26.0: only the game's notification, to show one line of text. e2_control only.
                       "ui.ui_dialog_notification": {"UiDialogNotification"},
                       # 2.31.0: the dialog base and its overriders, to hold or withhold the windows she is
                       # offered (e2_control only; see E2_CONTROL_ASSIGNABLE).
                       "ui.ui_dialog": {"UiDialogBase"},
                       "objects.color.object_color_dialog": {"UiDialogObjectColorPicker"},
                       "sims.sim_dialogs": {"SimPersonalityAssignmentDialog"},
                       "ui.ui_dialog_picker": {"UiMapViewPicker", "UiApartmentPicker"},
                       # 2.23.0: the close message _dialog_cancel_internal builds. e2_control only.
                       "protocolbuffers": {"Consts_pb2", "Dialog_pb2"},
                       # 2.40.0 (W13 P1): her trip's call, and the event's guest list (e2_actuator's own effect calls).
                       "world.travel_service": {"travel_sim_to_zone"},
                       "situations.situation_guest_list": {"SituationGuestInfo", "SituationGuestList",
                                                           "SituationInvitationPurpose"},
                       # 2.40.0 (W13 P2, home): the object creator, the one name the home verbs make an object with.
                       "objects.system": {"create_object"}}
# 2.31.0: modules whose names only e2_control.py may import.
E2_CONTROL_ONLY_MODULES = frozenset(("protocolbuffers", "ui.ui_dialog", "ui.ui_dialog_notification",
                                     "ui.ui_dialog_picker", "objects.color.object_color_dialog",
                                     "sims.sim_dialogs"))
# 2.31.0: dialog_cancel closes the map or apartment window she may not see (e2_control only).
# 2.31.0 (W3p): her pace. The decay-rate modifier on each motive she has (added and removed, each followed by
# its progress message), and the clock sync after the game clock's normal speed is set. e2_control only.
E2_CONTROL_ONLY_CALLS = frozenset(("dialog_cancel", "add_decay_rate_modifier", "remove_decay_rate_modifier",
                                   "send_commodity_progress_msg", "_sync_clock_and_broadcast_gameclock",
                                   # R3 (PROBE3-14): the interaction cancel of a pushed act, the cancel path (e2_control only).
                                   "cancel_user"))
# 2.31.0 adds dialog_text_input (every text field) and dialog_pick_result_def_ids_and_counts (counted rows).
# 2.23.0, cmd_answer only. Reviewed path: ui/ui_dialog_service._dialog_cancel_internal
# (Dialog_pb2.UiDialogCloseRequest, Consts_pb2.MSG_UI_DIALOG_CLOSE, Distributor.add_event
# with immediate=True). The dialog pause is released by clock.GameClock.pop_speed of the
# UI_MODAL PAUSED request, the same release as server_commands/clock_commands.unrequest_pause.
# If that request is absent, clock.GameClock.set_clock_speed, which is what
# server_commands/clock_commands.set_speed calls.
ANSWER_ONLY_CALLS = {"UiDialogCloseRequest", "add_event", "pop_speed", "set_clock_speed",
                      "dialog_text_input", "dialog_pick_result_def_ids_and_counts"}
ANSWER_ONLY_FILE = "e2_control.py"
ANSWER_ONLY_FUNC = "cmd_answer"
# 2.27.0: the first game attribute the probe replaced (e2_control's picker hold, now _install_holds).
# 2.31.0: the fixed allow-list of game attributes e2_control.py alone may replace (_install_holds):
# the dialog sends of UiDialogBase and of its overriders the hold reaches, and the three Distributor
# senders (add_event for the phone ring and client screens; add_op and add_op_with_no_owner for ops).
E2_CONTROL_ASSIGNABLE = frozenset((
    "ui.ui_dialog.UiDialogBase.distribute_dialog",
    "objects.color.object_color_dialog.UiDialogObjectColorPicker.distribute_dialog",
    "sims.sim_dialogs.SimPersonalityAssignmentDialog.distribute_dialog",
    "ui.ui_dialog_picker.UiMapViewPicker.distribute_dialog",
    "ui.ui_dialog_picker.UiApartmentPicker.distribute_dialog",
    # 2.36.0 (D6, P2): the notice observer. It reads each notification as it is shown and never holds it.
    "ui.ui_dialog_notification.UiDialogNotification.distribute_dialog",
    "distributor.system.Distributor.add_event",
    "distributor.system.Distributor.add_op",
    "distributor.system.Distributor.add_op_with_no_owner",
    # 2.31.0 (W3p): the game clock's normal speed, asserted while she samples at a slower pace (e2_control only).
    "clock.GameClock.NORMAL_SPEED_MULTIPLIER",
))
FORBIDDEN_IMPORT_ROOTS = {
    "http", "importlib", "s4cl", "shm", "socket", "ssl", "subprocess", "urllib",
}
FORBIDDEN_CALL_NAMES = {
    "__import__", "add_buff", "add_selectable_sim_info", "advance_current_time",
    "cancel", "compile", "destroy", "disable_autonomy", "enable_autonomy",
    "eval", "exec", "execute", "inject_safely_into", "pause_the_game",
    "push_super_affordance", "remove_buff", "remove_selectable_sim_info", "reset",
    "save_game_gen", "save_using", "set_active_sim", "set_clock_speed",
    "set_current_time", "system", "test_and_execute",
}
# E2 actuation calls: allowed ONLY in e2_actuator.py (plan E2 §4), forbidden elsewhere.
ACTUATOR_ONLY_CALLS = {
    "push_super_affordance", "push_speed", "remove_request",
    "register_on_finishing_callback", "add_manual_save_complete_callback",
    "remove_manual_save_complete_callback", "cancel",
    # 2.39.0 (W12 G1): a pie choice's own pair runs as a player's pick runs it; push_super_affordance is the same call.
    "test_and_execute",
    # 2.40.0 (W13 P1): her trip (the game's travel service), her planned event (the zone's situation manager) and the
    # household's funds for that event: the actuator's own effect calls, e2_actuator.py only.
    "travel_sim_to_zone", "create_situation", "try_remove",
    # 2.40.0 (W13 P2, home): her save (PersistenceService.save_using, as the game's save command calls it) and the
    # removal of a household object: destroy is called by sell_object, and by remove_created (an object the same
    # command just made, after a failed placement). Nothing else removes anything.
    "save_using", "destroy",
    # 2.40.0 (W13 P2 fix, CORE-6/HOME-2): the placement of an object (move_to, add_child, the game's create) and the
    # inventory's own removal and put-back. e2_actuator.py only.
    "create_object", "move_to", "add_child", "try_remove_object_by_id", "clear_previous_inventory",
    "player_try_add_object",
    # R3 (PROBE3-14): a guest added to an event's guest list (the event's own list, made by the actuator).
    "add_guest_info",
}
ACTUATOR_FILE = "e2_actuator.py"
# Pure E2 modules: no game imports at all.
PURE_FILES = {"e2_admission.py", "e2_lineage.py", "e2_registry.py", "e2_cards.py",
              "e2_trial.py", "writer.py", "schema.py", "snapshot.py", "cmdbox.py",
              "reach.py"}
FORBIDDEN_CALL_NAMES = FORBIDDEN_CALL_NAMES | (ACTUATOR_ONLY_CALLS - {"push_super_affordance"})
# 2.31.0 (W3p): clear_decay_rate_modifiers sets the list to None without recalculating, so the old rate stays
# in force; the probe removes its own modifier instead. Forbidden everywhere.
FORBIDDEN_CALL_NAMES = FORBIDDEN_CALL_NAMES | {"clear_decay_rate_modifiers"}


def _root(name):
    return name.split(".", 1)[0]


def scan_text(source, filename):
    findings = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return ["%s:%s syntax error: %s" % (filename, error.lineno, error.msg)]
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                root = _root(item.name)
                if root in FORBIDDEN_IMPORT_ROOTS:
                    findings.append("%s:%d forbidden import %s" % (filename, node.lineno, item.name))
                if root not in APPROVED_STDLIB_IMPORTS and root not in APPROVED_GAME_ROOTS:
                    findings.append("%s:%d unapproved import %s" % (filename, node.lineno, item.name))
                if (os.path.basename(filename).lower() in PURE_FILES and
                        root in APPROVED_GAME_ROOTS):
                    findings.append("%s:%d %s imports game module %s" %
                                    (filename, node.lineno,
                                     os.path.basename(filename).lower().rsplit(".", 1)[0],
                                     item.name))
                aliases[item.asname or root] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                continue
            root = _root(module)
            if root in FORBIDDEN_IMPORT_ROOTS:
                findings.append("%s:%d forbidden import %s" % (filename, node.lineno, module))
            narrow = NARROW_GAME_IMPORTS.get(module)
            if narrow is not None:
                names = {item.name for item in node.names}
                wrong_file = (module in E2_CONTROL_ONLY_MODULES and
                              os.path.basename(filename).lower() != ANSWER_ONLY_FILE)
                if (not names <= narrow or wrong_file or
                        os.path.basename(filename).lower() in PURE_FILES):
                    findings.append("%s:%d %s allows only %s" % (
                        filename, node.lineno, module, ", ".join(sorted(narrow))))
            elif root not in APPROVED_STDLIB_IMPORTS and root not in APPROVED_GAME_ROOTS:
                findings.append("%s:%d unapproved import %s" % (filename, node.lineno, module))
            if (os.path.basename(filename).lower() in PURE_FILES and
                    root in APPROVED_GAME_ROOTS):
                findings.append("%s:%d %s imports game module %s" %
                                (filename, node.lineno,
                                 os.path.basename(filename).lower().rsplit(".", 1)[0],
                                 module))
            for item in node.names:
                aliases[item.asname or item.name] = (module + "." + item.name).strip(".")
    # 2.27.0: nothing shipped may replace a game attribute, except the reviewed hold attributes of
    # E2_CONTROL_ASSIGNABLE, and only in e2_control.py.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            continue
        for target_node in (node.targets if isinstance(node, ast.Assign) else [node.target]):
            if not isinstance(target_node, ast.Attribute):
                continue
            resolved = _resolve_expr(target_node, aliases)
            if resolved is None:
                continue
            game = (_root(resolved) in APPROVED_GAME_ROOTS or
                    any(resolved.startswith(module + ".") for module in NARROW_GAME_IMPORTS))
            if game and not (resolved in E2_CONTROL_ASSIGNABLE and
                             os.path.basename(filename).lower() == ANSWER_ONLY_FILE):
                findings.append("%s:%d game attribute assigned %s" % (filename, node.lineno, resolved))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        resolved = _resolve_expr(node.value, aliases) if getattr(node, "value", None) is not None else None
        if resolved is None:
            continue
        for target_node in targets:
            if isinstance(target_node, ast.Name):
                aliases[target_node.id] = resolved
            elif isinstance(target_node, (ast.Tuple, ast.List)):
                for child in target_node.elts:
                    if isinstance(child, ast.Name):
                        aliases[child.id] = resolved
    def _scan_calls(node, stack):
        here = stack
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            here = stack + (node.name,)
        elif isinstance(node, ast.Lambda):
            here = stack + ("<lambda>",)
        if isinstance(node, ast.Call):
            target = _call_target(node.func)
            resolved_target = _resolve_expr(node.func, aliases) or target
            leaf = resolved_target.rsplit(".", 1)[-1] if resolved_target else ""
            is_actuator = os.path.basename(filename).lower() == ACTUATOR_FILE
            in_answer = (os.path.basename(filename).lower() == ANSWER_ONLY_FILE and
                         ANSWER_ONLY_FUNC in here and leaf in ANSWER_ONLY_CALLS)
            if in_answer or (leaf in ACTUATOR_ONLY_CALLS and is_actuator):
                pass
            elif leaf in FORBIDDEN_CALL_NAMES or leaf in ANSWER_ONLY_CALLS:
                findings.append("%s:%d forbidden call %s" % (
                    filename, node.lineno, resolved_target or leaf))
            if resolved_target in ("eval", "exec", "compile", "__import__"):
                findings.append("%s:%d dynamic execution %s" % (filename, node.lineno, resolved_target))
            if leaf in E2_CONTROL_ONLY_CALLS and os.path.basename(filename).lower() != ANSWER_ONLY_FILE:
                findings.append("%s:%d %s allowed only in %s" % (
                    filename, node.lineno, leaf, ANSWER_ONLY_FILE))
            # R3 (PROBE3-14): money is credited only by the actuator's own funds call (a funds object's add, whether
            # it is named or read from a household: funds_of(household).add, household.funds.add).
            if (leaf == "add" and isinstance(node.func, ast.Attribute) and not is_actuator and
                    _mentions(node.func.value, "funds")):
                findings.append("%s:%d funds credit allowed only in %s" % (filename, node.lineno, ACTUATOR_FILE))
            if leaf == "getattr" or leaf == "__import__":
                findings.append("%s:%d reflective dispatch" % (filename, node.lineno))
            if leaf == "open" and os.path.basename(filename).lower() != "writer.py":
                findings.append("%s:%d open outside writer" % (filename, node.lineno))
        for child in ast.iter_child_nodes(node):
            _scan_calls(child, here)

    _scan_calls(tree, ())
    return findings


def _mentions(node, word):
    """True when an expression names (a name or an attribute) something whose name contains word (R3, PROBE3-14)."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and word in child.id.lower():
            return True
        if isinstance(child, ast.Attribute) and word in child.attr.lower():
            return True
    return False


def _call_target(function):
    if isinstance(function, ast.Name):
        return function.id
    parts = []
    current = function
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    # 2.31.0 (W3p): a call on a call's result (services.game_clock_service()._sync...()) keeps its attribute
    # names, so a forbidden or e2_control-only name cannot hide behind a call in the chain.
    if isinstance(current, ast.Call) and parts:
        return ".".join(reversed(parts))
    return None


def _resolve_expr(expression, aliases):
    """Resolve imported and locally assigned call aliases conservatively."""
    target = _call_target(expression)
    if target is None:
        return None
    parts = target.split(".")
    seen = set()
    while parts and parts[0] in aliases and parts[0] not in seen:
        seen.add(parts[0])
        replacement = aliases[parts[0]].split(".")
        parts = replacement + parts[1:]
    return ".".join(parts)


def scan_tree(source_root):
    findings = []
    for root, _, names in os.walk(source_root):
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as handle:
                findings.extend(scan_text(handle.read(), path))
    return findings


def inspect_archive(path, expected_magic):
    findings = []
    required = {"ashley_e1/%s.pyc" % name for name in PRODUCTION_MODULES}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            missing = sorted(required - names)
            if missing:
                findings.append("missing members: %s" % ", ".join(missing))
            for name in names:
                if name.endswith(".py") or "__pycache__" in name or name.endswith(".pyo"):
                    findings.append("forbidden archive member: %s" % name)
                if name.endswith(".pyc") and archive.read(name)[:4] != expected_magic:
                    findings.append("wrong pyc magic: %s" % name)
    except (OSError, IOError, zipfile.BadZipFile) as error:
        findings.append("archive unreadable: %s" % error)
    return findings


def verify_artifact_manifest(path, manifest):
    expected = manifest.get("artifact", {}).get("sha256")
    with open(path, "rb") as handle:
        actual = hashlib.sha256(handle.read()).hexdigest().upper()
    return [] if expected == actual else ["artifact sha256 mismatch"]


if __name__ == "__main__":
    import sys
    # No argument used to scan nothing and exit 0; default to the shipped source.
    source = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
    errors = scan_tree(source)
    for error in errors:
        print(error)
    raise SystemExit(1 if errors else 0)
