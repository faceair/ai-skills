from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "rum-instrument"


class RumInstrumentPortabilityTests(unittest.TestCase):
    def test_installed_skill_tests_do_not_depend_on_repository_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "project" / ".agents" / "skills" / "rum-instrument"
            shutil.copytree(SKILL, installed)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(installed / "tests"),
                    "-v",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
