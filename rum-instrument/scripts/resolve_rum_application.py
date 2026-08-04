#!/usr/bin/env python3
"""Resolve a public RUM application without exposing its credentials to the agent."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import getpass
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


CATALOGS = (
    ("guance", "https://urls.guance.com/"),
    ("truewatch", "https://urls.truewatch.com/"),
)
DEFAULT_RUM_OPENWAY_ALIASES = {
    "https://rum-openway.guance.com": ("guance", "default"),
}
APPLICATION_TYPES = {
    "web",
    "miniapp",
    "android",
    "ios",
    "custom",
    "reactnative",
    "harmonyos",
}
CLIENT_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]+$")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SLOT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EXCHANGE_PATH = "/api/v1/account/accesskey/exchange"
RUM_APP_GET_PATH = "/api/v1/rum/app/get"
DEFAULT_TEMP_CODE_ENV = "GUANCE_TEMP_AUTH_CODE"
DEFAULT_CLIENT_TOKEN_ENV = "GUANCE_RUM_CLIENT_TOKEN"


class ResolutionError(RuntimeError):
    """A safe-to-display resolution error that never contains response bodies."""


@dataclass(frozen=True)
class Site:
    brand: str
    code: str
    catalog_url: str
    dataway_url: str
    ai_api_url: str
    catalog_kind: str = "official"
    tls_verification: str = "verified"


JsonFetcher = Callable[[str], dict[str, Any]]
JsonPoster = Callable[[str, dict[str, str], dict[str, str], str], dict[str, Any]]
Sleeper = Callable[[float], None]


def normalize_origin(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolutionError(f"{field} must be a non-empty absolute URL")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ResolutionError(f"{field} must be an absolute http(s) URL")
    try:
        parsed.port
    except ValueError:
        raise ResolutionError(f"{field} contains an invalid port") from None
    if parsed.hostname is None or any(
        character.isspace() or ord(character) < 32
        for character in parsed.netloc
    ):
        raise ResolutionError(f"{field} contains an invalid host")
    if parsed.username or parsed.password:
        raise ResolutionError(f"{field} must not contain URL credentials")
    if parsed.query or parsed.fragment:
        raise ResolutionError(f"{field} must not contain a query or fragment")
    if parsed.path not in {"", "/"}:
        raise ResolutionError(f"{field} must be an origin without a path")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _read_json_response(
    request: Request,
    timeout: float,
    operation: str,
    *,
    tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout, context=tls_context) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise ResolutionError(f"{operation} failed with HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise ResolutionError(f"{operation} failed before a valid JSON response was received") from None
    if not isinstance(payload, dict):
        raise ResolutionError(f"{operation} returned an invalid JSON object")
    return payload


def fetch_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "rum-instrument/1",
        },
    )
    return _read_json_response(request, timeout, "site catalog lookup")


def post_json(
    url: str,
    body: dict[str, str],
    headers: dict[str, str],
    operation: str,
    timeout: float = 15.0,
    *,
    tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "rum-instrument/1",
        **headers,
    }
    request = Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    return _read_json_response(
        request,
        timeout,
        operation,
        tls_context=tls_context,
    )


def _catalog_entries(payload: dict[str, Any], catalog_url: str) -> dict[str, Any]:
    entries = payload.get("urls")
    if not isinstance(entries, dict) or not entries:
        raise ResolutionError(f"site catalog {catalog_url} does not contain a non-empty urls object")
    return entries


def resolve_site(
    dataway_url: str,
    *,
    catalog_fetcher: JsonFetcher = fetch_json,
    catalogs: tuple[tuple[str, str], ...] = CATALOGS,
    catalog_kind: str = "official",
    tls_verification: str = "verified",
) -> Site:
    requested_origin = normalize_origin(dataway_url, "datawayUrl")
    loaded: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    unavailable_catalogs: list[str] = []

    for brand, catalog_url in catalogs:
        try:
            entries = _catalog_entries(catalog_fetcher(catalog_url), catalog_url)
        except ResolutionError:
            unavailable_catalogs.append(catalog_url)
            continue
        for code, raw_entry in entries.items():
            if not isinstance(code, str) or not isinstance(raw_entry, dict):
                continue
            openway = raw_entry.get("openway")
            ai_api = raw_entry.get("ai_api")
            if not isinstance(openway, str) or not isinstance(ai_api, str):
                continue
            try:
                openway_origin = normalize_origin(openway, f"{catalog_url}:{code}.openway")
            except ResolutionError:
                continue
            loaded[(brand, code)] = (catalog_url, raw_entry)
            if requested_origin == openway_origin:
                return _site_from_entry(
                    brand,
                    code,
                    catalog_url,
                    requested_origin,
                    raw_entry,
                    catalog_kind=catalog_kind,
                    tls_verification=tls_verification,
                )
        alias = DEFAULT_RUM_OPENWAY_ALIASES.get(requested_origin)
        if alias and alias[0] == brand and alias in loaded:
            alias_brand, alias_code = alias
            alias_catalog_url, entry = loaded[alias]
            return _site_from_entry(
                alias_brand,
                alias_code,
                alias_catalog_url,
                requested_origin,
                entry,
                catalog_kind=catalog_kind,
                tls_verification=tls_verification,
            )

    alias = DEFAULT_RUM_OPENWAY_ALIASES.get(requested_origin)
    if alias and alias in loaded:
        brand, code = alias
        catalog_url, entry = loaded[alias]
        return _site_from_entry(
            brand,
            code,
            catalog_url,
            requested_origin,
            entry,
            catalog_kind=catalog_kind,
            tls_verification=tls_verification,
        )

    checked = ", ".join(catalog_url for _, catalog_url in catalogs)
    unavailable = (
        f"; unavailable catalogs: {', '.join(unavailable_catalogs)}"
        if unavailable_catalogs
        else ""
    )
    raise ResolutionError(
        f"datawayUrl origin {requested_origin} did not match an openway entry; "
        f"catalogs checked: {checked}{unavailable}"
    )


def _site_from_entry(
    brand: str,
    code: str,
    catalog_url: str,
    dataway_url: str,
    entry: dict[str, Any],
    *,
    catalog_kind: str,
    tls_verification: str,
) -> Site:
    ai_api_url = normalize_origin(str(entry.get("ai_api", "")), f"{catalog_url}:{code}.ai_api")
    if not ai_api_url.startswith("https://"):
        raise ResolutionError("the matched site catalog ai_api endpoint must use https")
    return Site(
        brand=brand,
        code=code,
        catalog_url=catalog_url,
        dataway_url=dataway_url,
        ai_api_url=ai_api_url,
        catalog_kind=catalog_kind,
        tls_verification=tls_verification,
    )


def load_test_site_catalog(path: Path) -> tuple[Path, dict[str, Any]]:
    resolved = path.expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except OSError:
        raise ResolutionError("the test site catalog file could not be read") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ResolutionError("the test site catalog file is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise ResolutionError("the test site catalog must contain a JSON object")
    _catalog_entries(payload, f"test-file:{resolved}")
    return resolved, payload


def resolve_test_site(
    dataway_url: str,
    catalog_file: Path,
    *,
    insecure_test_tls: bool = False,
) -> Site:
    resolved, payload = load_test_site_catalog(catalog_file)
    catalog_reference = f"test-file:{resolved}"
    return resolve_site(
        dataway_url,
        catalog_fetcher=lambda _: payload,
        catalogs=(("testing", catalog_reference),),
        catalog_kind="testing_override",
        tls_verification=(
            "disabled_for_testing" if insecure_test_tls else "verified"
        ),
    )


def build_ai_api_tls_context(
    *,
    insecure_test_tls: bool,
    testing_override: bool,
) -> ssl.SSLContext | None:
    if insecure_test_tls and not testing_override:
        raise ResolutionError(
            "--insecure-test-tls requires --test-site-catalog-file"
        )
    if insecure_test_tls:
        return ssl._create_unverified_context()
    return None


def _response_item(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    if payload.get("success") is not True:
        raise ResolutionError(f"{operation} was rejected")
    data = payload.get("data")
    item = data.get("item") if isinstance(data, dict) else None
    if not isinstance(item, dict):
        raise ResolutionError(f"{operation} response did not contain data.item")
    return item


def resolve_application(
    site: Site,
    app_id: str,
    temporary_authorization_code: str,
    *,
    user_application_type: str | None = None,
    json_poster: JsonPoster = post_json,
) -> tuple[dict[str, Any], str]:
    metadata, client_tokens = resolve_applications(
        site,
        {"default": app_id},
        temporary_authorization_code,
        user_application_types=(
            {"default": user_application_type}
            if user_application_type is not None
            else {}
        ),
        json_poster=json_poster,
    )
    return {
        **metadata,
        "application": metadata["applications"]["default"],
    }, client_tokens["default"]


def resolve_applications(
    site: Site,
    application_ids: dict[str, str],
    temporary_authorization_code: str,
    *,
    user_application_types: dict[str, str] | None = None,
    json_poster: JsonPoster = post_json,
    lookup_attempts: int = 3,
    retry_delay: float = 1.0,
    sleeper: Sleeper = time.sleep,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(application_ids, dict) or not application_ids:
        raise ResolutionError("at least one appId is required")
    for slot, app_id in application_ids.items():
        if (
            not isinstance(slot, str)
            or not SLOT_PATTERN.fullmatch(slot)
            or not isinstance(app_id, str)
            or not app_id.strip()
        ):
            raise ResolutionError("every appId slot and value must be a non-empty string")
    if not isinstance(temporary_authorization_code, str) or not temporary_authorization_code.strip():
        raise ResolutionError("the temporary authorization code input is empty")
    temporary_authorization_code = temporary_authorization_code.strip()
    if lookup_attempts < 1:
        raise ResolutionError("lookup_attempts must be at least 1")
    selected_user_types = user_application_types or {}
    if set(selected_user_types) - set(application_ids):
        raise ResolutionError("applicationType contains a slot that has no matching appId")
    if any(value not in APPLICATION_TYPES for value in selected_user_types.values()):
        raise ResolutionError(
            "applicationType must be web, miniapp, android, ios, custom, reactnative, or harmonyos"
        )

    exchange_url = f"{site.ai_api_url}{EXCHANGE_PATH}"
    exchange_payload = json_poster(
        exchange_url,
        {"code": temporary_authorization_code},
        {},
        "temporary authorization code exchange",
    )
    api_key = _response_item(exchange_payload, "temporary authorization code exchange").get("sk")
    if not isinstance(api_key, str) or not api_key:
        raise ResolutionError("temporary authorization code exchange did not return data.item.sk")

    applications: dict[str, dict[str, Any]] = {}
    client_tokens: dict[str, str] = {}
    for slot, app_id in application_ids.items():
        app_url = f"{site.ai_api_url}{RUM_APP_GET_PATH}"
        operation = f"RUM application lookup for slot {slot}"
        app_item: dict[str, Any] | None = None
        for attempt in range(lookup_attempts):
            app_payload = json_poster(
                app_url,
                {"app_id": app_id.strip()},
                {"DF-API-KEY": api_key},
                operation,
            )
            candidate = _response_item(app_payload, operation)
            returned_app_id = candidate.get("app_id")
            if returned_app_id is not None and returned_app_id != app_id.strip():
                raise ResolutionError(f"{operation} returned a different app_id")

            token_expired = candidate.get("token_expired")
            sync_status = candidate.get("client_token_sync_status")
            mapping_status = candidate.get("mapping_status")
            mapping_ready = candidate.get("mapping_ready")
            if token_expired is not False:
                raise ResolutionError(f"{operation} returned an expired or unverifiable Client Token")
            if sync_status in {"failed", "not_applicable"}:
                raise ResolutionError(f"{operation} reported Client Token synchronization failure")
            if mapping_status == "failed":
                raise ResolutionError(f"{operation} reported application mapping failure")
            if (
                sync_status == "accepted"
                and mapping_status == "ready"
                and mapping_ready is True
            ):
                app_item = candidate
                break
            if (
                sync_status not in {"accepted", "queued"}
                or mapping_status not in {"pending", "ready"}
                or not isinstance(mapping_ready, bool)
            ):
                raise ResolutionError(f"{operation} returned unsupported readiness metadata")
            if attempt + 1 < lookup_attempts:
                sleeper(retry_delay)

        if app_item is None:
            raise ResolutionError(
                f"{operation} did not become ready after {lookup_attempts} attempts"
            )
        client_token = app_item.get("client_token")
        api_application_type = app_item.get("app_type")
        if (
            not isinstance(client_token, str)
            or not client_token
            or not CLIENT_TOKEN_PATTERN.fullmatch(client_token)
        ):
            raise ResolutionError(
                f"{operation} did not return a usable data.item.client_token"
            )
        if api_application_type not in APPLICATION_TYPES:
            raise ResolutionError(
                f"RUM application lookup for slot {slot} returned an unsupported app_type"
            )

        user_type = selected_user_types.get(slot)
        applications[slot] = {
            "app_id": app_id.strip(),
            "api_app_type": api_application_type,
            "selected_app_type": user_type or api_application_type,
            "selected_app_type_source": "user" if user_type else "ai_api",
            "type_mismatch": bool(user_type and user_type != api_application_type),
            "token_expired": False,
            "client_token_sync_status": app_item["client_token_sync_status"],
            "mapping_status": app_item["mapping_status"],
            "mapping_ready": True,
        }
        client_tokens[slot] = client_token

    metadata = {
        "site": {
            "brand": site.brand,
            "code": site.code,
            "catalog": site.catalog_url,
            "catalog_kind": site.catalog_kind,
            "dataway_url": site.dataway_url,
            "ai_api": site.ai_api_url,
            "tls_verification": site.tls_verification,
        },
        "applications": applications,
        "credential_resolution": {
            "status": "resolved",
            "exchange_path": EXCHANGE_PATH,
            "application_lookup_path": RUM_APP_GET_PATH,
            "api_key_persistence": "memory_only",
        },
    }
    return metadata, client_tokens


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_git_ignored(path: Path, repository: Path) -> None:
    repository = repository.resolve()
    path = path.resolve()
    try:
        root_result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if (
            root_result.returncode != 0
            or Path(root_result.stdout.strip()).resolve() != repository
        ):
            raise ResolutionError("--repository must point to the Git worktree root")
        if not _is_within(path, repository):
            return
        relative = path.relative_to(repository)
        result = subprocess.run(
            ["git", "-C", str(repository), "check-ignore", "-q", "--", str(relative)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        raise ResolutionError("git is required to verify an in-repository secret file") from None
    if result.returncode != 0:
        raise ResolutionError(
            "the requested client-token env file is inside the repository but is not git-ignored"
        )


def write_client_token_env(
    path: Path,
    environment_name: str,
    client_token: str,
    *,
    repository: Path | None = None,
) -> Path:
    return write_client_tokens_env(
        path,
        {"default": environment_name},
        {"default": client_token},
        repository=repository,
    )


def write_client_tokens_env(
    path: Path,
    environment_names: dict[str, str],
    client_tokens: dict[str, str],
    *,
    repository: Path | None = None,
) -> Path:
    if set(environment_names) != set(client_tokens) or not environment_names:
        raise ResolutionError("every Client Token must have exactly one runtime environment name")
    if len(set(environment_names.values())) != len(environment_names):
        raise ResolutionError("client-token environment names must be unique")
    for environment_name in environment_names.values():
        if not ENV_NAME_PATTERN.fullmatch(environment_name):
            raise ResolutionError("client-token environment name is invalid")
    for client_token in client_tokens.values():
        if not CLIENT_TOKEN_PATTERN.fullmatch(client_token):
            raise ResolutionError("client token contains characters unsafe for a dotenv assignment")

    candidate = path.expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise ResolutionError("client-token env file already exists; refusing to overwrite it")
    output = candidate.resolve()
    if repository is not None:
        _require_git_ignored(output, repository)

    created = False
    try:
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for slot in sorted(client_tokens):
                stream.write(f"{environment_names[slot]}={client_tokens[slot]}\n")
        os.chmod(output, 0o600)
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise ResolutionError("client-token env file could not be created safely") from None
    return output


def build_safe_result(
    metadata: dict[str, Any],
    *,
    client_token_environments: dict[str, str],
    secret_file: Path | None,
) -> dict[str, Any]:
    return {
        **metadata,
        "client_tokens": {
            slot: {
                "source": f"runtime:{environment_name}",
                "availability": "persisted" if secret_file is not None else "planned",
            }
            for slot, environment_name in sorted(client_token_environments.items())
        },
        "secret_sink": (
            {
                "path": str(secret_file),
                "format": "dotenv",
            }
            if secret_file is not None
            else None
        ),
    }


def parse_slot_assignments(values: list[str] | None, field: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw in values or []:
        if "=" in raw:
            slot, value = raw.split("=", 1)
        else:
            slot, value = "default", raw
        slot = slot.strip()
        value = value.strip()
        if not SLOT_PATTERN.fullmatch(slot) or not value:
            raise ResolutionError(f"{field} assignments must use [slot=]value")
        if slot in assignments:
            raise ResolutionError(f"{field} contains duplicate slot {slot}")
        assignments[slot] = value
    return assignments


def default_client_token_environments(application_ids: dict[str, str]) -> dict[str, str]:
    if set(application_ids) == {"default"}:
        return {"default": DEFAULT_CLIENT_TOKEN_ENV}
    environments: dict[str, str] = {}
    for slot in application_ids:
        normalized_slot = re.sub(r"[^A-Za-z0-9]+", "_", slot).strip("_").upper()
        if not normalized_slot:
            raise ResolutionError(f"cannot derive a runtime environment name for appId slot {slot}")
        environments[slot] = f"{DEFAULT_CLIENT_TOKEN_ENV}_{normalized_slot}"
    if len(set(environments.values())) != len(environments):
        raise ResolutionError("appId slots produce duplicate runtime environment names")
    return environments


def read_temporary_authorization_code(
    *,
    environment_name: str | None,
    from_stdin: bool,
) -> str:
    if from_stdin:
        if sys.stdin.isatty():
            temporary_code = getpass.getpass("Temporary authorization code: ")
        else:
            temporary_code = sys.stdin.readline().rstrip("\r\n")
    else:
        selected_environment = environment_name or DEFAULT_TEMP_CODE_ENV
        if not ENV_NAME_PATTERN.fullmatch(selected_environment):
            raise ResolutionError("temporary authorization code environment name is invalid")
        temporary_code = os.environ.get(selected_environment, "")
    if not temporary_code.strip():
        raise ResolutionError("the temporary authorization code input is empty")
    return temporary_code.strip()


def site_metadata(site: Site) -> dict[str, Any]:
    return {
        "site": {
            "brand": site.brand,
            "code": site.code,
            "catalog": site.catalog_url,
            "catalog_kind": site.catalog_kind,
            "dataway_url": site.dataway_url,
            "ai_api": site.ai_api_url,
            "tls_verification": site.tls_verification,
        },
        "credential_resolution": {
            "status": "catalog_resolved",
            "exchange_path": EXCHANGE_PATH,
            "application_lookup_path": RUM_APP_GET_PATH,
            "api_key_persistence": "memory_only",
        },
    }


def write_metadata_file(path: Path, rendered: str) -> Path:
    candidate = path.expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise ResolutionError("metadata file already exists; refusing to overwrite it")
    output = candidate.resolve()
    created = False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"{rendered}\n")
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise ResolutionError("metadata file could not be created safely") from None
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataway-url", required=True)
    parser.add_argument(
        "--app-id",
        action="append",
        help="repeat [slot=]APP_ID for independently deployed applications",
    )
    parser.add_argument(
        "--site-only",
        action="store_true",
        help="resolve only the official site catalog; do not exchange credentials or look up applications",
    )
    parser.add_argument(
        "--application-type",
        action="append",
        help="repeat [slot=]TYPE; user values take precedence over AI API metadata",
    )
    temporary_code_source = parser.add_mutually_exclusive_group()
    temporary_code_source.add_argument(
        "--temporary-auth-code-env",
        help=f"read the code from this environment variable; defaults to {DEFAULT_TEMP_CODE_ENV}",
    )
    temporary_code_source.add_argument(
        "--temporary-auth-code-stdin",
        action="store_true",
        help="read one code line from stdin; terminal input is hidden",
    )
    parser.add_argument(
        "--client-token-env",
        action="append",
        help="repeat [slot=]ENV_NAME; defaults are derived from appId slots",
    )
    parser.add_argument("--client-token-env-file", type=Path)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--metadata-file", type=Path)
    parser.add_argument(
        "--allow-external-secret-sink",
        action="store_true",
        help="allow an explicitly reviewed secret sink outside the repository",
    )
    parser.add_argument(
        "--test-site-catalog-file",
        type=Path,
        help="explicit test-only catalog override; disables official catalog lookup for this run",
    )
    parser.add_argument(
        "--insecure-test-tls",
        action="store_true",
        help="test only: disable AI API certificate verification; requires a test catalog file",
    )
    arguments = parser.parse_args()

    try:
        application_ids = parse_slot_assignments(arguments.app_id, "appId")
        application_types = parse_slot_assignments(
            arguments.application_type,
            "applicationType",
        )
        if arguments.site_only:
            incompatible = (
                application_ids
                or application_types
                or arguments.temporary_auth_code_env
                or arguments.temporary_auth_code_stdin
                or arguments.client_token_env
                or arguments.client_token_env_file
                or arguments.repository
                or arguments.allow_external_secret_sink
            )
            if incompatible:
                raise ResolutionError(
                    "--site-only accepts only site resolution and optional metadata output"
                )
        elif not application_ids:
            raise ResolutionError("at least one --app-id is required unless --site-only is used")
        elif arguments.client_token_env_file is None:
            raise ResolutionError(
                "application lookup requires --client-token-env-file so the Client Token is not discarded"
            )
        elif arguments.metadata_file is None:
            raise ResolutionError(
                "application lookup requires --metadata-file for recoverable non-secret results"
            )
        client_token_environments = (
            parse_slot_assignments(arguments.client_token_env, "client-token environment")
            if arguments.client_token_env
            else default_client_token_environments(application_ids)
        )
        if set(application_types) - set(application_ids):
            raise ResolutionError("applicationType contains a slot that has no matching appId")
        if set(client_token_environments) != set(application_ids):
            raise ResolutionError(
                "client-token environment slots must exactly match appId slots"
            )
        if arguments.client_token_env_file is not None:
            candidate = arguments.client_token_env_file.expanduser()
            if candidate.exists() or candidate.is_symlink():
                raise ResolutionError(
                    "client-token env file already exists; refusing to overwrite it"
                )
            if arguments.repository is None:
                raise ResolutionError(
                    "--client-token-env-file requires --repository for Git ignore verification"
                )
        if arguments.metadata_file is not None:
            metadata_candidate = arguments.metadata_file.expanduser()
            if metadata_candidate.exists() or metadata_candidate.is_symlink():
                raise ResolutionError("metadata file already exists; refusing to overwrite it")
            if (
                arguments.client_token_env_file is not None
                and metadata_candidate.resolve()
                == arguments.client_token_env_file.expanduser().resolve()
            ):
                raise ResolutionError(
                    "metadata file and client-token env file must use different paths"
                )
        if arguments.client_token_env_file is not None:
            repository_root = arguments.repository.expanduser().resolve()
            secret_output = arguments.client_token_env_file.expanduser().resolve()
            if (
                not _is_within(secret_output, repository_root)
                and not arguments.allow_external_secret_sink
            ):
                raise ResolutionError(
                    "an external client-token sink requires --allow-external-secret-sink"
                )
        if arguments.client_token_env_file is not None:
            _require_git_ignored(
                arguments.client_token_env_file.expanduser().resolve(),
                arguments.repository,
            )
        testing_override = arguments.test_site_catalog_file is not None
        tls_context = build_ai_api_tls_context(
            insecure_test_tls=arguments.insecure_test_tls,
            testing_override=testing_override,
        )
        site = (
            resolve_test_site(
                arguments.dataway_url,
                arguments.test_site_catalog_file,
                insecure_test_tls=arguments.insecure_test_tls,
            )
            if arguments.test_site_catalog_file is not None
            else resolve_site(arguments.dataway_url)
        )
        if arguments.site_only:
            rendered = json.dumps(
                site_metadata(site),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            if arguments.metadata_file is not None:
                write_metadata_file(arguments.metadata_file, rendered)
            print(rendered)
            return 0
        temporary_code = read_temporary_authorization_code(
            environment_name=arguments.temporary_auth_code_env,
            from_stdin=arguments.temporary_auth_code_stdin,
        )

        def selected_json_poster(
            url: str,
            body: dict[str, str],
            headers: dict[str, str],
            operation: str,
        ) -> dict[str, Any]:
            return post_json(
                url,
                body,
                headers,
                operation,
                tls_context=tls_context,
            )

        metadata, client_tokens = resolve_applications(
            site,
            application_ids,
            temporary_code,
            user_application_types=application_types,
            json_poster=selected_json_poster,
        )
        intended_secret_file = arguments.client_token_env_file.expanduser().resolve()
        result = build_safe_result(
            metadata,
            client_token_environments=client_token_environments,
            secret_file=intended_secret_file,
        )
        rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        secret_file = write_client_tokens_env(
            arguments.client_token_env_file,
            client_token_environments,
            client_tokens,
            repository=arguments.repository,
        )
        try:
            write_metadata_file(arguments.metadata_file, rendered)
        except ResolutionError as metadata_error:
            try:
                secret_file.unlink(missing_ok=True)
            except OSError:
                raise ResolutionError(
                    "metadata persistence failed and the new client-token sink "
                    "could not be rolled back; remove that sink before retrying"
                ) from None
            raise metadata_error
        print(rendered)
        return 0
    except ResolutionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
