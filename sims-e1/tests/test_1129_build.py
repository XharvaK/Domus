"""2.41.5: the probe declares the game build it was checked against (1.129.39.1030, gameapi diff 2026-10-27)."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parent
BUILD = "1.129.39.1030"


class TargetBuildTests(unittest.TestCase):
    def test_source_and_vendored_schema_declare_1129(self):
        for path in (ROOT / "src/ashley_e1/schema.py", REPO / "helper/domus_helper/vendor/schema.py"):
            match = re.search(r'^SIMS_BUILD = "([^"]+)"$', path.read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(match, path)
            self.assertEqual(match.group(1), BUILD, path)

    def test_build_manifest_and_verify_pin_1129(self):
        build = (ROOT / "tools/build.ps1").read_text(encoding="utf-8")
        verify = (ROOT / "tools/verify.ps1").read_text(encoding="utf-8")
        self.assertIn('target_sims_build = "%s"' % BUILD, build)
        self.assertIn("manifest.get('target_sims_build') != '%s'" % BUILD, verify)
        self.assertNotIn("1.128.90.1030", build)
        self.assertNotIn("1.128.90.1030", verify)


if __name__ == "__main__":
    unittest.main()


class GameDllPinTests(unittest.TestCase):
    def test_build_pins_the_1129_signed_python_dll(self):
        """1.129.39.1030 ships python37_x64.dll re-signed by EA (Authenticode Valid, same file version
        3.7.150.1013, product 3.7.0); its sha256 is C6D05CA6...08D5 (read on XQX 2026-10-27)."""
        build = (ROOT / "tools/build.ps1").read_text(encoding="utf-8")
        self.assertIn('sha256 = "C6D05CA679D51B38BF9A7FB27B0C2FF2FF6F17BF072A47F2A63D013DA3D708D5"', build)
        self.assertNotIn("3BD2257D1A7C3D405D25F989CC0E3C847213700397C3F86D7B64AFB910069AEC", build)
        self.assertIn('file_version_raw = "3.7.150.1013"', build)
