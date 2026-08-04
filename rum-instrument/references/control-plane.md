# Public DataWay control plane

Use this flow only for Public DataWay. DataKit sends to the user-supplied DataKit receiver and never needs a Client Token, temporary authorization code, API Key, or AI API lookup.

## Authoritative endpoint resolution

Load both official catalogs configured in the helper.

Each catalog returns a top-level `urls` object. Match the normalized user `datawayUrl` origin to an entry's `openway` origin and take `ai_api` from the same entry. Accept only the documented default Web RUM alias encoded in the helper.

Do not:

- derive AI API by replacing hostname labels;
- use `OWL_REGISTRY_ENDPOINT` or an installed Owl configuration as the source;
- accept `aiApiEndpoint` in the standard prompt;
- choose a site from a partial, suffix, or nearest-looking hostname match.

If no exact catalog entry or documented alias matches, block Public DataWay credential resolution. Report the unmatched non-secret origin and the catalogs checked. Do not fall back to a guessed endpoint.

## Built-in testing site

The helper has exactly one testing mapping:

- DataWay: `http://testing-openway.dataflux.cn`
- AI API: `https://testing-ft2x-ai-api.dataflux.cn`

Match the DataWay origin exactly. Do not accept another testing AI API, read operational configuration from `evals/`, fall back to an arbitrary file, or rewrite a hostname. Certificate validation remains enabled by default; `--insecure-test-tls` is scoped to this built-in site and remains an explicit test-only Review decision.

Represent the testing site in the stable plan with:

```json
{
  "status": "catalog_resolved",
  "catalog": "builtin_testing",
  "site_code": "testing",
  "ai_api_endpoint": {
    "value": "https://testing-ft2x-ai-api.dataflux.cn"
  },
  "test_only": true,
  "tls_verification": "disabled_for_testing"
}
```

Use `tls_verification: verified` when the test AI API certificate is trusted. Never carry the catalog override, disabled certificate verification, or a test DataWay into a production plan.

## Credential and application lookup

The temporary authorization code is a one-time value generated for the current account and workspace. It is not required or consumed during planning. For authorized implementation, accept it directly from the initial Prompt or a later user message and pass it to the helper process through `--temporary-auth-code-stdin`; the helper disables terminal echo when stdin is a TTY and also accepts Agent-managed process stdin. Keep `--temporary-auth-code-env NAME` as an optional source for automation. Never put the literal code in a shell command argument, shell expansion, temporary file, plan, execution state, log, or response.

1. Exchange it without a `DF-API-KEY` header:

   ```text
   POST <ai_api>/api/v1/account/accesskey/exchange
   Content-Type: application/json

   {"code":"<temporary-code>"}
   ```

2. Keep `data.item.sk` only in helper-process memory.
3. Look up the application:

   ```text
   POST <ai_api>/api/v1/rum/app/get
   Content-Type: application/json
   DF-API-KEY: <in-memory-api-key>

   {"app_id":"<application-id>"}
   ```

4. Accept the Token only when `token_expired` is exactly `false` and `client_token` is present and non-empty.
5. Treat `client_token_sync_status`, `mapping_status`, and `mapping_ready` as optional observations only. They do not determine Token validity, block implementation, or trigger polling.
6. Use `data.item.app_type` as application-type metadata and route `data.item.client_token` directly to the reviewed secret sink.
7. Discard the API Key and temporary code. Never persist or repeat either.

When the request contains multiple Application ID slots, exchange the temporary code once and call the application lookup once per slot with the same in-memory API Key. Retry only transient network failures of this idempotent lookup; do not repeat a successful response to wait for sync or mapping state. Keep a distinct runtime Client Token reference per slot; do not assume applications share a token.

The RUM lookup requires `rum.rumCfgManage`, is unavailable to unsupported/free workspaces, and accepts the application types `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`.

## Application type precedence

Resolve each independent Application ID slot in this order:

1. user-defined `applicationType`;
2. AI API `app_type`;
3. repository detection.

Repository detection is the normal fallback for DataKit because DataKit has no control-plane input. If user and AI API values disagree, preserve the user choice in the pending plan, record both non-secret values, and block implementation until the mismatch is reviewed.

Keep Public DataWay `control_plane.status: catalog_resolved` stable. After plan validation and implementation authorization, run the helper and persist its non-secret, digest-bound execution state. Network reachability, code consumption, lookup attempts, Token persistence, and optional sync/mapping observations never update the plan revision. Without a user type, select AI API metadata before repository inference. With a user type, keep it selected. Revise the plan only when the API type changes the selected adapter/edit set or conflicts with the user value; the latter requires Revision Review.

## Secret sinks

Planning runs the helper in `--site-only` mode. It resolves the official catalog and non-secret AI API endpoint without reading a temporary authorization code, exchanging credentials, looking up an application, or receiving a Client Token.

Approved implementation performs local destination checks and credential-free reachability checks before reading the authorization code. It then performs the credential/application lookup and must write the Client Token to a reviewed runtime/build configuration file plus a separate non-secret control-plane state file. The helper refuses an application lookup without both destinations and the canonical plan digest, so a one-time code cannot be consumed while discarding the Token or producing state for another plan. Select dotenv, JSON, properties, or xcconfig according to the target's existing configuration path. It is allowed only when:

- Git confirms an in-repository path is ignored; an external path additionally requires the explicit `--allow-external-secret-sink` Review decision;
- the helper receives and verifies the Git worktree root, preventing a subdirectory or unrelated path from bypassing the ignore check;
- the file is a regular non-symlink; create it or atomically update only the selected keys while preserving unrelated entries;
- the resulting file has mode `0600`;
- the state destination is distinct from the secret sink, Git-ignored when it is inside the repository, and does not already exist;
- maintained source references only the selected runtime variable;
- the Agent does not open, print, diff, stage, or otherwise inspect the file.

The helper builds the safe result before writing, writes the secret sink first, then the state file, and restores the previous sink if state persistence fails. Its stdout and state file contain only a `runtime:<KEY>` reference, sink metadata, the plan digest, credential-free preflight evidence, and non-secret site/application observations.

On a rerun, an existing reviewed secret sink plus matching non-secret state is convergence evidence. Preserve both and skip credential resolution; read only the state. A colliding state path, missing repository guard, unsafe Git-ignore state, symlinked sink, or unreviewed external sink fails before site resolution, network preflight, temporary-code input, or credential exchange.
