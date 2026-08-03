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
  "status": "resolved",
  "catalog": "testing_override",
  "catalog_source": {
    "source": "existing:user-provided-testing-catalog"
  },
  "site_code": "testing",
  "test_only": true,
  "tls_verification": "disabled_for_testing"
}
```

Use `tls_verification: verified` when the test AI API certificate is trusted. Never carry the catalog override, disabled certificate verification, or a test DataWay into a production plan.

## Credential and application lookup

The temporary authorization code is a one-time credential generated for the current account and workspace. Read it only from the named environment source.

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

4. Use `data.item.app_type` as application-type metadata and route `data.item.client_token` directly to the approved secret sink.
5. Discard the API Key and temporary code. Never persist either.

When the request contains multiple Application ID slots, exchange the temporary code once and call the application lookup once per slot with the same in-memory API Key. Keep a distinct runtime Client Token reference per slot; do not assume applications share a token.

The RUM lookup requires `rum.rumCfgManage`, is unavailable to unsupported/free workspaces, and accepts the application types `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`.

## Application type precedence

Resolve each independent Application ID slot in this order:

1. user-defined `applicationType`;
2. AI API `app_type`;
3. repository detection.

Repository detection is the normal fallback for DataKit because DataKit has no control-plane input. If user and AI API values disagree, preserve the user choice in the pending plan, record both non-secret values, and block implementation until the mismatch is reviewed.

## Secret sinks

Planning may run the helper without a secret output file. This proves the application exists, captures non-secret type/site metadata, and discards the returned Client Token.

Approved implementation may write the Client Token to a dedicated dotenv file only when:

- the path is outside the repository, or Git confirms the in-repository path is ignored;
- the file does not already exist;
- the file is created with mode `0600`;
- maintained source references only the selected runtime variable;
- the Agent does not open, print, diff, stage, or otherwise inspect the file.

The helper's stdout and optional metadata file contain only a `runtime:<VARIABLE>` reference and non-secret site/application metadata.

On a rerun, an existing approved secret sink is convergence evidence. Preserve it and skip credential resolution. If the helper is invoked with an existing sink, it fails during preflight before it reads the temporary-code value or exchanges credentials.
