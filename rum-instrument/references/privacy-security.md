# Privacy and security policy

## Data minimization

Default to collecting operational RUM fields only. Do not add:

- request or response bodies;
- authorization headers, cookies, session tokens, or credentials;
- raw URL queries, fragments, presigned URLs, object keys, or user info;
- form values, search text, editor content, DQL/query text, clipboard data, or file paths;
- email, phone, name, account ID, workspace name, or business identifiers without an explicit allowlist;
- unbounded custom Action/context values.

Review existing custom context and Action payloads even when the SDK integration itself is valid. Replace broad objects such as request parameters with bounded categorical fields or approved opaque identifiers.

## Receiver credentials

Application IDs and receiver URLs are configuration. A temporary authorization code is one-time input that the user may provide directly to the Agent. API Keys are server credentials. Public DataWay Client Tokens are delivered to client applications by design and therefore are not confidential from end users; the Skill treats them as restricted client configuration so they do not leak unnecessarily into Agent context, logs, Git history, or unrelated artifacts:

- accept a temporary authorization code directly from the Prompt or a later user message, but never repeat it;
- pass a prompt-provided code to the bundled helper through process stdin; disable terminal echo when a TTY is available, and keep a named environment variable as the optional automation path;
- keep the exchanged API Key only in helper-process memory;
- route the Client Token directly to a reviewed environment-assignment/build configuration sink;
- preserve only the redacted `prompt:provided` marker, `env:`, `runtime:`, or existing configuration references in plans and reports;
- do not echo, print, diff, stage, screenshot, or otherwise inspect credential values or the generated secret file;
- never place a real authorization code, API Key, or Client Token in command arguments, tracked source, fixtures, logs, or execution state.

The helper refuses to overwrite a restricted configuration file, requires separate digest-bound recoverable state, rolls back a newly written Client Token sink if state persistence fails, and refuses in-repository Token/state files that Git does not ignore. Its dotenv-shaped output does not justify adding a dotenv loader to native code. If the repository has no safe existing runtime/build-time injection source, keep implementation blocked and leave value injection to the human deployment system.

An insecure TLS context is permitted only for an explicitly approved test-site catalog. Keep that context scoped to AI API requests in the helper, preserve verified TLS for official catalogs, and never persist certificate errors or credential-bearing response content.

## Trace propagation

Trace headers change outbound requests and can expose topology or break signing/CORS. Before enabling:

1. enumerate API origins/resources actually used by the target;
2. allowlist only verified first-party receivers;
3. preserve an existing propagation format unless an approved migration exists;
4. verify CORS/preflight, signing, retries, redirects, and caching remain correct;
5. add a negative test proving no trace header reaches an unlisted origin.

Do not derive an allowlist from arbitrary runtime destinations or `*`.

## Session Replay

Replay remains off unless all are true:

- the platform and selected SDK version support it;
- user consent or an existing approved consent mechanism is identified;
- inputs, text, images/canvas, WebView/native views, and sensitive components have explicit masking rules;
- authentication, payment, administration, support, editor, healthcare, and other sensitive routes/views are reviewed and excluded when needed;
- sampling, storage/retention expectations, and performance impact are approved;
- start/stop behavior follows consent and account/session transitions.

Canvas/image capture requires separate approval because masking DOM text does not prove visual privacy.

## Sourcemaps and native symbols

Sourcemaps, dSYM, R8/ProGuard mappings, native symbols, and Unity artifacts can expose source or build metadata. Keep upload credentials out of the repository. Verify that artifacts:

- are produced from the same release version/build ID as telemetry;
- are not shipped publicly by mistake;
- use the current official upload mechanism;
- are uploaded only after explicit authorization;
- have a documented retention and rollback path.

Credential-like values found in comments or disabled examples are findings, not reusable configuration.

## Negative-test canaries

Use synthetic, non-secret canaries for:

- input text;
- query parameter and dynamic path;
- authorization/cookie value;
- request payload field;
- custom context/action field;
- excluded Replay component.

Inspect exported/local-capture payloads when possible and assert no canary appears. Separately prove that the application request and user-visible behavior remain unchanged.
