from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]


class SkillRegistryTests(unittest.TestCase):
    def test_rum_instrument_is_registered_and_documented(self):
        manifest = json.loads((REPO / "skills-manifest.json").read_text(encoding="utf-8"))
        entries = {entry["name"]: entry for entry in manifest["skills"]}

        self.assertIn("rum-instrument", entries)
        self.assertEqual("rum-instrument", entries["rum-instrument"]["path"])
        self.assertTrue((REPO / entries["rum-instrument"]["path"] / "SKILL.md").is_file())
        self.assertIn("`rum-instrument`", (REPO / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
