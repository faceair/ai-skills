---
name: rum-instrument
description: "Plan, audit, implement, repair, and validate Real User Monitoring across Web, MiniApp, Android, iOS/tvOS, macOS, HarmonyOS, React Native, Flutter, UniApp, C++, and Unity repositories. Use for browser/mobile RUM access, Public DataWay or DataKit delivery, Session Replay, RUM-to-APM tracing, or an existing RUM integration review—even when the user supplies only an Application ID and receiver variables."
---

# RUM Instrumentation

Instrument every deployable target through one convergent, plan-first workflow. Keep user input minimal and infer repository-specific details from maintained code and configuration.

## Non-negotiable boundaries

- Preserve one valid initializer; never add a parallel integration.
- Edit maintained source only. Do not edit generated output or vendored SDKs.
- Verify current SDK versions and APIs from primary sources before changing dependencies or initialization.
- Keep authorization codes, API Keys, and Client Token values out of tracked files, plans, commands, logs, diffs, and responses.
- Keep Session Replay off unless explicitly requested and privacy-reviewed.
- Do not perform console mutations, deployment, or artifact upload without exact authorization.
- Do not claim remote ingestion from local HTTP success or SDK debug output.

## Load references progressively

Read only what the current phase needs:

1. Read [references/common.md](references/common.md) to normalize input and targets.
2. Read [references/execution.md](references/execution.md) before writing a plan or application files.
3. Read [references/contracts.md](references/contracts.md) only when creating or validating `.rum/plan.json`.
4. Read [references/control-plane.md](references/control-plane.md) only for Public DataWay.
5. After detection, read each matching platform reference listed below.
6. Read [references/privacy-security.md](references/privacy-security.md) when custom data, Trace, Replay, WebView, or release artifacts are present or requested.
7. Read [references/validation.md](references/validation.md) before final verification.

| Target | Reference |
|---|---|
| Web, SPA, MPA, SSR, Electron, Flutter Web | [references/web.md](references/web.md) |
| MiniApp | [references/miniapp.md](references/miniapp.md) |
| Android | [references/android.md](references/android.md) |
| iOS/tvOS | [references/apple.md](references/apple.md) |
| macOS | [references/macos.md](references/macos.md) |
| HarmonyOS | [references/harmonyos.md](references/harmonyos.md) |
| React Native | [references/react-native.md](references/react-native.md) |
| Flutter mobile | [references/flutter.md](references/flutter.md) |
| UniApp | [references/uniapp.md](references/uniapp.md) |
| C++ | [references/cpp.md](references/cpp.md) |
| Unity | [references/unity.md](references/unity.md) |

## Minimal prompt

Accept YAML-like fields in natural language.

Public DataWay:

```yaml
datawayUrl: {{DATAWAY_URL}}
appId: {{APP_ID}}
temporaryAuthCode: <one-time code> # required only for implementation
applicationType: web              # optional
```

DataKit:

```yaml
datakitUrl: {{DATAKIT_URL}}
appId: {{APP_ID}}
applicationType: web # optional
```

For multiple independently deployed applications, accept target-keyed `appId` and `applicationType` maps. Never copy one scalar ID across multiple slots.

Do not request `clientToken`, `aiApiEndpoint`, platform, service, version, environment, sampling, tracing, or replay before repository analysis. Infer receiver mode from `datawayUrl` versus `datakitUrl` and reject conflicting URL families.

Accept a literal `temporaryAuthCode` directly in one Prompt. Redact it to `prompt:provided`, pass it to the helper through stdin after authorization, and never repeat it. Keep `env:RUM_TEMP_AUTH_CODE` only as an automation option.

Resolve application type in this order:

1. user value;
2. Public DataWay application API metadata;
3. repository evidence.

Require review when a user value conflicts with API metadata.

## Workflow

### 1. Inspect safely

Read repository instructions, Git status, commit, manifests, entry points, existing RUM code, generated paths, and documented validation commands. Preserve unrelated work.

