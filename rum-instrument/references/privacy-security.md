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

Application IDs and receiver URLs are configuration. Temporary authorization codes and API Keys are credentials. Public DataWay Client Tokens are delivered to clients by design, but the Skill still treats their values as restricted:

- read a temporary authorization code only inside the bundled helper from its named environment variable;
- keep the exchanged API Key only in helper-process memory;
- route the Client Token directly to an approved secret env file or deployment secret sink;
- preserve only `env:`, `runtime:`, or existing configuration references in plans and reports;
- do not echo, print, diff, stage, screenshot, or otherwise inspect credential values or the generated secret file;
- never place a credential in command arguments, tracked source, fixtures, logs, or metadata.

The helper refuses to overwrite a secret file and refuses an in-repository sink that Git does not ignore. If the repository has no safe runtime/build-time configuration source, keep implementation blocked and leave value injection to the human deployment system.

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
