# Common RUM model

## Minimal connection normalization

Use these exact inference rules:

| Supplied fields | Receiver mode | Normalized endpoint |
|---|---|---|
| `datawayUrl`, `temporaryAuthCode`, `appId` | `public_dataway` | `receiver.endpoint` from `datawayUrl` |
| `datakitUrl`, `appId` | `datakit` | `receiver.endpoint` from `datakitUrl` |

Reject multiple URL field families. Do not infer Public DataWay versus DataKit from a generic URL. `clientToken` and `aiApiEndpoint` are not standard-prompt inputs.

Normalize sources:

- `{{NAME}}` → `template:NAME`
- `env:NAME` → `env:NAME`
- an existing repository variable → `existing:<path-or-config-key>`
- a literal non-secret URL/Application ID → a plan value with provenance `user`

Treat `temporaryAuthCode` as a credential source. Prefer `env:GUANCE_TEMP_AUTH_CODE`; never store its value in a plan, command argument, tracked file, or response.

For Public DataWay, use [control-plane.md](control-plane.md) and the bundled helper. Store the resolved Client Token only as an `env:`, `runtime:`, or already-existing configuration reference. A `template:CLIENT_TOKEN` source is invalid because the Agent must obtain the value through the control-plane flow.

An explicitly approved test-site catalog is execution metadata, not a standard Prompt field. Record it as `catalog: testing_override`, keep its location as an `env:` or `existing:` source reference, and mark the control-plane resolution `test_only`.

Record whether `appId` was supplied as a scalar or map in `request.application_id_input`; this preserves enough provenance for deterministic cardinality validation without storing a secret.

## Application ID slots

The detector proposes slots; repository inspection confirms them.

| Target | Typical slots |
|---|---|
| Web | `web` |
| MiniApp | one slot per independently released MiniApp |
| Android | `android` |
| iOS/tvOS/macOS | one slot per independent Apple application |
| HarmonyOS | `harmonyos` |
| React Native | `android`, `ios` |
| Flutter mobile | `android`, `ios` |
| Flutter Web | `web` using Browser RUM |
| UniApp Native | `android`, `ios` |
| UniApp MiniApp | MiniApp-specific slot |
| C++ | one slot per independently shipped executable/application |
| Unity | `android`, `ios` |

A scalar `appId` is valid only when one independent slot remains after target confirmation. Do not copy it across platforms. When IDs are missing, complete the rest of the plan and mark only those targets `blocked`.

## Platform-field mapping

The user-facing names are stable while SDK names differ. Each platform adapter maps:

- `appId` to the SDK's application identifier;
- `datawayUrl` to the current SDK's Public DataWay site/server field;
- the helper-created runtime Client Token reference to the current SDK's Public DataWay client-token field;
- `datakitUrl` to the exact current local receiver field.

Verify the mapping against the selected SDK version. Do not assume Web's `site` or `datakitOrigin` names apply to native SDKs.

## Application type resolution

Resolve each Application ID slot in this order:

1. user-provided `applicationType`;
2. Public DataWay AI API `app_type`;
3. repository evidence.

Record the selected `value`, `source` (`user`, `ai_api`, or `repository`), and `confidence`. DataKit normally uses user input or repository evidence because it has no AI API control-plane flow.

## Inferred profile

Infer rather than ask before planning:

| Setting | Inference order | Safe fallback |
|---|---|---|
| `service` | existing RUM config → deployable package/module/bundle identity | stable target ID |
| `version` | existing release config → package/build version source | runtime-configured placeholder |
| `env` | existing RUM/deployment environment source | runtime-configured placeholder |
| core RUM | preserve valid existing state | enabled |
| Logs | preserve existing | disabled |
| Trace | preserve existing verified propagation | disabled with a plan recommendation |
| Replay | preserve only with consent/masking evidence | disabled |
| sampling | existing environment-driven values | platform-supported, environment-driven proposal |
| user/context fields | existing reviewed allowlist | none |
| remote config | preserve verified existing behavior | disabled |
| Sourcemap/symbol upload | preserve verified release pipeline | plan only, no upload |

For every inference record:

```json
{
  "value": "<value or null>",
  "source": "<repository evidence or proposed runtime source>",
  "confidence": "high|medium|low"
}
```

Do not freeze a guessed production environment, local Git commit, developer machine path, or test version in client code.

## Existing-integration convergence

Search manifests and source for Guance SDK packages, `DATAFLUX_RUM`, `datafluxRum`, `FTMobileSDK`, `FTSDK`, RUM configuration builders, Session Replay calls, custom actions/context, trace headers, and release symbol upload.

For each existing initializer answer:

- Is it executed once and before the events it intends to capture?
- Is its receiver branch mutually exclusive and complete?
- Are `service`, `version`, and `env` tied to release/runtime sources?
- Are sampling and optional signals intentional?
- Are custom fields bounded and privacy-reviewed?
- Does framework code duplicate a native initializer?
- Does a secondary HTML/entry path contain a drifted copy?
- Is SDK load failure observable and recoverable without breaking the app?

Prefer extracting a shared configuration or facade when multiple maintained entry points must behave identically. Do not refactor unrelated application code.

## Capability defaults

RUM is universal across supported adapters, but automatic views/actions/resources, WebView, native crash capture, Replay, remote configuration, and symbol tooling vary. Treat every optional capability as platform- and version-gated. Read the platform reference and current official documentation before planning it.
