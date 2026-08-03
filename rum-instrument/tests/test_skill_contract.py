from __future__ import annotations

from pathlib import Path
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (SKILL_DIR / relative).read_text(encoding="utf-8")

    def test_skill_uses_minimal_connection_input(self):
        skill = self.read("SKILL.md")

        for field in (
            "datawayUrl",
            "temporaryAuthCode",
            "datakitUrl",
            "appId",
            "template:NAME",
        ):
            with self.subTest(field=field):
                self.assertIn(field, skill)

        self.assertIn("Do not require a separate config file", skill)
        self.assertIn("Do not fan one scalar ID out", skill)
        self.assertIn("Do not put `clientToken` or `aiApiEndpoint` in the standard prompt", skill)

    def test_skill_requires_plan_revision_approval(self):
        skill = self.read("SKILL.md")
        execution = self.read("references/execution.md")
        contracts = self.read("references/contracts.md")

        self.assertIn("Create the plan and stop", skill)
        self.assertIn("approval covers only that revision", skill.lower())
        self.assertIn('"status": "pending"', contracts)
        self.assertIn('"revision": 1', contracts)
        self.assertIn("Revise and reapprove", execution)

    def test_all_official_rum_application_families_have_adapters(self):
        skill = self.read("SKILL.md")
        adapters = {
            "Web": "web.md",
            "MiniApp": "miniapp.md",
            "Android": "android.md",
            "iOS": "apple.md",
            "HarmonyOS": "harmonyos.md",
            "React Native": "react-native.md",
            "Flutter": "flutter.md",
            "UniApp": "uniapp.md",
            "C++": "cpp.md",
            "Unity": "unity.md",
        }

        for family, filename in adapters.items():
            with self.subTest(family=family):
                self.assertIn(family, skill)
                self.assertIn(f"references/{filename}", skill)
                self.assertTrue((SKILL_DIR / "references" / filename).is_file())

    def test_skill_keeps_token_values_and_remote_actions_out_of_plan(self):
        skill = self.read("SKILL.md")
        privacy = self.read("references/privacy-security.md")
        contracts = self.read("references/contracts.md")

        self.assertIn("never request, read, echo, or persist its value", skill)
        self.assertIn("uploaded only after explicit authorization", privacy)
        self.assertNotIn('"client_token": "<', contracts)
        self.assertIn('"remote_verification"', contracts)
        self.assertIn('"verified": false', contracts)

    def test_public_dataway_uses_catalog_and_ai_api_helper(self):
        skill = self.read("SKILL.md")
        control_plane = self.read("references/control-plane.md")
        helper = self.read("scripts/resolve_rum_application.py")

        for value in (
            "https://urls.guance.com/",
            "https://urls.truewatch.com/",
            "/api/v1/account/accesskey/exchange",
            "/api/v1/rum/app/get",
        ):
            with self.subTest(value=value):
                self.assertIn(value, control_plane + helper)

        self.assertIn("api_key_persistence", helper)
        self.assertIn("memory_only", helper)
        self.assertIn("temporary-auth-code-env", helper)
        self.assertNotIn("OWL_REGISTRY_ENDPOINT", helper)
        self.assertIn("use `OWL_REGISTRY_ENDPOINT`", control_plane)

    def test_test_site_override_is_explicit_and_not_a_standard_prompt_field(self):
        skill = self.read("SKILL.md")
        control_plane = self.read("references/control-plane.md")
        validator = self.read("scripts/validate_contract.py")

        for value in (
            "--test-site-catalog-file",
            "--insecure-test-tls",
            "testing_override",
            "test_only",
        ):
            with self.subTest(value=value):
                self.assertIn(value, skill + control_plane + validator)

        minimal_contract = skill.split("## Minimal input contract", 1)[1].split(
            "## Workflow",
            1,
        )[0]
        self.assertNotIn("aiApiEndpoint:", minimal_contract)
        self.assertNotIn("clientToken:", minimal_contract)

    def test_headless_receiver_mode_is_absent(self):
        paths = [
            "SKILL.md",
            "references/common.md",
            "references/contracts.md",
            "references/web.md",
            "references/miniapp.md",
            "evals/evals.json",
        ]

        for relative in paths:
            with self.subTest(relative=relative):
                self.assertNotIn("headless", self.read(relative).lower())

    def test_progressive_disclosure_and_metadata(self):
        skill_lines = self.read("SKILL.md").splitlines()
        agent = self.read("agents/openai.yaml")

        self.assertLess(len(skill_lines), 500)
        self.assertIn('display_name: "Guance RUM Instrumentation"', agent)
        self.assertIn("$rum-instrument", agent)

if __name__ == "__main__":
    unittest.main()
