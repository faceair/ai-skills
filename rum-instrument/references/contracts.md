# Plan and inventory contracts

Write UTF-8 JSON with stable key ordering and no comments. Never include client-token values, API keys, cookies, authorization headers, request/response bodies, captured telemetry, or secret environment values.

## `.rum/plan.json`

Use schema version 1:

```json
{
  "schema_version": 1,
  "repository": {
    "root": ".",
    "commit": "<git commit>",
    "initial_status": [],
    "analysis_fingerprint": "<non-secret fingerprint>"
  },
  "request": {
    "intent": "plan",
    "application_id_input": {
      "kind": "scalar",
      "reference": {
        "source": "template:APP_ID"
      }
    },
    "receiver": {
      "mode": "public_dataway",
      "endpoint": {
        "source": "template:DATAWAY_URL"
      },
      "client_tokens": {
        "web": {
          "source": "runtime:GUANCE_RUM_CLIENT_TOKEN"
        }
      },
      "control_plane": {
        "status": "resolved",
        "catalog": "https://urls.guance.com/",
        "site_code": "cn3",
        "ai_api_endpoint": {
          "value": "https://cn3-ai-api.guance.com"
        },
        "exchange_path": "/api/v1/account/accesskey/exchange",
        "application_lookup_path": "/api/v1/rum/app/get",
        "temporary_authorization_code": {
          "source": "env:GUANCE_TEMP_AUTH_CODE"
        },
        "api_key_persistence": "memory_only",
        "tls_verification": "verified"
      }
    }
  },
  "targets": [],
  "planned_changes": [],
  "validation": [],
  "risks": [],
  "handoff": [],
  "approval": {
    "status": "pending",
    "revision": 1
  }
}
```

`receiver.mode` is `public_dataway` or `datakit`. Public DataWay requires endpoint, slot-keyed runtime Client Token references, and control-plane source references. DataKit requires only its endpoint and omits both `client_tokens` and `control_plane`.

For a resolved Public DataWay control plane, `catalog` is normally one of the two official catalogs, `ai_api_endpoint` is the value returned for the matched site, `tls_verification` is `verified`, and the two API paths are fixed. If site/application resolution cannot run, use `status: "blocked"` plus concrete `blockers`; never fill an inferred endpoint. The temporary authorization code is always a source reference, and API Key persistence is always `memory_only`.

An explicitly approved non-production override uses `catalog: "testing_override"`, `catalog_source` with an `env:` or `existing:` source reference, and `test_only: true`. Its `tls_verification` is `verified` or `disabled_for_testing`; the latter is invalid for official catalogs. Even a test override requires an HTTPS `ai_api_endpoint`. Do not represent a custom AI API as a standard Prompt field.

Normalize the user-supplied Application ID shape in `request.application_id_input`. A scalar uses `{"kind":"scalar","reference":{...}}`. A map uses `{"kind":"map","references":{"android":{...},"ios":{...}}}` with the original user-facing keys preserved.

A scalar reference may be assigned only when repository confirmation leaves exactly one unresolved Application ID slot. If multiple slots remain, do not choose a target arbitrarily: leave the scalar unassigned, mark every unresolved target `blocked`, identify each missing slot in `blockers`, and request target-specific IDs.

Sensitive receiver mappings such as `temporary_authorization_code`, `clientToken`, or `Authorization` contain only `source`, or normalized `input`/`runtime`, references using the `template:`, `env:`, `existing:`, or `runtime:` prefixes. They may include non-secret metadata such as `persistence` or `description`, but never a literal `value` or an unrecognized field. A Public DataWay Client Token must not use `template:CLIENT_TOKEN`; it is resolved by the helper and represented by its runtime sink.

Each target records:

