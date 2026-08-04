# Public DataWay control plane

Use this flow only for Public DataWay. DataKit sends to the user-supplied DataKit receiver and never needs a Client Token, temporary authorization code, API Key, or AI API lookup.

## Authoritative endpoint resolution

Load both official catalogs:

- Guance: `https://urls.guance.com/`
- TrueWatch: `https://urls.truewatch.com/`

Each catalog returns a top-level `urls` object. Match the normalized user `datawayUrl` origin to an entry's `openway` origin and take `ai_api` from the same entry. The documented Web RUM address `https://rum-openway.guance.com` is the RUM-specific alias for the Guance `default` entry.

Do not:

- derive AI API by replacing hostname labels;
- use `OWL_REGISTRY_ENDPOINT` or an installed Owl configuration as the source;
- accept `aiApiEndpoint` in the standard prompt;
- choose a site from a partial, suffix, or nearest-looking hostname match.

If no exact catalog entry or documented alias matches, block Public DataWay credential resolution. Report the unmatched non-secret origin and the catalogs checked. Do not fall back to a guessed endpoint.

## Explicit test-site override

When the user explicitly authorizes a non-production site that is absent from both official catalogs, the bundled helper may load a local JSON catalog through `--test-site-catalog-file`. The file uses the same top-level `urls` shape and is authoritative for that run: match its `openway` origin exactly, take `ai_api` from the same entry, and do not fall back to an official catalog or hostname rewriting.

This is an advanced execution option and must not add `aiApiEndpoint` to the standard Prompt. The matched AI API must still be an HTTPS origin. Certificate verification remains enabled by default; `--insecure-test-tls` is allowed only with the explicit test catalog and only after the user approves that test-only exception.

Represent a resolved override in the plan with:

```json
{
  "status": "catalog_resolved",
  "catalog": "testing_override",
  "catalog_source": {
    "source": "existing:evals/files/test-site-catalog.json#testing"
  },
  "site_code": "testing",
  "test_only": true,
  "tls_verification": "disabled_for_testing"
}
```

Use `tls_verification: verified` when the test AI API certificate is trusted. Never carry the catalog override, disabled certificate verification, or a test DataWay into a production plan.

## Credential and application lookup

The temporary authorization code is a one-time value generated for the current account and workspace. It is not required or consumed during planning. For authorized implementation, accept it directly from the initial Prompt or a later user message and pass it to the helper process through `--temporary-auth-code-stdin`; the helper disables terminal echo when stdin is a TTY and also accepts Agent-managed process stdin. Keep `--temporary-auth-code-env NAME` as an optional source for automation. Never put the literal code in a shell command argument, shell expansion, temporary file, plan, metadata file, log, or response.

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

4. Validate readiness metadata before using the response: `token_expired` must be false, Client Token synchronization must be successful, and workspace mapping must be ready. Retry only explicit queued/pending states for a bounded number of attempts.
5. Use `data.item.app_type` as application-type metadata and route `data.item.client_token` directly to the reviewed secret sink.
6. Discard the API Key and temporary code. Never persist or repeat either.

When the request contains multiple Application ID slots, exchange the temporary code once and call the application lookup once per slot with the same in-memory API Key. Keep a distinct runtime Client Token reference per slot; do not assume applications share a token.

The RUM lookup requires `rum.rumCfgManage`, is unavailable to unsupported/free workspaces, and accepts the application types `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`.

## Application type precedence

Resolve each independent Application ID slot in this order:

1. user-defined `applicationType`;
2. AI API `app_type`;
3. repository detection.

Repository detection is the normal fallback for DataKit because DataKit has no control-plane input. If user and AI API values disagree, preserve the user choice in the pending plan, record both non-secret values, and block implementation until the mismatch is reviewed.

For Public DataWay, `catalog_resolved` is provisional. After the initial plan passes plan-phase validation and implementation is authorized, run the helper before application-code edits, persist the non-secret result, revise the plan to `resolved`, and record `verification` plus `api_value` per slot. Revalidate that resolved plan. Without a user type, select AI API metadata before repository inference. With a user type, keep it selected and mark matching metadata `matched` or conflicting metadata `mismatched`; the latter requires Revision Review.

## Secret sinks

Planning runs the helper in `--site-only` mode. It resolves the official catalog and non-secret AI API endpoint without reading a temporary authorization code, exchanging credentials, looking up an application, or receiving a Client Token.

Approved implementation performs the credential/application lookup once per implementation attempt and must write the Client Token to a dedicated environment-assignment file plus a separate non-secret metadata file. The helper refuses an application lookup without both destinations so a one-time code cannot be consumed while discarding the Token or the recovery metadata. The secret sink is a transport into an existing reviewed build/runtime injection path; do not assume every platform natively reads process environment variables. It is allowed only when:

- Git confirms an in-repository path is ignored; an external path additionally requires the explicit `--allow-external-secret-sink` Review decision;
- the helper receives and verifies the Git worktree root, preventing a subdirectory or unrelated path from bypassing the ignore check;
- the file does not already exist;
- the file is created with mode `0600`;
- the metadata destination is distinct from the secret sink and neither destination exists;
- maintained source references only the selected runtime variable;
- the Agent does not open, print, diff, stage, or otherwise inspect the file.

The helper builds the safe result before writing, writes the secret sink first, then the metadata file, and removes the newly created secret sink if metadata persistence fails. Its stdout and required metadata file contain only a `runtime:<VARIABLE>` reference and non-secret site/application metadata.

On a rerun, an existing reviewed secret sink plus matching non-secret metadata is convergence evidence. Preserve both and skip credential resolution; read only the metadata. If the helper is invoked with an existing sink, colliding metadata path, missing repository guard, unsafe Git-ignore state, or unreviewed external sink, it fails during preflight before it reads the temporary-code value from stdin or an environment variable, or exchanges credentials.
