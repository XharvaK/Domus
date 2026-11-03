"""OPENVULN 2026-11-03 (Domus, probe side): one regression test per finding."""
import json
import os
import time
import unittest

from test_2330_inbox_order import InboxOrderTests, envelope

KEY = bytes(range(32))


class OpenVulnInboxTests(InboxOrderTests):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.root, "cmd", "key"), "w", encoding="ascii") as handle:
            handle.write(KEY.hex())
        self.events = lambda: [row["e2"] for row in self.probe._WRITER.rows if row.get("event_kind") == "command_event"]

    def signed(self, body, key=KEY):
        body = dict(body)
        body["mac"] = self.probe.cmdbox.mac(key, body)
        return body

    def fresh(self, command_id, issuer="helper"):
        now = int(time.time() * 1000)
        body = envelope(command_id, now - 10, now + 20_000)
        body["issuer"] = issuer
        return body

    def only_reply(self):
        folder = os.path.join(self.root, "cmd", "outbox")
        names = os.listdir(folder)
        self.assertEqual(len(names), 1, names)
        with open(os.path.join(folder, names[0]), "rb") as handle:
            return json.loads(handle.read())

    def reply_of(self, command_id):
        with open(os.path.join(self.root, "cmd", "outbox", command_id + ".json"), "rb") as handle:
            return json.loads(handle.read())

    # F1: issuer attribution is only believed for a command carrying a valid MAC under the shared key.
    def test_f1_an_unsigned_command_is_refused_and_its_issuer_is_not_attributed(self):
        self.drop("forged", self.fresh("1" * 32, issuer="console"), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        reply = self.only_reply()
        self.assertEqual((reply["status"], reply["code"], reply["issuer"]), ("REJECTED", "BAD_MAC", None))
        self.assertEqual(self.events(), [])

    def test_f1_a_command_signed_with_another_key_is_refused(self):
        self.drop("forged", self.signed(self.fresh("2" * 32), key=bytes(32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        self.assertEqual(self.only_reply()["code"], "BAD_MAC")

    def test_f1_a_signed_command_runs_and_is_attributed(self):
        self.drop("good", self.signed(self.fresh("3" * 32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["3" * 32])
        self.assertEqual([event["issuer"] for event in self.events()], ["helper"])

    def test_f1_without_a_key_file_nothing_runs(self):
        os.remove(os.path.join(self.root, "cmd", "key"))
        self.drop("good", self.signed(self.fresh("4" * 32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        self.assertEqual(self.only_reply()["code"], "BAD_MAC")


    # F8: the probe signs its reply under the same key, so the helper can tell it from a forged one.
    def test_f8_the_reply_carries_a_valid_mac(self):
        self.drop("good", self.signed(self.fresh("5" * 32)))
        self.probe._inbox_tick_body()
        reply = self.reply_of("5" * 32)
        self.assertTrue(self.probe.cmdbox.mac_ok(KEY, reply), reply)


    # F3: a second envelope naming a used id never overwrites that id's reply slot, signed or not.
    def test_f3_an_unsigned_same_id_envelope_leaves_the_real_reply_alone(self):
        self.drop("real", self.signed(self.fresh("6" * 32)))
        self.probe._inbox_tick_body()
        first = self.reply_of("6" * 32)
        self.assertEqual(first["status"], "OK")
        self.drop("dup", self.fresh("6" * 32), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.reply_of("6" * 32), first)

    def test_f3_a_replayed_signed_envelope_leaves_the_real_reply_alone(self):
        body = self.signed(self.fresh("7" * 32))
        self.drop("real", body)
        self.probe._inbox_tick_body()
        first = self.reply_of("7" * 32)
        self.drop("again", body)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["7" * 32])
        self.assertEqual(self.reply_of("7" * 32), first)


    # F2: entries the pump cannot take never hold the four places of a tick forever.
    def plant_untakeable(self, count=6):
        inbox = os.path.join(self.root, "cmd", "inbox")
        for index in range(count):
            name = "wedge%d.json" % index
            with open(os.path.join(inbox, name), "w", encoding="utf-8") as handle:
                json.dump({"issued_at_ms": 0}, handle)
            blocker = os.path.join(inbox, name + ".taken")
            os.makedirs(os.path.join(blocker, "full"))

    def test_f2_untakeable_files_do_not_wedge_the_pump(self):
        self.plant_untakeable()
        self.drop("good", self.signed(self.fresh("8" * 32)))
        for _ in range(3):
            self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["8" * 32])

    def test_f2_folders_named_like_commands_are_not_taken(self):
        inbox = os.path.join(self.root, "cmd", "inbox")
        for index in range(6):
            os.makedirs(os.path.join(inbox, "dir%d.json" % index, "x"))
            os.makedirs(os.path.join(inbox, "dir%d.json.taken" % index, "x"))
        self.drop("good", self.signed(self.fresh("9" * 32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["9" * 32])

    # AU NB-3: the probe pins cmd/key at its first good read; a later swap of the file (a cmd/ writer) is not believed.
    def swap_key(self, new):
        path = os.path.join(self.root, "cmd", "key")
        os.replace(path, path + ".old")
        with open(path, "w", encoding="ascii") as handle:
            handle.write(new.hex())

    def test_au_nb3_a_swapped_key_does_not_let_a_cmd_writer_forge(self):
        self.drop("good", self.signed(self.fresh("c" * 32)), sign=False)
        self.probe._inbox_tick_body()
        evil = bytes([7]) * 32
        self.swap_key(evil)
        self.drop("forged", self.signed(self.fresh("b" * 32, issuer="console"), key=evil), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["c" * 32])
        self.assertEqual([event["issuer"] for event in self.events()], ["helper"])

    def test_au_nb3_the_pinned_key_still_works_after_a_swap(self):
        self.drop("good", self.signed(self.fresh("c" * 32)), sign=False)
        self.probe._inbox_tick_body()
        self.swap_key(bytes([7]) * 32)
        self.drop("good2", self.signed(self.fresh("d" * 32)), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["c" * 32, "d" * 32])

    def test_au_nb3_a_key_made_after_start_is_pinned_when_first_read(self):
        os.remove(os.path.join(self.root, "cmd", "key"))
        self.probe._inbox_tick_body()
        with open(os.path.join(self.root, "cmd", "key"), "w", encoding="ascii") as handle:
            handle.write(KEY.hex())
        self.drop("good", self.signed(self.fresh("e" * 32)), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["e" * 32])

    def test_au_nb3_a_linked_key_is_not_read(self):
        path = os.path.join(self.root, "cmd", "key")
        os.replace(path, path + ".real")
        try:
            os.symlink(path + ".real", path)
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        self.drop("good", self.signed(self.fresh("f" * 32)), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])

    # AU NB-4: many untakeable entries (more than a scan) must not hold the pump.
    def test_au_nb4_256_untakeable_entries_do_not_wedge_the_pump(self):
        self.plant_untakeable(count=256)
        self.drop("good", self.signed(self.fresh("a" * 32)), sign=False)
        for _ in range(2):
            self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["a" * 32])

    def test_au_nb4_still_dispatched_after_the_stuck_wait_expires(self):
        self.plant_untakeable(count=256)
        for _ in range(61):
            self.probe._inbox_tick_body()
        self.drop("good", self.signed(self.fresh("a" * 32)), sign=False)
        for _ in range(2):
            self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["a" * 32])


del InboxOrderTests

if __name__ == "__main__":
    unittest.main()
