from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import stat
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_rum_application.py"
SPEC = importlib.util.spec_from_file_location("resolve_rum_application", SCRIPT)
assert SPEC and SPEC.loader
RESOLVER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RESOLVER
SPEC.loader.exec_module(RESOLVER)


GUANCE_CATALOG = {
    "urls": {
        "default": {
            "openway": "https://openway.guance.com",
            "ai_api": "https://ai-api.guance.com/",
        },
        "cn3": {
            "openway": "https://cn3-openway.guance.com",
            "ai_api": "https://cn3-ai-api.guance.com/",
        },
    }
}
TRUEWATCH_CATALOG = {
    "urls": {
        "us1": {
            "openway": "https://us1-openway.truewatch.com",
            "ai_api": "https://us1-ai-api.truewatch.com",
        }
    }
}


def catalog_fetcher(url: str):
    if url == "https://urls.guance.com/":
        return GUANCE_CATALOG
    if url == "https://urls.truewatch.com/":
        return TRUEWATCH_CATALOG
    raise AssertionError(url)


class ResolveRumApplicationTests(unittest.TestCase):
    def test_resolves_guance_and_truewatch_from_official_catalog_entries(self):
        guance = RESOLVER.resolve_site(
            "https://cn3-openway.guance.com/",
            catalog_fetcher=catalog_fetcher,
        )
        truewatch = RESOLVER.resolve_site(
            "https://us1-openway.truewatch.com",
            catalog_fetcher=catalog_fetcher,
        )

        self.assertEqual(("guance", "cn3"), (guance.brand, guance.code))
        self.assertEqual("https://cn3-ai-api.guance.com", guance.ai_api_url)
        self.assertEqual("official", guance.catalog_kind)
        self.assertEqual("verified", guance.tls_verification)
        self.assertEqual(("truewatch", "us1"), (truewatch.brand, truewatch.code))
        self.assertEqual("https://us1-ai-api.truewatch.com", truewatch.ai_api_url)

    def test_resolves_exact_match_from_explicit_test_catalog_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "testing-sites.json"
            catalog.write_text(
                json.dumps(
                    {
                        "urls": {
                            "testing": {
                                "openway": "http://testing-openway.dataflux.cn",
                                "ai_api": "https://testing-ft2x-ai-api.dataflux.cn",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            site = RESOLVER.resolve_test_site(
                "http://testing-openway.dataflux.cn",
                catalog,
                insecure_test_tls=True,
            )

        self.assertEqual(("testing", "testing"), (site.brand, site.code))
        self.assertEqual("testing_override", site.catalog_kind)
        self.assertEqual("disabled_for_testing", site.tls_verification)
        self.assertEqual(
            "https://testing-ft2x-ai-api.dataflux.cn",
            site.ai_api_url,
        )

    def test_insecure_tls_requires_explicit_test_catalog_override(self):
        self.assertIsNone(
            RESOLVER.build_ai_api_tls_context(
                insecure_test_tls=False,
                testing_override=False,
            )
        )
        with self.assertRaisesRegex(
            RESOLVER.ResolutionError,
            "--test-site-catalog-file",
        ):
            RESOLVER.build_ai_api_tls_context(
                insecure_test_tls=True,
                testing_override=False,
            )

        context = RESOLVER.build_ai_api_tls_context(
            insecure_test_tls=True,
            testing_override=True,
        )
        self.assertIsNotNone(context)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)

    def test_resolves_documented_default_rum_openway_alias(self):
        site = RESOLVER.resolve_site(
            "https://rum-openway.guance.com",
            catalog_fetcher=catalog_fetcher,
        )

        self.assertEqual("default", site.code)
        self.assertEqual("https://ai-api.guance.com", site.ai_api_url)

    def test_rejects_unknown_dataway_without_guessing_an_ai_api_endpoint(self):
        with self.assertRaisesRegex(
            RESOLVER.ResolutionError,
            "catalogs checked: https://urls.guance.com/, https://urls.truewatch.com/",
        ):
            RESOLVER.resolve_site(
                "https://private-openway.example.com",
                catalog_fetcher=catalog_fetcher,
            )

    def test_rejects_slot_names_that_could_inject_output(self):
        with self.assertRaisesRegex(RESOLVER.ResolutionError, "assignments"):
            RESOLVER.parse_slot_assignments(
                ["web\nforged=app"],
                "appId",
            )

    def test_exchange_and_lookup_keep_api_key_and_client_token_out_of_metadata(self):
        site = RESOLVER.Site(
            brand="guance",
            code="cn3",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://cn3-openway.guance.com",
            ai_api_url="https://cn3-ai-api.guance.com",
        )
        calls = []

        def poster(url, body, headers, operation):
            calls.append((url, body, headers, operation))
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {
                    "success": True,
                    "data": {"item": {"sk": "synthetic-api-key"}},
                }
            return {
                "success": True,
                "data": {
                    "item": {
                        "app_id": "web_demo",
                        "name": "Web Demo",
                        "app_type": "web",
                        "client_token": "synthetic-client-token",
                    }
                },
            }

        metadata, client_token = RESOLVER.resolve_application(
            site,
            "web_demo",
            "synthetic-temporary-code",
            json_poster=poster,
        )
        rendered = str(metadata)

        self.assertEqual("synthetic-client-token", client_token)
        self.assertNotIn("synthetic-api-key", rendered)
        self.assertNotIn("synthetic-client-token", rendered)
        self.assertNotIn("synthetic-temporary-code", rendered)
        self.assertEqual(
            {"DF-API-KEY": "synthetic-api-key"},
            calls[1][2],
        )
        self.assertEqual("ai_api", metadata["application"]["selected_app_type_source"])

    def test_user_application_type_wins_and_mismatch_is_reported(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://rum-openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )

        def poster(url, body, headers, operation):
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            return {
                "success": True,
                "data": {
                    "item": {
                        "app_type": "web",
                        "client_token": "client-token",
                    }
                },
            }

        metadata, _ = RESOLVER.resolve_application(
            site,
            "app",
            "temp-code",
            user_application_type="custom",
            json_poster=poster,
        )

        self.assertEqual("custom", metadata["application"]["selected_app_type"])
        self.assertEqual("user", metadata["application"]["selected_app_type_source"])
        self.assertTrue(metadata["application"]["type_mismatch"])

    def test_secret_env_file_is_mode_600_and_safe_result_contains_only_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rum-client-token.env"
            written = RESOLVER.write_client_token_env(
                output,
                "GUANCE_RUM_CLIENT_TOKEN",
                "synthetic-client-token",
            )
            result = RESOLVER.build_safe_result(
                {"application": {"app_id": "demo"}},
                client_token_environments={
                    "default": "GUANCE_RUM_CLIENT_TOKEN"
                },
                secret_file=written,
            )

            self.assertEqual(
                "GUANCE_RUM_CLIENT_TOKEN=synthetic-client-token\n",
                output.read_text(encoding="utf-8"),
            )
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))
            self.assertNotIn("synthetic-client-token", str(result))
            self.assertEqual(
                "runtime:GUANCE_RUM_CLIENT_TOKEN",
                result["client_tokens"]["default"]["source"],
            )

    def test_multiple_applications_share_one_api_key_exchange(self):
        site = RESOLVER.Site(
            brand="guance",
            code="cn3",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://cn3-openway.guance.com",
            ai_api_url="https://cn3-ai-api.guance.com",
        )
        calls = []

        def poster(url, body, headers, operation):
            calls.append((url, body, headers, operation))
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            app_type = "android" if body["app_id"] == "android_app" else "ios"
            return {
                "success": True,
                "data": {
                    "item": {
                        "app_type": app_type,
                        "client_token": f"{app_type}-client-token",
                    }
                },
            }

        metadata, tokens = RESOLVER.resolve_applications(
            site,
            {"android": "android_app", "ios": "ios_app"},
            "temporary-code",
            json_poster=poster,
        )

        self.assertEqual(3, len(calls))
        self.assertEqual(1, sum(url.endswith(RESOLVER.EXCHANGE_PATH) for url, *_ in calls))
        self.assertEqual(
            {"android": "android-client-token", "ios": "ios-client-token"},
            tokens,
        )
        self.assertNotIn("client-token", str(metadata))

    def test_refuses_unignored_in_repository_secret_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / ".git").mkdir()
            output = repository / ".rum" / "runtime-secrets.env"

            with self.assertRaisesRegex(RESOLVER.ResolutionError, "not git-ignored"):
                RESOLVER.write_client_token_env(
                    output,
                    "GUANCE_RUM_CLIENT_TOKEN",
                    "synthetic-client-token",
                    repository=repository,
                )

    def test_cli_output_never_contains_credentials(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        metadata = {
            "site": {
                "brand": "guance",
                "code": "default",
                "catalog": "https://urls.guance.com/",
                "catalog_kind": "official",
                "dataway_url": "https://openway.guance.com",
                "ai_api": "https://ai-api.guance.com",
                "tls_verification": "verified",
            },
            "applications": {
                "default": {
                    "app_id": "web_demo",
                    "api_app_type": "web",
                    "selected_app_type": "web",
                    "selected_app_type_source": "ai_api",
                    "type_mismatch": False,
                }
            },
            "credential_resolution": {
                "exchange_path": RESOLVER.EXCHANGE_PATH,
                "application_lookup_path": RESOLVER.RUM_APP_GET_PATH,
                "api_key_persistence": "memory_only",
            },
        }
        stdout = io.StringIO()
        stderr = io.StringIO()
        temporary_code = "synthetic-temporary-code"
        client_token = "synthetic-client-token"
        with (
            mock.patch.object(RESOLVER, "resolve_site", return_value=site),
            mock.patch.object(
                RESOLVER,
                "resolve_applications",
                return_value=(metadata, {"default": client_token}),
            ),
            mock.patch.dict(
                os.environ,
                {RESOLVER.DEFAULT_TEMP_CODE_ENV: temporary_code},
                clear=False,
            ),
            mock.patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--dataway-url",
                    "https://openway.guance.com",
                    "--app-id",
                    "web_demo",
                ],
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = RESOLVER.main()

        rendered = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(0, result)
        self.assertNotIn(temporary_code, rendered)
        self.assertNotIn(client_token, rendered)
        self.assertIn("runtime:GUANCE_RUM_CLIENT_TOKEN", rendered)

    def test_existing_secret_sink_stops_before_credential_exchange(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.env"
            output.write_text("existing-content\n", encoding="utf-8")
            stderr = io.StringIO()
            with (
                mock.patch.object(RESOLVER, "resolve_site") as resolve_site,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--client-token-env-file",
                        str(output),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

            self.assertEqual(1, result)
            resolve_site.assert_not_called()
            self.assertEqual(
                "existing-content\n",
                output.read_text(encoding="utf-8"),
            )
            self.assertIn("refusing to overwrite", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
