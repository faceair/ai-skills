# Repository execution and authorization

## Safety baseline

Read repository-level and nested agent instructions before analysis. Record:

- repository root, current commit, branch, and `git status --short`;
- every uncommitted path and whether it overlaps a potential RUM edit;
- manifests, lockfiles, runtime entry points, deployment configuration, and generated/vendor directories;
- documented format, build/type-check, test, and smoke commands;
- current RUM, Logs, Trace, Replay, Sourcemap, dSYM, mapping, and native-symbol behavior.

Never stash, reset, clean, overwrite, or reformat unrelated user work. An unrelated dirty worktree may be analyzed. A planned dirty file blocks ordinary explicit implementation. Revision Review may approve an exact pre-existing overlap only when `reviewed_overlaps` binds the file bytes reviewed by the user; any new dirty file or digest drift blocks implementation.

## Target ownership

Define a target as an independently deployed application with its own RUM Application ID. A framework wrapper and its generated/native subprojects are normally one logical target with platform-specific Application ID slots:

- React Native: Android and iOS;
- Flutter: Android and iOS, plus a separate Web slot when Flutter Web is deployed;
- UniApp Native: Android and iOS; route UniApp MiniApp output to the MiniApp adapter;
- Unity: Android and iOS.

Treat a nested native project as independent only when repository evidence shows a separate build, release, startup, or SDK initialization path.

Trace every target to its canonical maintained startup source. Do not edit `dist`, `build`, `DerivedData`, `Pods`, `.gradle`, `node_modules`, `oh_modules`, `unpackage`, generated Xcode/Gradle output, vendored SDKs, or copied release artifacts.

## Plan-only behavior

“规划” and “审查” do not authorize application-code edits. A planning run may create or update `.rum/plan.json` when the repository is writable, because that file is the requested planning artifact. If the user requested a purely read-only review, return the same contract in the response without writing it.

The plan must cover the entire in-scope repository before the first implementation edit. Record exact files and batches so authorization is auditable.

## Intent-aware authorization

Infer authorization from the user's verb; do not add an `approvalMode` Prompt variable:

- “规划”, “审查”, “plan”, “audit”, and read-only “validate” are plan-only. Write a pending plan with `basis: plan_only_request` and stop.
- “实施”, “接入”, “修复”, “implement”, “integrate”, “repair”, and “规划并实施” explicitly authorize ordinary repository changes required for core RUM. Generate and validate the plan first, then use `status: approved` with `basis: explicit_implementation_request` and continue in the same run.
- A later message that identifies or clearly approves the latest persisted revision uses `basis: revision_review`.

Before implementation, confirm:

- repository identity and commit;
- initial Git status and every planned file;
- target set and Application ID slots;
- receiver mode and source references;
- SDK/package decisions;
- signals, privacy controls, and artifact behavior;
- exact files and validation commands;
- dirty-file overlap.

For Public DataWay also confirm the official catalog match, non-secret AI API metadata, temporary-code source reference when already supplied, runtime Client Token variable, and ignored secret sink. Never inspect the sink's contents.

Explicit implementation intent is not blanket approval. Stop with `status: pending`, `basis: explicit_implementation_request`, and concrete `approval.blockers` when the plan contains any of:

- ambiguous or reused Application ID slots;
- a user-defined application type that conflicts with AI API metadata;
- an uncommitted file or hunk overlapping a planned edit;
- SDK dependency upgrade, replacement, removal, or unverifiable provenance;
- new Logs, Trace, Replay, WebView, native crash, ANR, freeze, UI-block, Remote Config, Canvas Replay, Sourcemap, symbol, or other optional scope;
- the built-in testing site, disabled TLS verification, or another test-only exception;
- no safe ignored runtime Client Token sink;
- a remote mutation such as application creation, deployment, or artifact upload;
- a material change to targets, files, receiver mode, signals, privacy behavior, or artifact handling after plan validation.

Continue only after the user reviews the exact revised plan. Record that as `basis: revision_review`, add the canonical digest printed by `validate_contract.py --print-review-digest`, and record an exact digest for every approved dirty overlap. A plain “开始实现” may approve the latest displayed or persisted pending revision only when repository identity, revision, digest, and overlap set are unambiguous.

Record optional capability and artifact decisions in the structured `existing_instrumentation.signals`, `profile.signals`, and `artifacts` fields defined by [contracts.md](contracts.md). The plan validator derives Review requirements from those fields; free-form risk prose is not an authorization control.

## Baseline and batches

Run documented commands before modification where practical. Existing failures are baseline evidence. Do not claim a later failure is pre-existing unless the same command and failure were recorded.

Batch by independently deployable target while respecting shared initialization/configuration. For each batch record:

- target and platform variants;
- exact ordered edits;
- dependency and version source;
- receiver and Application ID source mappings;
- privacy and signal changes;
- validation commands and expected evidence;
- rollback instructions.

Rerunning the Skill must converge on one initializer and one canonical configuration path.

Planning never consumes the temporary authorization code. Authorized Public DataWay implementation first validates the stable plan, then performs credential-free receiver checks before reading the code, resolves each application once, and persists the Client Token plus digest-bound non-secret execution state before application-code edits. Sync/mapping observations never cause polling or plan revision. Revalidate the stable plan together with the state; revise only when application metadata changes a material decision. A rerun preserves an existing safe runtime sink and matching state instead of exchanging another code. DataKit implementation requires evidence that the RUM collector is enabled and the application runtime can reach its receiver.

## Remote actions

Repository implementation does not authorize Guance console changes, application creation, deployment, SDK artifact download from an unverified source, Sourcemap/symbol upload, or production traffic. Prepare commands or handoff steps, but execute a remote mutation only after explicit authorization for that action.
