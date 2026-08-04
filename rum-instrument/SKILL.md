---
name: rum-instrument
description: "Plan, audit, implement, repair, and validate Guance RUM across Web, MiniApp, Android, iOS/tvOS, macOS, HarmonyOS, React Native, Flutter, UniApp, C++, and Unity repositories. Use whenever a user mentions Guance RUM, real user monitoring, browser/mobile SDK access, Public DataWay or DataKit RUM delivery, session replay, RUM-to-APM tracing, or asks to review an existing RUM integration—even when they provide only appId plus minimal receiver connection variables."
---

# Guance RUM Instrumentation

Instrument every deployable RUM target through a plan-first, convergent workflow. Keep the user-facing input minimal: receiver connection variables and the matching RUM Application ID are enough to produce a complete plan.

## Boundaries

- Support Web, MiniApp, Android, iOS/tvOS, macOS, HarmonyOS, React Native, Flutter, UniApp, C++, and Unity. Route framework variants such as SSR, Electron, Flutter Web, and UniApp MiniApp to the correct platform adapter.
- Preserve a valid existing integration and converge it instead of adding a second initializer.
- Treat SDK versions, package coordinates, initialization APIs, and feature support as current facts that require verification from official Guance documentation and GuanceCloud repositories.
- Never edit generated output, vendored SDK code, or live Guance resources.
- Never create applications, deploy, upload Sourcemaps/symbols, or make other remote changes unless the user explicitly authorizes that exact action.
- Keep temporary authorization codes, API keys, and server credentials out of client code, tracked files, plans, commands, and responses. A Public DataWay Client Token is client-visible restricted configuration, not a server secret; still route it through the bundled helper and never echo, inspect, or persist its value in Agent-visible output or Git.
- Default Session Replay to off. Enable it only when the selected platform supports it and the approved plan defines consent, masking, excluded views/routes, and sampling.
- Do not claim remote ingestion from SDK initialization logs or local requests. Remote verification remains false without external evidence.

## Required references

Before analysis or modification, read:

- [references/execution.md](references/execution.md)
- [references/common.md](references/common.md)
- [references/contracts.md](references/contracts.md)
- [references/privacy-security.md](references/privacy-security.md)
- [references/validation.md](references/validation.md)

For Public DataWay, also read [references/control-plane.md](references/control-plane.md).

After target detection, read every matching platform file:

| Detected target | Reference |
|---|---|
| Web, SPA, MPA, SSR, Electron, Flutter Web | [references/web.md](references/web.md) |
| Native MiniApp or MiniApp framework | [references/miniapp.md](references/miniapp.md) |
| Android | [references/android.md](references/android.md) |
| `apple` target with iOS/tvOS variants | [references/apple.md](references/apple.md) |
| `apple` target with a macOS variant | [references/macos.md](references/macos.md) |
| HarmonyOS | [references/harmonyos.md](references/harmonyos.md) |
| React Native | [references/react-native.md](references/react-native.md) |
| Flutter Android/iOS | [references/flutter.md](references/flutter.md) |
| UniApp | [references/uniapp.md](references/uniapp.md) |
| C++ | [references/cpp.md](references/cpp.md) |
| Unity | [references/unity.md](references/unity.md) |

## Minimal input contract

Accept YAML-like fields embedded in natural-language prompts. Do not require a separate config file.

Public DataWay:

```text
datawayUrl: {{DATAWAY_URL}}
appId: {{APP_ID}}
applicationType: {{APPLICATION_TYPE}} # optional
temporaryAuthCode: <paste for one-prompt implementation or provide after plan review> # optional during planning
```

DataKit:

```text
datakitUrl: {{DATAKIT_URL}}
appId: {{APP_ID}}
applicationType: {{APPLICATION_TYPE}} # optional
```

