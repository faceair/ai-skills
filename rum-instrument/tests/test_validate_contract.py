from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_contract", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_plan():
    return {
        "schema_version": 1,
        "repository": {
            "root": ".",
            "commit": "abc123",
            "initial_status": [],
            "analysis_fingerprint": "fingerprint",
        },
        "request": {
            "intent": "plan",
            "application_id_input": {
                "kind": "scalar",
                "reference": {"source": "template:APP_ID"},
            },
            "receiver": {
                "mode": "public_dataway",
                "endpoint": {"source": "template:DATAWAY_URL"},
                "client_tokens": {
                    "web": {"source": "runtime:GUANCE_RUM_CLIENT_TOKEN"}
                },
                "control_plane": {
                    "status": "resolved",
                    "catalog": "https://urls.guance.com/",
                    "site_code": "cn3",
                    "ai_api_endpoint": {"value": "https://cn3-ai-api.guance.com"},
                    "exchange_path": "/api/v1/account/accesskey/exchange",
                    "application_lookup_path": "/api/v1/rum/app/get",
                    "temporary_authorization_code": {
                        "source": "env:GUANCE_TEMP_AUTH_CODE"
                    },
                    "api_key_persistence": "memory_only",
                },
            },
        },
        "targets": [
            {
                "id": "web:.",
                "path": ".",
                "platform": "web",
                "variants": ["browser"],
                "evidence": ["package.json"],
                "application_id_slots": ["web"],
                "application_ids": {"web": {"source": "template:APP_ID"}},
                "application_types": {
                    "web": {
                        "value": "web",
                        "source": "ai_api",
                        "confidence": "high",
                    }
                },
                "existing_instrumentation": {},
                "profile": {},
                "receiver_mapping": {},
                "privacy": {},
                "artifacts": {},
                "official_sources": ["https://docs.guance.com/real-user-monitoring/web/app-access/"],
                "disposition": "planned",
                "blockers": [],
            }
        ],
        "planned_changes": [
            {
                "target_id": "web:.",
                "file": "src/rum.ts",
                "order": 1,
                "purpose": "Configure Browser RUM once",
                "edits": ["Add the approved Browser RUM initializer"],
                "dependency_decision": {"action": "preserve"},
                "validation": ["npm test"],
                "risk": "The initializer could run too late",
                "rollback": "Revert src/rum.ts",
            }
        ],
        "validation": [],
        "risks": [],
        "handoff": [],
        "approval": {"status": "pending", "revision": 1},
    }


