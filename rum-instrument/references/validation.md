# Validation and evidence

## Plan validation

Before stopping for review or beginning implementation:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --kind plan --phase plan
```

Confirm detector candidates against real manifests and entry points. The plan must list every target, Application ID slot, exact edit, receiver mapping, privacy control, validation command, risk, and rollback.

For Revision Review, recompute the canonical plan digest and verify it equals `approval.reviewed_plan_sha256`. Hash every approved dirty overlap and verify it still equals the recorded `reviewed_overlaps` digest. Reject symlinked/out-of-worktree planned paths and any new dirty planned file.

For Public DataWay, also validate:

- normalized origin matches `openway` in an official Guance/TrueWatch catalog or the documented default Web RUM alias;
- `ai_api` comes from the matched catalog entry rather than hostname rewriting;
- the exchange and application lookup paths are exact;
- stdout, metadata, plans, diffs, and Git status contain no temporary code, API Key, or Client Token value;
- an in-repository restricted environment-assignment file is ignored and mode `0600`.
- the application lookup used both a new restricted configuration sink and a distinct new metadata file; a simulated metadata-write failure leaves no orphan Client Token sink;
- before application-code edits, `control_plane.status` is `resolved`, every selected application type records `matched`/`mismatched` plus `api_value`, and the resolved plan passes implementation validation.

For an approved test-site override, additionally validate:

- the helper was given `--test-site-catalog-file`, the DataWay origin matched that file exactly, and official catalogs were not used as fallback;
- the plan records `catalog: testing_override`, an `env:` or `existing:` catalog source, and `test_only: true`;
- the AI API remains HTTPS;
- `--insecure-test-tls` was explicitly approved and cannot run without the test catalog;
- the test catalog, TLS exception, and any HTTP DataWay receiver are excluded from production configuration.

For DataKit, assert that no control-plane lookup, temporary code, API Key, or Client Token is present. Require evidence that the RUM collector is enabled/configured and that the target runtime can reach the exact DataKit origin; unknown or blocked readiness prevents implementation.

## Local implementation proof

Run the repository's documented format, build/type-check, unit, integration, and platform packaging commands. Then verify:

- the SDK initializes exactly once per application process/page lifecycle;
- initialization occurs early enough for the intended errors, views, resources, and actions;
- one and only one receiver mode is active;
- Application ID selection matches the actual platform/build target;
- `service`, `version`, and `env` come from the recorded sources;
- SDK load/init failure does not break application startup;
- rerunning the implementation adds no duplicate dependency, initializer, config, or plugin;
- an existing reviewed Client Token sink is preserved without another credential exchange;
- existing network requests, signing, redirects, retries, and cancellation remain unchanged.

Use SDK debug output only as supporting evidence. It does not prove remote ingestion.

## Signal checks

For a representative local or mock session, check:

- View/page lifecycle and route names are stable and bounded;
- resource timing/status appears without bodies or unsafe URLs;
- errors retain useful stack information;
- custom actions/context contain only approved fields;
- trace headers appear only on allowed origins and correlate when a local/mock backend supports it;
- no header reaches a disallowed origin;
- Logs remain unchanged unless explicitly planned;
- Replay starts/stops with consent and masks/excludes the approved surfaces.

Run privacy canaries from [privacy-security.md](privacy-security.md) and inspect the actual locally captured/exported payload when possible.

## Artifact checks

When applicable, generate without uploading and verify:

- Web Sourcemap references match minified assets and release version;
- Android R8/ProGuard mapping and native symbols match the APK/AAB build;
- Apple dSYM UUIDs match the archive;
- Flutter/React Native/Unity wrapper and native artifacts share the intended release identity;
- upload commands use placeholders or existing secret references and have not been executed without authorization.

## Inventory validation

Validate `.rum/instrumentation.json` using:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/instrumentation.json --kind instrumentation
```

Every target must have one disposition and evidence or a concrete blocker. If optional `docs/rum-instrumentation.md` was generated, compare it with the JSON inventory.

Set:

```json
{
  "remote_verification": {
    "verified": false,
    "evidence": []
  }
}
```

Change it only from human-provided console/ingestion evidence. Local HTTP success, SDK debug messages, or an absence of exceptions are not remote proof.
