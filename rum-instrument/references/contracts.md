# Plan and inventory contracts

Write UTF-8 JSON with stable key ordering and no comments. Never include client-token values, API keys, cookies, authorization headers, request/response bodies, captured telemetry, or secret environment values.

## `.rum/plan.json`

Use plan schema version 2:

```json
{
  "schema_version": 2,
  "repository": {
    "root": ".",
    "commit": "<git commit>",
    "initial_status": []
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
          "source": "runtime:GUANCE_RUM_CLIENT_TOKEN",
          "availability": "planned"
        }
      },
      "control_plane": {
        "status": "catalog_resolved",
        "catalog": "https://urls.guance.com/",
        "site_code": "cn3",
        "ai_api_endpoint": {
          "value": "https://cn3-ai-api.guance.com"
        },
        "exchange_path": "/api/v1/account/accesskey/exchange",
        "application_lookup_path": "/api/v1/rum/app/get",
        "temporary_authorization_code": null,
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
    "basis": "plan_only_request",
    "blockers": [],
    "revision": 1
  }
}
```

`receiver.mode` is `public_dataway` or `datakit`. Public DataWay requires endpoint, slot-keyed runtime Client Token references for active targets, and control-plane metadata. DataKit omits both `client_tokens` and `control_plane`, but requires `readiness` with `rum_collector` and `network_reachability` checks. Each check is `unknown`, `verified`, or `blocked`; verified checks carry evidence, while unknown/blocked checks carry concrete handoff. Implementation and final inventory require both checks to be verified.

```json
{
  "mode": "datakit",
  "endpoint": {
    "source": "template:DATAKIT_URL"
  },
  "readiness": {
    "status": "unknown",
    "checks": {
      "rum_collector": {
        "status": "unknown",
        "evidence": [],
        "handoff": ["Verify that the DataKit RUM collector is enabled"]
      },
      "network_reachability": {
        "status": "unknown",
        "evidence": [],
        "handoff": ["Verify runtime reachability to the exact DataKit origin"]
      }
    }
  }
}
```

Resolve the site catalog during planning and keep `status: "catalog_resolved"` stable; new Client Token references use `availability: "planned"`, while an already reviewed runtime sink uses `"existing"`. `temporary_authorization_code` is either absent or a redacted source reference. After plan-phase validation and implementation authorization, run the helper before application-code edits and persist the result in `.rum/control-plane-state.json` or another reviewed Git-ignored path. Do not copy network, credential, Token-persistence, lookup-attempt, sync, or mapping state into the plan. Increment the plan revision only when application metadata changes the selected adapter/edit set or reveals a user-type mismatch. If site resolution cannot complete, use `status: "blocked"` plus concrete `blockers`; blocked plans omit `client_tokens`. Never fill an inferred endpoint. API Key persistence is always `memory_only`.

The only non-production site uses `catalog: "builtin_testing"`, `site_code: "testing"`, `test_only: true`, and `ai_api_endpoint.value: "https://testing-ft2x-ai-api.dataflux.cn"`. Do not accept `catalog_source`, read a site from `evals/`, or support another testing AI API. `tls_verification` is `verified` or `disabled_for_testing`; the latter is invalid for official catalogs. Do not represent a custom AI API as a standard Prompt field.

Normalize the user-supplied Application ID shape in `request.application_id_input`. A scalar uses `{"kind":"scalar","reference":{...}}`. A map uses `{"kind":"map","references":{"android":{...},"ios":{...}}}` with the original user-facing keys preserved.

A scalar reference may be assigned only when repository confirmation leaves exactly one unresolved Application ID slot. If multiple slots remain, do not choose a target arbitrarily: leave the scalar unassigned, mark every unresolved target `blocked`, identify each missing slot in `blockers`, and request target-specific IDs.