Do not put `clientToken` or `aiApiEndpoint` in the standard prompt. Infer the receiver mode from the field names and reject conflicting receiver fields rather than choosing silently. Public DataWay planning requires `datawayUrl` and `appId`; implementation additionally requires a temporary authorization code. Accept the one-time code directly in `temporaryAuthCode` for a one-Prompt run or from a later user message, and keep `env:NAME` for automation. Do not consume the code until the plan has passed plan-phase validation and implementation is authorized. DataKit requires `datakitUrl` and `appId`; it does not use the Client Token or AI API flow.

Normalize `{{NAME}}` to `template:NAME`, preserve `env:NAME` as an environment reference, and normalize a literal or separately pasted authorization code to `prompt:provided` without copying its value into the plan. During authorized implementation, pass a prompt-provided code to the helper through process stdin; terminal input is hidden when a TTY is available. Never place it in a command argument, temporary file, plan, or response.

Accept a scalar `appId` when exactly one independently deployable RUM application is in scope. For multiplatform targets, accept a map:

```yaml
appId:
  web: "{{WEB_APP_ID}}"
  android: "{{ANDROID_APP_ID}}"
  ios: "{{IOS_APP_ID}}"
```

Do not fan one scalar ID out to multiple independent applications. Generate a blocked plan and ask only for the unresolved platform IDs.

`applicationType` is optional and accepts the same scalar or target-keyed shape. Resolve each slot in this order:

1. user-provided `applicationType`;
2. AI API `app_type` for Public DataWay;
3. repository detection when control-plane metadata is unavailable, including DataKit.

When a user type conflicts with AI API metadata, keep the user type for planning, record the mismatch as a blocker, and require revision review before implementation.

## Workflow

### 1. Establish repository safety

Inspect repository instructions, Git status, current commit, manifests, entry points, generated directories, and discoverable baseline commands. Preserve unrelated work. Do not edit a dirty planned file under ordinary explicit authorization. A user may approve an exact pre-existing overlap through Revision Review only when the plan records both the canonical plan digest and the reviewed file digest; any later byte change invalidates that approval.

Interpret verbs explicitly:

- “审查” / “audit” performs read-only analysis.
- “规划” / “plan” writes only `.rum/plan.json` when repository writes are allowed; it does not modify application code.
- “实施” / “接入” / “修复” / “implement” / “integrate” / “repair” authorizes normal core-RUM repository changes. Create and validate `.rum/plan.json`, then continue in the same run when no review blocker exists.
- “规划并实施” has the same implementation authorization; do not stop merely to ask for routine plan approval.
- “验证” / “validate” is read-only unless the user also asks for repairs.

Do not ask for an `approvalMode` field. Infer plan-only versus implementation authorization from these verbs.

### 2. Parse the minimal input

Normalize receiver and Application ID sources using [references/common.md](references/common.md). Do not ask for platform, service, version, environment, signals, sampling, tracing, replay, or artifact settings before repository analysis. Infer them and expose every decision in the plan.

If the connection input is missing, continue the audit and mark receiver wiring blocked. Ask for only the missing connection fields after presenting useful repository findings.

For Public DataWay planning, resolve only the official site catalog:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <public-dataway-origin> \
  --site-only
```

This verifies the exact `openway` match and records the catalog-provided AI API without consuming credentials. Never derive AI API from Owl or hostname rewriting. Keep non-production catalog and TLS exceptions in [references/control-plane.md](references/control-plane.md); use them only after explicit test authorization.

During authorized implementation, call the application API once and write its Client Token directly to the reviewed runtime sink:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <public-dataway-origin> \
  --app-id <application-id> \
  --temporary-auth-code-stdin \
  --client-token-env <slot>=<repository-specific-runtime-variable> \
  --client-token-env-file <already-git-ignored-secret-file> \
  --metadata-file <new-non-secret-resolution-json> \
  --repository <repository-root>
```

For direct Prompt input, send the code through the subprocess stdin channel without embedding it in the shell command; use `--temporary-auth-code-env NAME` only for automation. For a scalar app, omit `<slot>=` from `--client-token-env`. For a map, repeat `--app-id`, `--application-type`, and `--client-token-env` per repository-wide unique slot.