class ValidateContractTests(unittest.TestCase):
    def test_accepts_minimal_public_dataway_plan(self):
        errors, warnings = VALIDATOR.validate_plan(valid_plan(), "plan")

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_accepts_explicit_test_catalog_and_tls_exception(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "testing_override",
                "catalog_source": {
                    "source": "existing:user-provided-testing-catalog"
                },
                "site_code": "testing",
                "ai_api_endpoint": {
                    "value": "https://testing-ft2x-ai-api.dataflux.cn"
                },
                "test_only": True,
                "tls_verification": "disabled_for_testing",
            }
        )

        errors, warnings = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_rejects_tls_exception_for_an_official_catalog(self):
        plan = valid_plan()
        plan["request"]["receiver"]["control_plane"][
            "tls_verification"
        ] = "disabled_for_testing"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("must remain verified for official catalogs" in error for error in errors)
        )

    def test_test_catalog_requires_explicit_test_only_source(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane["catalog"] = "testing_override"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any(".test_only must be true" in error for error in errors))
        self.assertTrue(any(".catalog_source must be an object" in error for error in errors))

    def test_rejects_non_https_ai_api_even_for_test_catalog(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "testing_override",
                "catalog_source": {
                    "source": "existing:user-provided-testing-catalog"
                },
                "test_only": True,
                "tls_verification": "disabled_for_testing",
                "ai_api_endpoint": {
                    "value": "http://testing-ft2x-ai-api.dataflux.cn"
                },
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("must be an HTTPS origin" in error for error in errors))

    def test_requires_approved_revision_for_implementation(self):
        errors, _ = VALIDATOR.validate_plan(valid_plan(), "implement")

        self.assertIn("implementation requires approval.status=approved", errors)

        plan = valid_plan()
        plan["approval"]["status"] = "approved"
        errors, _ = VALIDATOR.validate_plan(plan, "implement")
        self.assertEqual([], errors)

    def test_rejects_empty_changes_for_a_planned_target(self):
        plan = valid_plan()
        plan["planned_changes"] = []

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("planned_changes must not be empty" in error for error in errors))

    def test_rejects_incomplete_or_unmatched_planned_changes(self):
        plan = valid_plan()
        plan["planned_changes"] = [
            {
                "target_id": "web:missing",
                "file": "dist/rum.js",
                "order": 0,
                "purpose": "",
                "edits": [],
                "dependency_decision": {},
                "validation": [],
                "risk": "",
                "rollback": "",
            }
        ]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("unknown target_id" in error for error in errors))
        self.assertTrue(any("generated or dependency directory" in error for error in errors))
        self.assertTrue(any(".order must be a positive integer" in error for error in errors))
        self.assertTrue(any(".edits must be a non-empty array" in error for error in errors))
        self.assertTrue(any(".dependency_decision.action" in error for error in errors))
        self.assertTrue(any("has no planned change" in error for error in errors))

    def test_rejects_client_token_value(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"] = {
            "value": "must-not-be-persisted"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("client_token" in error for error in errors))
        self.assertTrue(any("never contain a value" in error for error in errors))

    def test_rejects_user_supplied_client_token_template(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"] = {
            "source": "template:CLIENT_TOKEN"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("control-plane flow" in error for error in errors))

    def test_rejects_temporary_authorization_code_value_without_echoing_it(self):
        plan = valid_plan()
        secret = "synthetic-temporary-code"
        plan["request"]["receiver"]["control_plane"]["temporary_authorization_code"] = {
            "value": secret
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        rendered = "\n".join(errors)

        self.assertIn("temporary_authorization_code", rendered)
        self.assertNotIn(secret, rendered)

    def test_requires_resolved_public_dataway_control_plane_contract(self):
        plan = valid_plan()
        del plan["request"]["receiver"]["control_plane"]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("control_plane must be an object" in error for error in errors))

    def test_rejects_nested_sensitive_values_without_echoing_them(self):
        plan = valid_plan()
        secret = "synthetic-secret-for-validator-test"
        plan["targets"][0]["receiver_mapping"] = {
            "clientToken": {"value": secret},
            "headers": {"Authorization": f"Bearer {secret}"},
        }
        plan["handoff"] = [{"cookie": secret}]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        rendered = "\n".join(errors)

        self.assertIn("targets[0].receiver_mapping.clientToken", rendered)
        self.assertIn("targets[0].receiver_mapping.headers.Authorization", rendered)
        self.assertIn("handoff[0].cookie", rendered)
        self.assertNotIn(secret, rendered)

    def test_accepts_nested_sensitive_source_references(self):
        plan = valid_plan()
        plan["targets"][0]["receiver_mapping"] = {
            "clientToken": {
                "input": "runtime:GUANCE_RUM_CLIENT_TOKEN",
                "runtime": "runtime:DEPLOYCONFIG.rumClientToken",
                "persistence": "deployment only",
            },
            "headers": {"Authorization": "runtime:RUM_AUTHORIZATION"},
        }
        plan["targets"][0]["privacy"] = {
            "cookies": "disabled",
            "requestBody": "not_collected",
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_rejects_persisted_request_or_response_bodies(self):
        plan = valid_plan()
        plan["handoff"] = [{"requestBody": {"source": "runtime:PAYLOAD"}}]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("handoff[0].requestBody must not be persisted" in error for error in errors))

    def test_rejects_conflicting_raw_prompt_fields(self):
        plan = valid_plan()
        plan["request"]["receiver"]["datakitUrl"] = {"source": "template:DATAKIT_URL"}

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("raw prompt fields" in error for error in errors))

    def test_missing_platform_id_is_allowed_only_when_blocked(self):
        plan = valid_plan()
        plan["request"]["application_id_input"] = {
            "kind": "map",
            "references": {
                "android": {"source": "template:ANDROID_APP_ID"},
                "ios": {"source": "template:IOS_APP_ID"},
            },
        }
        target = plan["targets"][0]
        target["platform"] = "flutter"
        target["application_id_slots"] = ["android", "ios"]
        target["application_ids"] = {"android": {"source": "template:ANDROID_APP_ID"}}
        target["application_types"] = {
            "android": {
                "value": "android",
                "source": "ai_api",
                "confidence": "high",
            },
            "ios": {
                "value": "ios",
                "source": "ai_api",
                "confidence": "high",
            },
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(any("missing slot ios" in error for error in errors))

        target["disposition"] = "blocked"
        target["blockers"] = ["Missing Application ID slot: ios"]
        plan["planned_changes"] = []
        errors, warnings = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)
        self.assertTrue(any("slot ios" in warning for warning in warnings))

    def test_datakit_omits_client_token(self):
        plan = valid_plan()
        plan["request"]["receiver"] = {
            "mode": "datakit",
            "endpoint": {"source": "template:DATAKIT_URL"},
        }
        plan["targets"][0]["application_types"]["web"]["source"] = "repository"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_rejects_removed_headless_mode(self):
        plan = valid_plan()
        plan["request"]["receiver"] = {
            "mode": "headless",
            "endpoint": {"source": "template:HEADLESS_URL"},
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("headless is no longer supported" in error for error in errors))

    def test_datakit_rejects_public_control_plane_fields(self):
        plan = valid_plan()
        plan["request"]["receiver"]["mode"] = "datakit"
        plan["request"]["receiver"].pop("client_tokens")

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("control_plane is valid only" in error for error in errors))

    def test_requires_application_type_value_and_source(self):
        plan = valid_plan()
        plan["targets"][0]["application_types"]["web"] = {
            "value": "flutter",
            "source": "guess",
            "confidence": "certain",
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("supported RUM application type" in error for error in errors))
        self.assertTrue(any("source must be user, ai_api, or repository" in error for error in errors))
        self.assertTrue(any("confidence must be high, medium, or low" in error for error in errors))

    def test_rejects_reused_application_id_reference(self):
        plan = valid_plan()
        plan["request"]["application_id_input"] = {
            "kind": "map",
            "references": {
                "android": {"source": "template:APP_ID"},
                "ios": {"source": "template:IOS_APP_ID"},
            },
        }
        target = plan["targets"][0]
        target["platform"] = "flutter"
        target["application_id_slots"] = ["android", "ios"]
        target["application_ids"] = {
            "android": {"source": "template:APP_ID"},
            "ios": {"source": "template:APP_ID"},
        }
        target["application_types"] = {
            "android": {
                "value": "android",
                "source": "ai_api",
                "confidence": "high",
            },
            "ios": {
                "value": "ios",
                "source": "ai_api",
                "confidence": "high",
            },
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("reuses the Application ID reference" in error for error in errors))

    def test_rejects_assigning_a_scalar_id_when_multiple_slots_are_unresolved(self):
        plan = valid_plan()
        first = plan["targets"][0]
        first["id"] = "web:apps/admin"
        first["path"] = "apps/admin"
        plan["planned_changes"][0]["target_id"] = first["id"]
        plan["planned_changes"][0]["file"] = "apps/admin/src/main.jsx"

        second = copy.deepcopy(first)
        second["id"] = "web:apps/portal"
        second["path"] = "apps/portal"
        second["application_ids"] = {}
        second["disposition"] = "blocked"
        second["blockers"] = ["Missing Application ID slot: web"]
        plan["targets"].append(second)

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("scalar is ambiguous" in error for error in errors))

    def test_accepts_unassigned_scalar_when_all_ambiguous_slots_are_blocked(self):
        plan = valid_plan()
        first = plan["targets"][0]
        first["id"] = "web:apps/admin"
        first["path"] = "apps/admin"
        first["application_ids"] = {}
        first["disposition"] = "blocked"
        first["blockers"] = ["Missing Application ID slot: web; scalar input is ambiguous"]

        second = copy.deepcopy(first)
        second["id"] = "web:apps/portal"
        second["path"] = "apps/portal"
        plan["targets"].append(second)
        plan["planned_changes"] = []

        errors, warnings = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)
        self.assertTrue(any("scalar Application ID input remains unassigned" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
