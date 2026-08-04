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
        self.assertIn(
            "temporaryAuthCode: <paste for one-prompt implementation or provide after plan review>",
            skill,
        )
        self.assertIn("prompt:provided", skill)
        self.assertIn(
            "Do not consume the code until the plan has passed plan-phase validation",
            skill,
        )
        self.assertIn(
            "Only `temporary_authorization_code`/`temporaryAuthCode` may use",
            self.read("references/contracts.md"),
        )

    def test_skill_uses_intent_aware_authorization(self):
        skill = self.read("SKILL.md")
        execution = self.read("references/execution.md")
        contracts = self.read("references/contracts.md")

        self.assertIn("Create and authorize the plan", skill)
        self.assertIn("continue directly to step 7 in the same run", skill)
        self.assertIn("Do not ask for an `approvalMode` field", skill)
        self.assertIn('"status": "pending"', contracts)
        self.assertIn('"basis": "plan_only_request"', contracts)
        self.assertIn('"basis": "explicit_implementation_request"', contracts)
        self.assertIn('"revision": 1', contracts)
        self.assertIn("Explicit implementation intent is not blanket approval", execution)
        self.assertIn("basis: revision_review", execution)
        self.assertIn("reviewed_plan_sha256", contracts)
        self.assertIn("--print-review-digest", contracts)
        self.assertIn("reviewed_overlaps", contracts)
        self.assertIn("existing_instrumentation.signals", contracts)
        self.assertIn("profile.signals", contracts)
        self.assertIn("validator derives material review reasons", contracts.lower())

    def test_all_official_rum_application_families_have_adapters(self):
        skill = self.read("SKILL.md")
        adapters = {
            "Web": "web.md",
            "MiniApp": "miniapp.md",
            "Android": "android.md",
            "iOS": "apple.md",
            "macOS": "macos.md",
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

        self.assertIn("never echo, inspect, or persist its value", skill)
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
        self.assertIn("temporary-auth-code-stdin", helper)
        self.assertIn("getpass.getpass", helper)
        self.assertIn("--site-only", skill)
        self.assertIn("application lookup requires --client-token-env-file", helper)
        self.assertIn("application lookup requires --state-file", helper)
        self.assertIn("application lookup requires --plan-digest", helper)
        self.assertIn("--allow-external-secret-sink", helper)
        self.assertIn(
            "removes the new secret sink if state persistence fails",
            skill,
        )
        self.assertIn("credential-free HTTP reachability checks", skill)
        self.assertIn("never poll for them", skill)
        self.assertNotIn("OWL_REGISTRY_ENDPOINT", helper)
        self.assertIn("use `OWL_REGISTRY_ENDPOINT`", control_plane)

    def test_testing_site_is_built_in_and_not_a_standard_prompt_field(self):
        skill = self.read("SKILL.md")
        control_plane = self.read("references/control-plane.md")
        validator = self.read("scripts/validate_contract.py")

        for value in (
            "--insecure-test-tls",
            "builtin_testing",
            "https://testing-ft2x-ai-api.dataflux.cn",
            "test_only",
        ):
            with self.subTest(value=value):
                self.assertIn(value, skill + control_plane + validator)
        for removed in ("--test-site-catalog-file", "testing_override"):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, skill + control_plane + validator)

        minimal_contract = skill.split("## Minimal input contract", 1)[1].split(
            "## Workflow",
            1,
        )[0]
        self.assertNotIn("aiApiEndpoint:", minimal_contract)
        self.assertNotIn("clientToken:", minimal_contract)
        self.assertNotIn("evals/files", skill + control_plane)

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

    def test_optional_capabilities_are_repository_or_user_driven(self):
        skill = self.read("SKILL.md")
        common = self.read("references/common.md")

        self.assertIn(
            "only when the repository already uses them or the user requests them",
            skill,
        )
        self.assertIn("Core RUM is the default planning scope", common)
        self.assertIn("omit irrelevant sections", common)

    def test_macos_and_cpp_receiver_boundaries_are_explicit(self):
        macos = self.read("references/macos.md")
        cpp = self.read("references/cpp.md")
        validator = self.read("scripts/validate_contract.py")
        common = self.read("references/common.md")

        for value in ("datakit-macos", "FTMacOSSDK", "main.swift", "custom"):
            with self.subTest(value=value):
                self.assertIn(value, macos)
        for value in ("setServerUrl", "setRumAppId", "only DataKit"):
            with self.subTest(value=value):
                self.assertIn(value, cpp + validator)
        self.assertIn("block Public DataWay plans", common)

    def test_evals_have_repository_fixtures_and_platform_edge_cases(self):
        import json

        evals = json.loads(self.read("evals/evals.json"))["evals"]
        self.assertTrue(all(case["files"] for case in evals))
        for case in evals:
            for relative in case["files"]:
                with self.subTest(case=case["id"], relative=relative):
                    self.assertTrue((SKILL_DIR / relative).is_file())
        prompts = "\n".join(case["prompt"] for case in evals)
        for family in (
            "Android",
            "iOS",
            "tvOS",
            "macOS",
            "HarmonyOS",
            "React Native",
            "Flutter",
            "UniApp",
            "C++",
            "Unity",
            "小程序",
        ):
            with self.subTest(family=family):
                self.assertIn(family, prompts)
        self.assertIn("规划并实施", prompts)
        self.assertTrue(
            any(
                "explicit_implementation_request" in expectation
                for case in evals
                for expectation in case["expectations"]
            )
        )

    def test_contract_covers_datakit_readiness_and_type_verification(self):
        contracts = self.read("references/contracts.md")
        validator = self.read("scripts/validate_contract.py")

        for value in (
            "rum_collector",
            "network_reachability",
            "verification",
            "api_value",
            "not_applicable",
        ):
            with self.subTest(value=value):
                self.assertIn(value, contracts + validator)

if __name__ == "__main__":
    unittest.main()