```json
{
  "id": "flutter:apps/mobile",
  "path": "apps/mobile",
  "platform": "flutter",
  "variants": ["android", "ios", "web"],
  "evidence": ["apps/mobile/pubspec.yaml", "apps/mobile/web/index.html"],
  "application_id_slots": ["android", "ios", "web"],
  "application_ids": {
    "android": {
      "source": "template:ANDROID_APP_ID"
    },
    "ios": {
      "source": "template:IOS_APP_ID"
    },
    "web": {
      "source": "template:WEB_APP_ID"
    }
  },
  "application_types": {
    "android": {
      "value": "android",
      "source": "ai_api",
      "confidence": "high"
    },
    "ios": {
      "value": "ios",
      "source": "ai_api",
      "confidence": "high"
    },
    "web": {
      "value": "web",
      "source": "user",
      "confidence": "high"
    }
  },
  "existing_instrumentation": {
    "status": "none",
    "files": [],
    "sdk": null,
    "version": null,
    "signals": []
  },
  "profile": {
    "service": {
      "value": "mobile",
      "source": "apps/mobile/pubspec.yaml:name",
      "confidence": "high"
    },
    "version": {
      "value": null,
      "source": "apps/mobile/pubspec.yaml:version",
      "confidence": "high"
    },
    "env": {
      "value": null,
      "source": "runtime:RUM_ENV",
      "confidence": "medium"
    },
    "signals": {
      "rum": true,
      "logs": "preserve",
      "tracing": "preserve",
      "replay": false
    }
  },
  "receiver_mapping": {},
  "privacy": {},
  "artifacts": {},
  "official_sources": [
    "https://docs.guance.com/real-user-monitoring/flutter/app-access/",
    "https://docs.guance.com/real-user-monitoring/web/app-access/"
  ],
  "disposition": "planned",
  "blockers": []
}
```

Every confirmed slot must have exactly one Application ID reference. Missing IDs are permitted only when target disposition is `blocked` and the missing slots appear in `blockers`. Do not silently reuse one ID.

Every confirmed slot also records one application type. Allowed values are `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`; allowed sources are `user`, `ai_api`, and `repository`. A user value takes precedence, but a user/API mismatch is a blocker until reviewed.

Every target with disposition `planned` must be covered by at least one `planned_changes` entry:

```json
{
  "target_id": "web:.",
  "file": "src/rum.ts",
  "order": 1,
  "purpose": "Configure Browser RUM once",
  "edits": [
    "Add the approved Browser RUM initializer"
  ],
  "dependency_decision": {
    "action": "preserve"
  },
  "validation": [
    "npm test"
  ],
  "risk": "The initializer could run too late",
  "rollback": "Revert src/rum.ts"
}
```

`target_id` must reference a declared target whose disposition is `planned`. `file` is an exact repository-relative maintained source or configuration path, never generated output or a dependency directory. `order` is a unique positive integer. `edits` and `validation` contain non-empty commands or instructions. `dependency_decision.action` is `preserve`, `add`, `upgrade`, `remove`, `none`, or `blocked`.

For an added, upgraded, or preserved official dependency, also record package/repository owner, selected version or constraint, primary-source URLs, compatibility evidence, and verification date in `dependency_decision`.

Approval status is `pending` or `approved`. Record approver/time only when known; never invent them. Increment `revision` whenever the target graph, receiver, SDK choice, signals, privacy behavior, artifacts, or exact edit set changes.

Plans from another schema version are stale. Preserve usable connection-source references, rebuild repository analysis, increment the revision, and request approval.

## `.rum/instrumentation.json`

Use:

```json
{
  "schema_version": 1,
  "generated_from_plan_revision": 1,
  "repository": {},
  "receiver": {
    "mode": "public_dataway",
    "endpoint": {
      "source": "template:DATAWAY_URL"
    },
    "client_tokens": {
      "web": {
        "source": "runtime:GUANCE_RUM_CLIENT_TOKEN"
      }
    }
  },
  "targets": [],
  "validation": [],
  "artifacts": [],
  "remote_verification": {
    "verified": false,
    "evidence": []
  },
  "handoff": []
}
```

Every discovered target appears exactly once with disposition `existing`, `instrumented`, `skipped`, `blocked`, or `failed`. For existing/instrumented targets record:

- platform variants and Application ID source mapping;
- SDK package/version and primary-source evidence;
- changed and existing source/configuration files;
- initialization lifecycle and single-init proof;
- RUM, Logs, Trace, Replay, WebView, and crash capabilities;
- service/version/environment sources;
- sampling and trace propagation;
- privacy controls and negative-test evidence;
- Sourcemap/dSYM/R8/native-symbol behavior;
- build/test/smoke evidence and residual gaps.

The inventory must never contain a temporary authorization code, API Key, or Client Token value. `remote_verification.verified` remains false unless the user supplies external console/ingestion evidence.

## `docs/rum-instrumentation.md`

Generate an answer-first projection of the inventory:

1. receiver mode and non-secret source references;
2. target/application coverage;
3. existing and changed initialization;
4. SDK/version decisions and official links;
5. privacy, sampling, Trace, Replay, and artifact decisions;
6. baseline and post-change validation evidence;
7. skipped, blocked, failed, and remotely unverified items;
8. rollback and human handoff.

Keep Markdown and JSON consistent. Correct the JSON inventory first when they disagree.