Interpret intent:

- Audit/validate: remain read-only unless repair is requested.
- Plan: write only `.rum/plan.json` when writes are allowed, then stop.
- Implement/integrate/repair: create and validate the plan, then continue in the same run when no material blocker exists.

Do not require a routine second approval for explicit implementation. Require Revision Review only for ambiguous IDs, application-type conflict, pre-existing dirty overlap, dependency replacement/upgrade/removal, new optional signals, release artifacts, test-only TLS/site behavior, external Token sinks, remote mutation, or material scope drift.

### 2. Detect targets

Run:

```bash
python3 <skill-dir>/scripts/detect_rum_targets.py <repository-root> --pretty
```

Use `--scope <relative-directory>` only for an explicit subdirectory scope. Confirm detector candidates from real manifests and startup paths. Treat wrapper-owned native projects as one logical target unless repository evidence proves independent deployment.

Read the matching platform references and the corresponding entry in `references/official-sources.json`. Verify current APIs and compatibility before choosing a dependency change.

### 3. Build and validate the plan

Infer core RUM, receiver mapping, Application ID mapping, service/version/environment sources, and repository validation. Preserve existing optional signals; do not enable absent Logs, Trace, Replay, WebView, crash capture, remote config, or artifact upload silently.

Write `.rum/plan.json` using [references/contracts.md](references/contracts.md), then run:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --kind plan --phase plan
```

Keep the plan stable when only network, credential, Token persistence, or mapping observations change.

### 4. Resolve Public DataWay configuration

During planning, resolve only the site:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <origin> \
  --site-only
```

During planning, record the exact non-secret sink path, format, scope, and slot keys. During authorized implementation, use that existing or new Git-ignored runtime/build configuration file that the target already knows how to consume. Choose `dotenv`, `json`, `properties`, or `xcconfig`; do not add a dotenv loader to a native application.

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <origin> \
  --app-id <slot>=<application-id> \
  --temporary-auth-code-stdin \
  --client-token-key <slot>=<runtime-key> \
  --client-token-sink <git-ignored-config-file> \
  --sink-format <dotenv|json|properties|xcconfig> \
  --state-file <git-ignored-state-file> \
  --plan-digest <canonical-plan-digest> \
  --repository <repository-root>
```

The helper performs credential-free network preflight before reading the code, exchanges the code once, looks up each application once, and accepts a Token only when `token_expired` is exactly `false` and `client_token` is present. It retries only transient lookup transport failures and never polls mapping state.

The helper atomically creates or updates the reviewed sink, preserves unrelated keys, sets mode `0600`, and writes separate non-secret state. If state persistence fails, it restores the previous sink. Never open or print the sink.

Before application-code edits, validate the plan/state pair:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json \
  --phase implement \
  --execution-state <state-file> \
  --repository <repository-root>
```

Require the state to match the plan digest, concrete Application IDs, application types, runtime keys, sink path/format, Git-ignore status, and file mode.

### 5. Implement

Initialize core RUM once at the canonical startup point. Preserve lifecycle, config precedence, networking, signing, retries, consent, and framework ownership. Use Public DataWay Client Token configuration only in Public DataWay mode. DataKit never uses the application API, authorization code, API Key, or Client Token.

For DataKit, allow local implementation when collector or runtime reachability is unknown. Record those checks as warnings and handoff; they gate only a claim of successful remote ingestion.

### 6. Validate and deliver

Run repository format, build/type-check, unit, integration, packaging, and a representative local smoke test. Prove single initialization, correct receiver branch, safe data collection, and unchanged application requests.

Write `.rum/instrumentation.json` only when the user requests a durable machine-readable inventory or the repository already maintains one. Otherwise provide the same evidence in the final response. Keep remote verification false without external ingestion evidence.

Report changed files, local proof, warnings/handoff, rollback, and whether ingestion was remotely verified.