The helper exchanges the code once, validates that the Client Token is not expired and that token synchronization and application mapping are ready, then transactionally writes a new mode-`0600` environment-assignment sink and a separate non-secret metadata file. It requires both outputs, requires `--repository`, rejects a non-ignored in-repository sink, requires `--allow-external-secret-sink` for a reviewed external sink, refuses output-path collisions, and removes the new secret sink if metadata persistence fails. Do not open, print, diff, stage, or inspect the generated secret file.

Read only the non-secret metadata file. Update the same plan to `control_plane.status: resolved`, mark Client Token references `persisted`, and set each application type to `matched` or `mismatched` with `api_value`. User-defined type remains the selected value; without one, the AI API value takes precedence over repository inference. Revalidate the resolved plan before any application-code edit. A mismatch or another material change requires Revision Review.

The helper's dotenv-shaped output is a transport into an existing reviewed runtime/build configuration path, not proof that every platform supports process environment variables. Do not add a new dotenv loader or embed the value into native source merely to consume it. If the repository lacks a safe existing build/runtime injection path, keep implementation blocked and hand off value injection.

On a convergent rerun, preserve an existing reviewed runtime Client Token source and do not invoke the helper again. Recover application metadata from the non-secret metadata file. Its preflight rejects an existing secret sink before reading the temporary-code environment variable or making a network request.

### 3. Detect all targets

Run:

```bash
python3 <skill-dir>/scripts/detect_rum_targets.py <repository> --pretty
```

Pass the Git worktree root as `<repository>`. The detector prefers Git-tracked and non-ignored files. When the user explicitly limits the task to a repository subdirectory, add `--scope <repository-relative-directory>`; do not pass that subdirectory as the repository root. Otherwise scan the repository once. Treat detector output as evidence, not final authority. Confirm candidates using manifests and runtime entry points. Suppress native subprojects owned by React Native, Flutter, UniApp, or Unity unless they are independently built and initialized.

Build one repository-wide model containing every deployable target, its platform variants, canonical startup surface, existing core RUM integration, release metadata sources, privacy boundaries, and validation commands. Treat framework dependencies without a deployable entry point, Android library modules, and Flutter packages without `lib/main.dart` plus a platform directory as non-target evidence. Split Xcode Application ID slots when one project contains multiple application targets. Include optional signals and artifacts only when detected or requested.

### 4. Verify current official integration guidance

For each detected platform, verify the current Guance app-access page, official GuanceCloud repository, package ownership, latest compatible release, runtime/build requirements, initialization lifecycle, receiver fields, and optional capability support. Record URLs and the verification date.

When network access is unavailable, reuse an already locked official SDK only if its provenance is locally verifiable. Otherwise produce a blocked dependency decision instead of inventing a version.

### 5. Infer the core profile

Apply the defaults in [references/common.md](references/common.md):

- enable core RUM once at the canonical startup point;
- derive receiver, Application ID, `service`, `version`, `env`, and sampling from maintained runtime/build sources;
- collect no request/response bodies, raw query values, user inputs, or unapproved high-cardinality context.

Analyze Logs, Trace, Replay, WebView, native crash/ANR/freeze/UI-block capture, Remote Config, Canvas Replay, Sourcemaps, and native symbols only when the repository already uses them or the user requests them. Preserve existing behavior; do not add an absent optional signal silently. Replay remains off by default and Trace propagation remains allowlisted. Record only decisions relevant to the detected target.

### 6. Create and authorize the plan

Write `.rum/plan.json` according to [references/contracts.md](references/contracts.md). Initial Public DataWay plans use `control_plane.status: catalog_resolved` and mark new runtime Client Token references `availability: planned`; preserve an already reviewed sink as `availability: existing`. Authorized implementation updates the plan to `resolved` from the helper's non-secret metadata before code edits. Include the target graph, exact planned files, core receiver/profile decisions, applicable advanced decisions, validation, risks, rollback, and intent-aware approval.

