---
name: rum-instrument
description: "Plan, audit, implement, repair, and validate Guance RUM across Web, MiniApp, Android, iOS/tvOS/macOS, HarmonyOS, React Native, Flutter, UniApp, C++, and Unity repositories. Use whenever a user mentions Guance RUM, real user monitoring, browser/mobile SDK access, Public DataWay or DataKit RUM delivery, session replay, RUM-to-APM tracing, or asks to review an existing RUM integration—even when they provide only appId plus minimal receiver connection variables."
---

# Guance RUM Instrumentation

Instrument every deployable RUM target through a plan-first, convergent workflow. Keep the user-facing input minimal: receiver connection variables and the matching RUM Application ID are enough to produce a complete plan.

## Boundaries

- Support Web, MiniApp, Android, iOS/tvOS/macOS, HarmonyOS, React Native, Flutter, UniApp, C++, and Unity. Route framework variants such as SSR, Electron, Flutter Web, and UniApp MiniApp to the correct platform adapter.
- Preserve a valid existing integration and converge it instead of adding a second initializer.
- Treat SDK versions, package coordinates, initialization APIs, and feature support as current facts that require verification from official Guance documentation and GuanceCloud repositories.
- Never edit generated output, vendored SDK code, or live Guance resources.
- Never create applications, deploy, upload Sourcemaps/symbols, or make other remote changes unless the user explicitly authorizes that exact action.
- Keep temporary authorization codes, API keys, and server credentials out of client code, tracked files, plans, commands, and responses. Resolve a Public DataWay Client Token through the bundled control-plane helper; never request, read, echo, or persist its value in Agent-visible output.
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
| iOS, tvOS, macOS | [references/apple.md](references/apple.md) |
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
temporaryAuthCode: env:GUANCE_TEMP_AUTH_CODE
appId: {{APP_ID}}
applicationType: {{APPLICATION_TYPE}} # optional
```

DataKit:

```text
datakitUrl: {{DATAKIT_URL}}
appId: {{APP_ID}}
applicationType: {{APPLICATION_TYPE}} # optional
```

Do not put `clientToken` or `aiApiEndpoint` in the standard prompt. Infer the receiver mode from the field names and reject conflicting receiver fields rather than choosing silently. Public DataWay requires `datawayUrl`, a temporary-authorization-code source, and `appId`. DataKit requires `datakitUrl` and `appId`; it does not use the Client Token or AI API flow.

Normalize `{{NAME}}` to `template:NAME` and preserve `env:NAME` as an environment reference. Never resolve or print a credential reference through a general-purpose shell read. The bundled helper reads the temporary code directly from its named environment variable and emits only non-secret metadata plus a runtime Client Token reference.

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

When a user type conflicts with AI API metadata, keep the user type for planning, record the mismatch as a risk, and require confirmation before implementation.

## Workflow

### 1. Establish repository safety

Inspect repository instructions, Git status, current commit, manifests, entry points, generated directories, and discoverable baseline commands. Preserve unrelated work. Stop before editing if an approved hunk overlaps an uncommitted user change.

Interpret verbs explicitly:

- “审查” / “audit” performs read-only analysis.
- “规划” / “plan” writes only `.rum/plan.json` when repository writes are allowed; it does not modify application code.
- “实施” / “接入” / “implement” still requires an approved `.rum/plan.json` revision before application changes.
- “验证” / “validate” is read-only unless the user also asks for repairs.

### 2. Parse the minimal input

Normalize receiver and Application ID sources using [references/common.md](references/common.md). Do not ask for platform, service, version, environment, signals, sampling, tracing, replay, or artifact settings before repository analysis. Infer them and expose every decision in the plan.

If the connection input is missing, continue the audit and mark receiver wiring blocked. Ask for only the missing connection fields after presenting useful repository findings.

For Public DataWay, resolve the site and application metadata with:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <public-dataway-origin> \
  --app-id <application-id> \
  --temporary-auth-code-env GUANCE_TEMP_AUTH_CODE
```

Add `--application-type <type>` when the user supplied it. The helper loads both official site catalogs, matches the Public DataWay origin, uses the catalog's `ai_api`, exchanges the one-time code, calls `/api/v1/rum/app/get`, keeps the API Key in memory, and discards the Client Token after reporting only its availability and runtime reference. Never derive AI API from an Owl endpoint or by rewriting the DataWay hostname.

For a target-keyed `appId` map, repeat `--app-id <slot>=<application-id>` and, when provided, `--application-type <slot>=<type>`. The helper exchanges the temporary code once, looks up every slot with the same in-memory API Key, and keeps a separate Client Token reference for each application.

For an explicitly approved non-production site that is absent from the official catalogs, use a local test catalog with the same top-level `urls` shape:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <test-public-dataway-origin> \
  --app-id <application-id> \
  --temporary-auth-code-env GUANCE_TEMP_AUTH_CODE \
  --test-site-catalog-file <local-test-catalog.json> \
  --insecure-test-tls