Sensitive receiver mappings such as `clientToken`, API Key, or `Authorization` contain only structured references. `template:` and `env:` locators are environment-style names (`[A-Z_][A-Z0-9_]*`); `runtime:` is an environment name or dotted configuration path such as `DEPLOY_CONFIG.rumClientToken`; `existing:` identifies a concrete path/key such as `.env.local#GUANCE_RUM_CLIENT_TOKEN`. A prefix followed by a token-like literal is invalid. Only `temporary_authorization_code`/`temporaryAuthCode` may use the exact redacted marker `prompt:provided`. Never append or encode the supplied value in that marker. Sensitive mappings may include approved non-secret metadata such as `persistence`, `description`, or Client Token `availability`, but never a literal `value` or an unrecognized field. A Public DataWay Client Token must use an `env:`, `existing:`, or `runtime:` reference.

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
      "source": "repository",
      "confidence": "high",
      "verification": "pending",
      "api_value": null
    },
    "ios": {
      "value": "ios",
      "source": "repository",
      "confidence": "high",
      "verification": "pending",
      "api_value": null
    },
    "web": {
      "value": "web",
      "source": "user",
      "confidence": "high",
      "verification": "pending",
      "api_value": null
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

`existing_instrumentation.signals` is an array and `profile.signals` is an object on every plan target. The closed optional set is `logs`, `tracing`, `replay`, `webview`, `native_crash`, `anr`, `freeze`, `ui_block`, `remote_config`, and `canvas_replay`; `rum` is the core signal and must be enabled for every planned RUM target. Decisions are booleans, one of `enabled`/`disabled`/`existing`/`omitted`/`preserve`, or an object containing only `status`. Unknown signals and recursively inferred configuration objects are invalid. Enabling an optional capability absent from the baseline is a material review condition.

`artifacts` is empty when release artifacts are irrelevant. Each artifact uses a string or an object with exactly one `status` or `action`; allowed values are `existing`, `preserve`, `disabled`, `omitted`, `generate`, `configure`, and `upload`. Contradictory controls such as `{"status":"existing","upload":true}` are invalid. Generate/configure/upload decisions are material review scope.

The validator derives material review reasons from these structured fields. Do not describe a new optional signal or artifact only in free-form `edits` or `risks`.

Every confirmed slot must have exactly one Application ID reference. Missing IDs are permitted only when target disposition is `blocked` and the missing slots appear in `blockers`. Do not silently reuse one ID.

Every confirmed slot also records one application type. Allowed values are `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`; allowed sources are `user`, `ai_api`, and `repository`. Public DataWay may keep `verification: pending` and `api_value: null` while matching runtime observations remain in the digest-bound control-plane state. Update the plan to `matched`/`mismatched` plus `api_value` only when application metadata changes a stable decision or a user mismatch must be reviewed. DataKit uses `not_applicable`. A user value takes precedence, but `mismatched` is a material review condition.

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
    "action": "preserve",
    "package": "@cloudcare/browser-rum",
    "owner": "CloudCare",
    "version": "existing lockfile version",
    "official_sources": [
      "https://docs.guance.com/real-user-monitoring/web/app-access/"
    ],
    "compatibility": "Preserve the repository-resolved version",
    "verified_at": "2026-08-04"
  },
  "validation": [
    "npm test"
  ],
  "risk": "The initializer could run too late",
  "rollback": "Revert src/rum.ts"
}
```

`target_id` must reference a declared target whose disposition is `planned`. `file` is an exact repository-relative maintained source or configuration path, never generated output, a dependency directory, `.rum`, `.git`, or an Agent/Skill control directory. Implementation validation also rejects symlink traversal outside the worktree. `order` is a unique positive integer. `edits` and `validation` contain non-empty commands or instructions. `dependency_decision.action` is `preserve`, `add`, `upgrade`, `remove`, `none`, or `blocked`.

For an added, upgraded, or preserved official dependency, also record package/repository owner, selected version or constraint, primary-source URLs, compatibility evidence, and verification date in `dependency_decision`.

Approval status is `pending` or `approved`. `basis` is one of:

- `plan_only_request`: the user asked only to plan, audit, or validate, so the plan stays `pending`;
- `explicit_implementation_request`: the user explicitly asked to implement, integrate, repair, or “plan and implement”; a normal core-RUM plan may be `approved` immediately without another Prompt;
- `revision_review`: the user reviewed and approved the exact persisted revision.

`blockers` is always an array. It is empty for an authorized plan. When an explicit implementation request encounters a material-risk or scope decision, keep `status: "pending"`, preserve `basis: "explicit_implementation_request"`, and list every reason in `blockers`.

For a normal one-Prompt implementation request, write:

```json
{
  "status": "approved",
  "basis": "explicit_implementation_request",
  "blockers": [],
  "revision": 1
}
```

Explicit implementation authorization does not cover ambiguous Application ID mapping, user/AI application-type conflict, an overlapping dirty hunk, dependency upgrade/replacement/removal, any new optional signal, release-artifact scope, the built-in testing site or a TLS exception, an unsafe Client Token sink, remote mutation, or a material change to the planned files or behavior. Those cases require a revised plan and `revision_review`.

Record approver/time only when known; never invent them. Increment `revision` whenever the target graph, receiver, SDK choice, signals, privacy behavior, artifacts, or exact edit set changes.

For `revision_review`, also record:

```json
{
  "reviewed_plan_sha256": "sha256:<canonical-plan-digest>",
  "reviewed_overlaps": [
    {
      "file": "src/rum.ts",
      "sha256": "sha256:<reviewed-file-digest>"
    }
  ]
}
```

Set the reviewed revision and `reviewed_overlaps` first, then obtain the canonical plan digest with `validate_contract.py <plan> --print-review-digest` and store that exact output as `reviewed_plan_sha256`. `reviewed_overlaps` is empty unless a planned file was already dirty when the plan was created. For each approved overlap, hash the exact reviewed file bytes; implementation validation accepts it only while that file still has the same digest. A new dirty planned file or post-Review change remains blocked.

Plan schema version 1 is stale under this authorization model. Preserve usable connection-source references, rebuild repository analysis as schema version 2, increment the revision, and request review only when the original request was plan-only or a material blocker remains.

## `.rum/control-plane-state.json`

Public DataWay implementation uses a separate Git-ignored, non-secret execution state:

```json
{
  "schema_version": 1,
  "kind": "rum_control_plane_state",
  "plan_digest": "sha256:<canonical-plan-digest>",
  "site": {
    "code": "cn3",
    "catalog": "https://urls.guance.com/",
    "dataway_url": "https://cn3-openway.guance.com",
    "ai_api": "https://cn3-ai-api.guance.com",
    "tls_verification": "verified"
  },
  "network_preflight": {
    "status": "passed",
    "dataway": {"status": "reachable", "http_status": 404},
    "ai_api": {"status": "reachable", "http_status": 401}
  },
  "credential_resolution": {
    "status": "resolved",
    "exchange_path": "/api/v1/account/accesskey/exchange",
    "application_lookup_path": "/api/v1/rum/app/get",
    "api_key_persistence": "memory_only"
  },
  "applications": {
    "web": {
      "app_id": "web_demo",
      "api_app_type": "web",
      "selected_app_type": "web",
      "selected_app_type_source": "ai_api",
      "type_mismatch": false,
      "token_expired": false,
      "client_token_available": true,
      "network_attempts": 1,
      "observations": {
        "client_token_sync_status": "queued",
        "mapping_status": "pending",
        "mapping_ready": false
      }
    }
  },
  "client_tokens": {
    "web": {
      "source": "runtime:GUANCE_RUM_CLIENT_TOKEN",
      "availability": "persisted"
    }
  }
}
```

Generate `plan_digest` with `validate_contract.py .rum/plan.json --print-review-digest` after finalizing the authorized revision. The state must match the plan's catalog, site code, AI API, Application ID slots, application types, and Client Token references. Token acceptance requires only `token_expired: false`, a present non-empty `client_token` during helper execution, and `client_token_available: true` in this redacted state. Sync/mapping observations never gate implementation and never alter the plan digest.

Validate the pair before editing application code:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json \
  --phase implement \
  --execution-state .rum/control-plane-state.json \
  --repository <repository-root>
```