Choose the approval object from the user's intent:

- Plan, audit, and read-only validation: `status: pending`, `basis: plan_only_request`, `blockers: []`. Validate, summarize, and stop.
- Explicit implementation or repair with ordinary core-RUM changes: `status: approved`, `basis: explicit_implementation_request`, `blockers: []`. Validate, then continue directly to step 7 in the same run.
- Explicit implementation with a material review condition: `status: pending`, `basis: explicit_implementation_request`, and concrete `blockers`. Validate, summarize the decision needed, and stop.

Material review conditions include ambiguous Application IDs, application-type conflict, dirty overlap, SDK upgrade/replacement/removal, any new optional signal (including Logs/Trace/Replay/WebView/native crash/ANR/freeze/UI-block/Remote Config/Canvas Replay), release-artifact scope, test catalog/TLS exceptions, an unsafe Token sink, remote mutations, and material target/file/behavior drift. Record optional capabilities in `profile.signals`, their existing baseline in `existing_instrumentation.signals`, and release decisions in `artifacts`; the contract validator uses those structured fields to prevent explicit implementation intent from bypassing Review. Follow the complete list in [references/execution.md](references/execution.md).

Run:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json
```

Every authorization is bound to the validated revision and exact edit set. For Revision Review, record `approval.reviewed_plan_sha256` from `validate_contract.py .rum/plan.json --print-review-digest` and `reviewed_overlaps` as defined in the contract. Increment the revision and require `revision_review` when targets, files, receiver mode, SDK choice, signals, privacy behavior, or artifact handling changes materially. Do not pause a normal explicit implementation request merely because the plan artifact was just created.

### 7. Implement an authorized revision

Before editing, verify repository identity, commit, dirty-file overlap, target evidence, and connection source references. Run:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json \
  --phase implement \
  --repository <repository-root>
```

Implement in target-sized batches. Edit canonical source and runtime configuration, never generated output. Preserve existing config precedence, application lifecycle, networking behavior, request signing, and user consent flows. Do not duplicate native and framework initialization.

For Public DataWay, implementation remains blocked until the helper result is persisted, `control_plane.status` is `resolved`, every application type is verified, and the reviewed runtime Client Token source exists. Obtain it only with the helper workflow above, after plan validation. DataKit implementation must not request a temporary code, resolve an AI API endpoint, or add a Client Token field; it also remains blocked until the RUM collector and runtime-to-DataKit network reachability are both verified with evidence.

If a newly discovered fact materially changes the authorized edit set, stop, revise the plan, and obtain revision review before continuing.

### 8. Validate and deliver

Run the repository's format, build/type-check, unit, integration, and platform-specific checks plus [references/validation.md](references/validation.md). Prove initialization is single and early enough, receiver selection is correct, prohibited data is absent, and requests remain unchanged. Validate Trace, Replay, WebView, and release artifacts only when they are in the authorized scope.

Write `.rum/instrumentation.json` and validate it:

```bash
python3 <skill-dir>/scripts/validate_contract.py \
  .rum/instrumentation.json \
  --kind instrumentation
```

Record every target exactly once as `existing`, `instrumented`, `skipped`, `blocked`, or `failed`. Keep remote verification false unless the user supplies external evidence.

Generate `docs/rum-instrumentation.md` only when the user requests durable documentation or the repository already maintains equivalent operational docs. The final response is otherwise the human-readable projection of the inventory.

## Response format

For planning, report:

1. receiver mode and source references, without values;
2. detected targets and required Application ID slots;
3. existing integration findings;
4. inferred profile with evidence/confidence;
5. exact planned changes and validation;
6. privacy, compatibility, and rollout risks;
7. authorization state: pending plan review, pending blocker review, or authorized implementation.

For plan-only requests, stop after the planning report. For implementation, report changed files, local validation evidence, unresolved runtime/remote steps, and the generated inventory. Clearly distinguish local proof from remotely verified ingestion.
