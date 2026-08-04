#!/usr/bin/env python3
"""Validate a rum-instrument .rum/plan.json contract using only the standard library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any
from urllib.parse import urlsplit


RECEIVER_MODES = {"public_dataway", "datakit"}
TARGET_DISPOSITIONS = {"planned", "existing", "instrumented", "skipped", "blocked", "failed"}
REFERENCE_PREFIXES = ("template:", "env:", "existing:", "runtime:")
DEPENDENCY_ACTIONS = {"preserve", "add", "upgrade", "remove", "none", "blocked"}
CONTROL_PLANE_CATALOGS = {
    "https://urls.guance.com/",
    "https://urls.truewatch.com/",
}
TESTING_CONTROL_PLANE_CATALOG = "testing_override"
TLS_VERIFICATION_MODES = {"verified", "disabled_for_testing"}
APPLICATION_TYPES = {
    "web",
    "miniapp",
    "android",
    "ios",
    "custom",
    "reactnative",
    "harmonyos",
}
APPLICATION_TYPE_SOURCES = {"user", "ai_api", "repository"}
GENERATED_PATH_PARTS = {
    ".gradle",
    "build",
    "deriveddata",
    "dist",
    "node_modules",
    "oh_modules",
    "pods",
    "unpackage",
    "vendor",
}
SENSITIVE_FIELDS = {
    "accesstoken",
    "apikey",
    "apikeys",
    "apikeysource",
    "apikeyvalue",
    "authorization",
    "authorizationheader",
    "authorizationheaders",
    "clienttoken",
    "clienttokensource",
    "clienttokenvalue",
    "cookie",
    "cookies",
    "password",
    "refreshtoken",
    "secret",
    "secretenvironmentvalue",
    "secretenvironmentvalues",
    "secretvalue",
    "setcookie",
    "temporaryauthorizationcode",
    "temporaryauthcode",
}
PAYLOAD_FIELDS = {
    "capturedtelemetry",
    "requestbody",
    "responsebody",
    "telemetrypayload",
}
SAFE_PAYLOAD_DECLARATIONS = {
    "disabled",
    "excluded",
    "not_collected",
    "redacted",
}
SENSITIVE_REFERENCE_FIELDS = {"source", "input", "runtime"}
SENSITIVE_REFERENCE_METADATA_FIELDS = {
    "behavior",
    "confidence",
    "description",
    "persistence",
    "provenance",
}


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_source(
    value: Any,
    location: str,
    errors: list[str],
    *,
    allow_literal: bool,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return

    source = value.get("source")
    literal = value.get("value")
    if source is not None and literal is not None:
        errors.append(f"{location} must contain source or value, not both")
        return
    if source is not None:
        if not is_nonempty_string(source):
            errors.append(f"{location}.source must be a non-empty string")
        return
    if allow_literal and is_nonempty_string(literal):
        return
    errors.append(f"{location} must contain a non-empty source" + (" or value" if allow_literal else ""))


def reference_identity(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    if is_nonempty_string(value.get("source")):
        return "source", value["source"]
    if is_nonempty_string(value.get("value")):
        return "value", value["value"]
    return None


def validate_application_id_input(
    value: Any,
    errors: list[str],
) -> tuple[str | None, tuple[str, str] | None]:
    if not isinstance(value, dict):
        errors.append("request.application_id_input must be an object")
        return None, None

    kind = value.get("kind")
    if kind == "scalar":
        reference = value.get("reference")
        validate_source(
            reference,
            "request.application_id_input.reference",
            errors,
            allow_literal=True,
        )
        return kind, reference_identity(reference)
    if kind == "map":
        references = value.get("references")
        if not isinstance(references, dict) or not references:
            errors.append("request.application_id_input.references must be a non-empty object")
            return kind, None
        identities: set[tuple[str, str]] = set()
        for key, reference in references.items():
            location = f"request.application_id_input.references.{key}"
            if not is_nonempty_string(key):
                errors.append("request.application_id_input.references keys must be non-empty strings")
                continue
            validate_source(reference, location, errors, allow_literal=True)
            identity = reference_identity(reference)
            if identity in identities:
                errors.append(f"{location} duplicates another Application ID input reference")
            elif identity:
                identities.add(identity)
        return kind, None

    errors.append("request.application_id_input.kind must be scalar or map")
    return None, None


def normalize_field_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def is_source_reference(value: Any) -> bool:
    if is_nonempty_string(value):
        return value.startswith(REFERENCE_PREFIXES)
    if not isinstance(value, dict) or "value" in value:
        return False
    if not set(value).issubset(SENSITIVE_REFERENCE_FIELDS | SENSITIVE_REFERENCE_METADATA_FIELDS):
        return False
    references = [value[field] for field in SENSITIVE_REFERENCE_FIELDS if field in value]
    return bool(references) and all(
        is_nonempty_string(reference) and reference.startswith(REFERENCE_PREFIXES)
        for reference in references
    )


def is_safe_payload_declaration(value: Any) -> bool:
    if value is None or value is False:
        return True
    return isinstance(value, str) and value.strip().lower() in SAFE_PAYLOAD_DECLARATIONS


def validate_sensitive_values(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                continue
            nested_location = f"{location}.{key}" if location else key
            normalized = normalize_field_name(key)
            if normalized in PAYLOAD_FIELDS and not is_safe_payload_declaration(nested):
                errors.append(f"{nested_location} must not be persisted")
                continue
            if (
                normalized in SENSITIVE_FIELDS
                and not is_source_reference(nested)
                and not is_safe_payload_declaration(nested)
            ):
                errors.append(
                    f"{nested_location} must contain only a non-secret source reference or disabled/redacted declaration"
                )
                continue
            validate_sensitive_values(nested, nested_location, errors)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_sensitive_values(nested, f"{location}[{index}]", errors)


def validate_nonempty_string_list(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{location} must be a non-empty array")
        return
    if any(not is_nonempty_string(item) for item in value):
        errors.append(f"{location} must contain only non-empty strings")


def validate_https_origin(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or "value" not in value:
        return
    endpoint = value.get("value")
    if not is_nonempty_string(endpoint):
        return
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        errors.append(f"{location}.value must be an HTTPS origin")


def validate_control_plane(value: Any, errors: list[str]) -> None:
    location = "request.receiver.control_plane"
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return

    status = value.get("status")
    if status not in {"resolved", "blocked"}:
        errors.append(f"{location}.status must be resolved or blocked")

    temporary_code = value.get("temporary_authorization_code")
    if status == "resolved" or temporary_code is not None:
        validate_source(
            temporary_code,
            f"{location}.temporary_authorization_code",
            errors,
            allow_literal=False,
        )
        if isinstance(temporary_code, dict):
            source = temporary_code.get("source")
            if is_nonempty_string(source) and not source.startswith(REFERENCE_PREFIXES):
                errors.append(
                    f"{location}.temporary_authorization_code.source must be a template, env, existing, or runtime reference"
                )
            if "value" in temporary_code:
                errors.append(f"{location}.temporary_authorization_code must never contain a value")

    if value.get("api_key_persistence") != "memory_only":
        errors.append(f"{location}.api_key_persistence must be memory_only")

    if status == "resolved":
        catalog = value.get("catalog")
        tls_verification = value.get("tls_verification", "verified")
        if tls_verification not in TLS_VERIFICATION_MODES:
            errors.append(
                f"{location}.tls_verification must be verified or disabled_for_testing"
            )
        if catalog in CONTROL_PLANE_CATALOGS:
            if value.get("test_only") is True:
                errors.append(
                    f"{location}.test_only is valid only with catalog=testing_override"
                )
            if "catalog_source" in value:
                errors.append(
                    f"{location}.catalog_source is valid only with catalog=testing_override"
                )
            if tls_verification != "verified":
                errors.append(
                    f"{location}.tls_verification must remain verified for official catalogs"
                )
        elif catalog == TESTING_CONTROL_PLANE_CATALOG:
            if value.get("test_only") is not True:
                errors.append(
                    f"{location}.test_only must be true for catalog=testing_override"
                )
            catalog_source = value.get("catalog_source")
            validate_source(
                catalog_source,
                f"{location}.catalog_source",
                errors,
                allow_literal=False,
            )
            source = (
                catalog_source.get("source")
                if isinstance(catalog_source, dict)
                else None
            )
            if is_nonempty_string(source) and not source.startswith(
                ("env:", "existing:")
            ):
                errors.append(
                    f"{location}.catalog_source.source must be an env: or existing: reference"
                )
        else:
            errors.append(
                f"{location}.catalog must be an official catalog URL or testing_override"
            )
        if not is_nonempty_string(value.get("site_code")):
            errors.append(f"{location}.site_code must be a non-empty string")
        validate_source(
            value.get("ai_api_endpoint"),
            f"{location}.ai_api_endpoint",
            errors,
            allow_literal=True,
        )
        validate_https_origin(
            value.get("ai_api_endpoint"),
            f"{location}.ai_api_endpoint",
            errors,
        )
        if value.get("exchange_path") != "/api/v1/account/accesskey/exchange":
            errors.append(
                f"{location}.exchange_path must be /api/v1/account/accesskey/exchange"
            )
        if value.get("application_lookup_path") != "/api/v1/rum/app/get":
            errors.append(f"{location}.application_lookup_path must be /api/v1/rum/app/get")
    elif status == "blocked":
        validate_nonempty_string_list(value.get("blockers"), f"{location}.blockers", errors)


def validate_application_types(
    value: Any,
    slots: Any,
    disposition: Any,
    location: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location}.application_types must be an object")
        return
    declared_slots = set(slots) if isinstance(slots, list) else set()
    extra_slots = sorted(set(value) - declared_slots)
    if extra_slots:
        errors.append(
            f"{location}.application_types contains undeclared slots: {', '.join(extra_slots)}"
        )

    for slot in slots if isinstance(slots, list) else []:
        descriptor = value.get(slot)
        descriptor_location = f"{location}.application_types.{slot}"
        if descriptor is None:
            if disposition == "blocked":
                warnings.append(f"{descriptor_location} remains unresolved")
            else:
                errors.append(f"{location}.application_types is missing slot {slot}")
            continue
        if not isinstance(descriptor, dict):
            errors.append(f"{descriptor_location} must be an object")
            continue
        if descriptor.get("value") not in APPLICATION_TYPES:
            errors.append(
                f"{descriptor_location}.value must be a supported RUM application type"
            )
        if descriptor.get("source") not in APPLICATION_TYPE_SOURCES:
            errors.append(
                f"{descriptor_location}.source must be user, ai_api, or repository"
            )
        if descriptor.get("confidence") not in {"high", "medium", "low"}:
            errors.append(f"{descriptor_location}.confidence must be high, medium, or low")


def validate_planned_file(value: Any, location: str, errors: list[str]) -> None:
    if not is_nonempty_string(value):
        errors.append(f"{location} must be a non-empty repository-relative path")
        return
    if "\\" in value:
        errors.append(f"{location} must use repository-relative POSIX separators")
        return

    path = PurePosixPath(value)
    if path.is_absolute() or value == "." or ".." in path.parts:
        errors.append(f"{location} must stay within the repository")
    if any(part.lower() in GENERATED_PATH_PARTS for part in path.parts):
        errors.append(f"{location} must not point into a generated or dependency directory")


def validate_planned_changes(
    value: Any,
    target_ids: set[str],
    planned_target_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append("planned_changes must be an array")
        return
    if planned_target_ids and not value:
        errors.append("planned_changes must not be empty when targets have disposition=planned")
        return

    covered_targets: set[str] = set()
    used_orders: set[int] = set()
    for index, change in enumerate(value):
        location = f"planned_changes[{index}]"
        if not isinstance(change, dict):
            errors.append(f"{location} must be an object")
            continue

        target_id = change.get("target_id")
        if not is_nonempty_string(target_id):
            errors.append(f"{location}.target_id must be a non-empty string")
        elif target_id not in target_ids:
            errors.append(f"{location}.target_id references an unknown target_id")
        elif target_id not in planned_target_ids:
            errors.append(f"{location}.target_id must reference a target with disposition=planned")
        else:
            covered_targets.add(target_id)

        validate_planned_file(change.get("file"), f"{location}.file", errors)
        order = change.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            errors.append(f"{location}.order must be a positive integer")
        elif order in used_orders:
            errors.append(f"{location}.order duplicates {order}")
        else:
            used_orders.add(order)

        for field in ("purpose", "risk", "rollback"):
            if not is_nonempty_string(change.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")
        validate_nonempty_string_list(change.get("edits"), f"{location}.edits", errors)
        validate_nonempty_string_list(change.get("validation"), f"{location}.validation", errors)

        dependency = change.get("dependency_decision")
        if not isinstance(dependency, dict):
            errors.append(f"{location}.dependency_decision must be an object")
        elif dependency.get("action") not in DEPENDENCY_ACTIONS:
            errors.append(
                f"{location}.dependency_decision.action must be preserve, add, upgrade, remove, none, or blocked"
            )

    for target_id in sorted(planned_target_ids - covered_targets):
        errors.append(f"target {target_id} has no planned change")


def validate_plan(plan: Any, phase: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(plan, dict):
        return ["plan must be a JSON object"], warnings
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    repository = plan.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        for field in ("root", "commit", "analysis_fingerprint"):
            if not is_nonempty_string(repository.get(field)):
                errors.append(f"repository.{field} must be a non-empty string")
        if not isinstance(repository.get("initial_status"), list):
            errors.append("repository.initial_status must be an array")

    request = plan.get("request")
    receiver: Any = None
    application_id_kind: str | None = None
    scalar_application_id: tuple[str, str] | None = None
    if not isinstance(request, dict):
        errors.append("request must be an object")
    else:
        if request.get("intent") not in {"audit", "plan", "implement", "validate", "repair"}:
            errors.append("request.intent must be audit, plan, implement, validate, or repair")
        receiver = request.get("receiver")
        raw_request_fields = sorted(
            {
                "datawayUrl",
                "datakitUrl",
                "headlessUrl",
                "clientToken",
                "temporaryAuthCode",
                "applicationType",
                "appId",
            }
            & set(request)
        )
        if raw_request_fields:
            errors.append(
                "request must normalize raw prompt fields into receiver and targets: "
                + ", ".join(raw_request_fields)
            )
        application_id_kind, scalar_application_id = validate_application_id_input(
            request.get("application_id_input"),
            errors,
        )

    if not isinstance(receiver, dict):
        errors.append("request.receiver must be an object")
    else:
        mode = receiver.get("mode")
        if mode not in RECEIVER_MODES:
            if mode == "headless":
                errors.append(
                    "request.receiver.mode=headless is no longer supported; use public_dataway or datakit"
                )
            else:
                errors.append("request.receiver.mode must be public_dataway or datakit")
        validate_source(receiver.get("endpoint"), "request.receiver.endpoint", errors, allow_literal=True)
        if mode == "public_dataway":
            client_tokens = receiver.get("client_tokens")
            if not isinstance(client_tokens, dict) or not client_tokens:
                errors.append("request.receiver.client_tokens must be a non-empty object")
                client_tokens = {}
            for slot, client_token in client_tokens.items():
                location = f"request.receiver.client_tokens.{slot}"
                if not is_nonempty_string(slot):
                    errors.append(
                        "request.receiver.client_tokens keys must be non-empty strings"
                    )
                    continue
                validate_source(client_token, location, errors, allow_literal=False)
                source = client_token.get("source") if isinstance(client_token, dict) else None
                if is_nonempty_string(source) and not source.startswith(REFERENCE_PREFIXES):
                    errors.append(
                        f"{location}.source must be a template, env, existing, or runtime reference"
                    )
                elif is_nonempty_string(source) and source.startswith("template:"):
                    errors.append(
                        f"{location}.source must be resolved by the control-plane flow, not supplied as a template"
                    )
                if isinstance(client_token, dict) and "value" in client_token:
                    errors.append(f"{location} must never contain a value")
            if "client_token" in receiver:
                errors.append(
                    "request.receiver.client_token is obsolete; use slot-keyed client_tokens"
                )
            validate_control_plane(receiver.get("control_plane"), errors)
        elif "client_token" in receiver or "client_tokens" in receiver:
            errors.append(
                "request.receiver.client_tokens is valid only for public_dataway"
            )
        if mode == "datakit" and "control_plane" in receiver:
            errors.append("request.receiver.control_plane is valid only for public_dataway")

        forbidden_input_fields = {
            "datawayUrl",
            "datakitUrl",
            "headlessUrl",
            "clientToken",
            "temporaryAuthCode",
            "applicationType",
            "appId",
        }
        present = sorted(forbidden_input_fields & set(receiver))
        if present:
            errors.append(
                "request.receiver must use normalized fields; found raw prompt fields: " + ", ".join(present)
            )

    targets = plan.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty array")
        targets = []

    target_ids: set[str] = set()
    planned_target_ids: set[str] = set()
    application_id_owners: dict[tuple[str, str], str] = {}
    application_id_slots: list[tuple[str, str, tuple[str, str] | None]] = []
    for index, target in enumerate(targets):
        location = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{location} must be an object")
            continue

        target_id = target.get("id")
        if not is_nonempty_string(target_id):
            errors.append(f"{location}.id must be a non-empty string")
        elif target_id in target_ids:
            errors.append(f"{location}.id duplicates {target_id}")
        else:
            target_ids.add(target_id)

        for field in ("path", "platform"):
            if not is_nonempty_string(target.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")
        for field in ("variants", "evidence", "application_id_slots", "official_sources", "blockers"):
            if not isinstance(target.get(field), list):
                errors.append(f"{location}.{field} must be an array")

        disposition = target.get("disposition")
        if disposition not in TARGET_DISPOSITIONS:
            errors.append(f"{location}.disposition is invalid")
        elif disposition == "planned" and is_nonempty_string(target_id):
            planned_target_ids.add(target_id)

        slots = target.get("application_id_slots")
        application_ids = target.get("application_ids")
        if not isinstance(application_ids, dict):
            errors.append(f"{location}.application_ids must be an object")
            application_ids = {}
        if isinstance(slots, list):
            if len(slots) != len(set(slot for slot in slots if isinstance(slot, str))):
                errors.append(f"{location}.application_id_slots must not contain duplicates")
            for slot in slots:
                if not is_nonempty_string(slot):
                    errors.append(f"{location}.application_id_slots must contain non-empty strings")
                    continue
                if slot not in application_ids:
                    application_id_slots.append((target_id or location, slot, None))
                    if disposition != "blocked":
                        errors.append(f"{location}.application_ids is missing slot {slot}")
                    else:
                        warnings.append(f"{location} remains blocked on Application ID slot {slot}")
                        blockers = target.get("blockers")
                        if not isinstance(blockers, list) or not any(
                            isinstance(blocker, str) and slot in blocker for blocker in blockers
                        ):
                            errors.append(f"{location}.blockers must identify missing slot {slot}")
                    continue
                validate_source(
                    application_ids[slot],
                    f"{location}.application_ids.{slot}",
                    errors,
                    allow_literal=True,
                )
                reference = application_ids[slot]
                identity = reference_identity(reference)
                application_id_slots.append((target_id or location, slot, identity))
                if identity:
                    owner = application_id_owners.get(identity)
                    current_owner = f"{target_id or location}:{slot}"
                    if owner:
                        errors.append(
                            f"{location}.application_ids.{slot} reuses the Application ID reference owned by {owner}"
                        )
                    else:
                        application_id_owners[identity] = current_owner
        extra_slots = sorted(set(application_ids) - set(slots if isinstance(slots, list) else []))
        if extra_slots:
            errors.append(f"{location}.application_ids contains undeclared slots: {', '.join(extra_slots)}")
        validate_application_types(
            target.get("application_types"),
            slots,
            disposition,
            location,
            errors,
            warnings,
        )

        for field in ("existing_instrumentation", "profile", "receiver_mapping", "privacy", "artifacts"):
            if not isinstance(target.get(field), dict):
                errors.append(f"{location}.{field} must be an object")
        if not target.get("evidence"):
            warnings.append(f"{location} has no repository evidence")
        if disposition == "planned" and not target.get("official_sources"):
            warnings.append(f"{location} has no recorded official source")

    if application_id_kind == "scalar" and scalar_application_id:
        scalar_assignments = [
            (target_id, slot)
            for target_id, slot, identity in application_id_slots
            if identity == scalar_application_id
        ]
        unresolved_slots = [
            (target_id, slot)
            for target_id, slot, identity in application_id_slots
            if identity is None or identity == scalar_application_id
        ]
        if len(unresolved_slots) > 1 and scalar_assignments:
            errors.append(
                "request.application_id_input scalar is ambiguous across multiple unresolved Application ID slots; "
                "leave it unassigned and block those targets until target-specific IDs are provided"
            )
        elif len(unresolved_slots) > 1:
            warnings.append(
                "scalar Application ID input remains unassigned because multiple target-specific slots are unresolved"
            )
        elif len(unresolved_slots) == 1 and not scalar_assignments:
            target_id, slot = unresolved_slots[0]
            errors.append(
                f"request.application_id_input scalar must be assigned to the only unresolved slot {target_id}:{slot}"
            )
        elif not unresolved_slots:
            warnings.append("scalar Application ID input is unused because all target slots use existing references")

    validate_planned_changes(plan.get("planned_changes"), target_ids, planned_target_ids, errors)
    for field in ("validation", "risks", "handoff"):
        if not isinstance(plan.get(field), list):
            errors.append(f"{field} must be an array")

    approval = plan.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval must be an object")
    else:
        status = approval.get("status")
        if status not in {"pending", "approved"}:
            errors.append("approval.status must be pending or approved")
        revision = approval.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            errors.append("approval.revision must be a positive integer")
        if phase == "implement" and status != "approved":
            errors.append("implementation requires approval.status=approved")

    validate_sensitive_values(plan, "", errors)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--phase", choices=("plan", "implement"), default="plan")
    arguments = parser.parse_args()

    try:
        plan = json.loads(arguments.plan.read_text(encoding="utf-8"))
    except OSError as error:
        parser.error(str(error))
    except json.JSONDecodeError as error:
        print(f"invalid JSON: {error}", file=sys.stderr)
        return 1

    errors, warnings = validate_plan(plan, arguments.phase)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"valid rum plan: revision {plan['approval']['revision']} ({arguments.phase})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
