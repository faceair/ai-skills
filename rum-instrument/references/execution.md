# Repository execution and approval

## Safety baseline

Read repository-level and nested agent instructions before analysis. Record:

- repository root, current commit, branch, and `git status --short`;
- every uncommitted path and whether it overlaps a potential RUM edit;
- manifests, lockfiles, runtime entry points, deployment configuration, and generated/vendor directories;
- documented format, build/type-check, test, and smoke commands;
- current RUM, Logs, Trace, Replay, Sourcemap, dSYM, mapping, and native-symbol behavior.

Never stash, reset, clean, overwrite, or reformat unrelated user work. An unrelated dirty worktree may be analyzed. Stop before an edit whose file or hunk overlaps existing work.

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

The plan must cover the entire in-scope repository before the first implementation edit. Record exact files and batches so approval is meaningful.

## Approval gate

Approval is valid only when the user identifies the plan revision or clearly approves the latest displayed revision. Before implementation, confirm:

- repository identity and commit;
- analysis fingerprint;
- target set and Application ID slots;
- receiver mode and source references;
- SDK/package decisions;
- signals, privacy controls, and artifact behavior;
- exact files and validation commands;
- dirty-file overlap.

For Public DataWay also confirm the official catalog match, non-secret AI API metadata, temporary-code source reference, runtime Client Token variable, and ignored secret sink. Never inspect the sink's contents.

Revise and reapprove when any of these changes materially. A request such as “开始实现” approves the design being discussed only when a matching persisted plan exists and the response clearly identifies its revision; otherwise first create the plan and stop.

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

The temporary authorization code is one-time. A planning lookup may consume it while discarding the Client Token; implementation therefore requires a fresh code unless an approved runtime Client Token source already exists.

## Remote actions

Repository implementation does not authorize Guance console changes, application creation, deployment, SDK artifact download from an unverified source, Sourcemap/symbol upload, or production traffic. Prepare commands or handoff steps, but execute a remote mutation only after explicit authorization for that action.