```

The test catalog argument is an advanced execution option, not a standard Prompt field. It disables official catalog lookup for that run and still requires an exact DataWay match plus an HTTPS AI API origin. Add `--insecure-test-tls` only when the user explicitly authorizes bypassing certificate verification for that test catalog; it is rejected without `--test-site-catalog-file`. Mark the plan `test_only`, record the catalog as `testing_override`, and never promote either override to production.

During approved implementation, rerun the helper with a fresh one-time code and a dedicated runtime variable:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py \
  --dataway-url <public-dataway-origin> \
  --app-id <application-id> \
  --temporary-auth-code-env GUANCE_TEMP_AUTH_CODE \
  --client-token-env <slot>=<repository-specific-runtime-variable> \
  --client-token-env-file <already-git-ignored-secret-file> \
  --repository <repository-root>
```

For a scalar app, omit `<slot>=` from `--client-token-env`. For a map, repeat it once per slot. The helper refuses an existing file and an in-repository path that Git does not ignore. Do not open, print, diff, stage, or inspect the generated secret file. Wire only the runtime variable names into maintained configuration. Because the authorization code is one-time, request a fresh code for implementation when planning already consumed one.

On a convergent rerun, preserve an existing approved runtime Client Token source and do not invoke the helper again. Its preflight rejects an existing secret sink before reading the temporary-code environment variable or making a network request.

### 3. Detect all targets

Run:

```bash
python3 <skill-dir>/scripts/detect_rum_targets.py <repository> --pretty
```

Treat detector output as evidence, not final authority. Confirm candidates using manifests and runtime entry points. Suppress native subprojects owned by React Native, Flutter, UniApp, or Unity unless they are independently built and initialized.

Build one repository-wide model containing every deployable target, its platform variants, canonical startup surface, existing RUM/Logs/Trace/Replay integration, release metadata sources, privacy boundaries, and validation commands.

### 4. Verify current official integration guidance

For each detected platform, verify the current Guance app-access page, official GuanceCloud repository, package ownership, latest compatible release, runtime/build requirements, initialization lifecycle, receiver fields, and optional capability support. Record URLs and the verification date.

When network access is unavailable, reuse an already locked official SDK only if its provenance is locally verifiable. Otherwise produce a blocked dependency decision instead of inventing a version.

### 5. Infer the profile

Apply the defaults in [references/common.md](references/common.md):

- enable core RUM;
- preserve existing Logs and Trace behavior but do not add absent optional signals silently;
- keep Replay off unless explicitly requested and safely configurable;
- derive `service`, `version`, and `env` from canonical build/runtime sources;
- preserve existing sampling or propose environment-configured, platform-supported values;
- limit trace propagation to verified first-party origins/resources;
- collect no request/response bodies, raw query values, user inputs, or unapproved high-cardinality context.

Record each inferred value with its source and confidence. An unresolved optional value is a handoff item, not a reason to interrogate the user before producing the plan.

### 6. Create the plan and stop

Write `.rum/plan.json` according to [references/contracts.md](references/contracts.md). Include the complete target graph, exact planned files, dependency decisions, receiver mappings, Application ID slots, privacy controls, validation commands, risks, rollback, and approval:

```json
{
  "status": "pending",
  "revision": 1
}
```

Run:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json
```

Present an answer-first summary and stop. Approval covers only that revision and exact edit set. Increment the revision and request another approval when targets, files, receiver mode, SDK choice, signals, privacy behavior, or artifact handling changes materially.

### 7. Implement an approved revision

Before editing, verify that repository identity, commit, dirty-file overlap, manifests, target graph, connection source references, and plan fingerprint still match. Run:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --phase implement
```

Implement in target-sized batches. Edit canonical source and runtime configuration, never generated output. Preserve existing config precedence, application lifecycle, networking behavior, request signing, and user consent flows. Do not duplicate native and framework initialization.

For Public DataWay, implementation remains blocked until the approved runtime Client Token source exists. Obtain it only with the helper workflow above. DataKit implementation must not request a temporary code, resolve an AI API endpoint, or add a Client Token field.

If a newly discovered fact changes the approved edit set, stop, revise the plan, and obtain approval before continuing.

### 8. Validate and deliver

Run the repository's format, build/type-check, unit, integration, and platform-specific checks plus [references/validation.md](references/validation.md). Prove initialization is single and early enough, receiver selection is correct, prohibited data is absent, trace propagation is allowlisted, requests remain unchanged, Replay is gated, and release artifacts match the build.

Write:

- `.rum/instrumentation.json`
- `docs/rum-instrumentation.md`

Record every target exactly once as `existing`, `instrumented`, `skipped`, `blocked`, or `failed`. Keep remote verification false unless the user supplies external evidence.

## Response format

For planning, report:

1. receiver mode and source references, without values;
2. detected targets and required Application ID slots;
3. existing integration findings;
4. inferred profile with evidence/confidence;
5. exact planned changes and validation;
6. privacy, compatibility, and rollout risks;
7. plan revision awaiting approval.

For implementation, report changed files, local validation evidence, unresolved runtime/remote steps, and the generated inventory. Clearly distinguish local proof from remotely verified ingestion.