## `.rum/instrumentation.json`

Use:

```json
{
  "schema_version": 1,
  "generated_from_plan_revision": 1,
  "repository": {
    "root": ".",
    "commit": "<git commit>"
  },
  "receiver": {
    "mode": "public_dataway",
    "endpoint": {
      "source": "template:DATAWAY_URL"
    },
    "client_tokens": {
      "web": {
        "source": "runtime:GUANCE_RUM_CLIENT_TOKEN",
        "availability": "persisted"
      }
    }
  },
  "targets": [
    {
      "id": "web:.",
      "path": ".",
      "platform": "web",
      "variants": ["browser"],
      "evidence": ["src/rum.ts"],
      "application_id_slots": ["web"],
      "application_ids": {
        "web": {
          "source": "runtime:RUM_APPLICATION_ID"
        }
      },
      "application_types": {
        "web": {
          "value": "web",
          "source": "repository",
          "confidence": "high",
          "verification": "matched",
          "api_value": "web"
        }
      },
      "disposition": "instrumented",
      "blockers": []
    }
  ],
  "validation": ["npm test: passed"],
  "artifacts": [],
  "remote_verification": {
    "verified": false,
    "evidence": []
  },
  "handoff": []
}
```

Every discovered target appears exactly once with disposition `existing`, `instrumented`, `skipped`, `blocked`, or `failed`. Existing/instrumented targets require non-empty repository evidence, Application ID/type mappings, and global validation evidence. Skipped/blocked/failed targets require concrete blockers. For existing/instrumented targets record core integration evidence:

- platform variants and Application ID source mapping;
- SDK package/version and primary-source evidence;
- changed and existing source/configuration files;
- initialization lifecycle and single-init proof;
- RUM capability and only those optional Logs, Trace, Replay, WebView, or crash capabilities that existed or were requested;
- service/version/environment sources;
- sampling and trace propagation;
- privacy controls and negative-test evidence;
- Sourcemap/dSYM/R8/native-symbol behavior;
- build/test/smoke evidence and residual gaps.

The inventory must never contain a temporary authorization code, API Key, or Client Token value. `remote_verification.verified` remains false unless the user supplies external console/ingestion evidence.

## Optional `docs/rum-instrumentation.md`

Generate this answer-first projection only when the user asks for durable documentation or the repository already maintains equivalent operational documentation:

1. receiver mode and non-secret source references;
2. target/application coverage;
3. existing and changed initialization;
4. SDK/version decisions and official links;
5. privacy, sampling, Trace, Replay, and artifact decisions;
6. baseline and post-change validation evidence;
7. skipped, blocked, failed, and remotely unverified items;
8. rollback and human handoff.

When generated, keep Markdown and JSON consistent. Correct the JSON inventory first when they disagree.
