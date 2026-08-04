# macOS adapter

Primary-source registry: `official-sources.json#macos`.

## Detect

Confirm independently shipped macOS application targets from Xcode project/workspace settings, `MACOSX_DEPLOYMENT_TARGET`, schemes, product bundle identifiers, `Package.swift`/Podfile dependencies, and release archives. Do not treat iOS/tvOS targets, Pods, DerivedData, generated projects, or wrapper-owned native subprojects as the same SDK integration.

Inspect existing `FTMacOSSDK`, `FTSDKConfig`, `FTSDKAgent`, `FTRumConfig`, CocoaPods/SPM wiring, `main.m`/`main.swift`, AppDelegate initialization, networking hooks, and dSYM tasks.

## Plan

Use the separate `datakit-macos` repository and `FTMacOSSDK` package. Do not substitute `datakit-ios`, `FTMobileSDK`, or an iOS App/Scene-delegate recipe.

Map:

- DataKit to `FTSDKConfig(datakitUrl:)`;
- Public DataWay to `FTSDKConfig(datawayUrl:clientToken:)`;
- the macOS Application ID to `FTRumConfig(appid:)`.

Use `custom` as the repository fallback RUM application type for a macOS slot; do not classify it as `ios`.

Keep DataKit and Public DataWay mutually exclusive. For Public DataWay, reference only the helper-created runtime Client Token source.

The official macOS guide initializes the SDK in `main.m` or `main.swift` before `NSApplicationMain`, because the first `NSViewController.viewDidLoad` or `NSWindowController.windowDidLoad` may precede `applicationDidFinishLaunching`. Preserve an existing earlier canonical initializer and ensure the SDK starts once.

## Privacy and artifacts

Review application privacy declarations and data-sanitization hooks. Do not collect input/control text, request bodies, raw URL queries, file paths, window titles containing user data, or broad user dictionaries.

Generate dSYM files from the same archive/build and verify UUIDs before planning an upload. Keep upload credentials out of project files and do not upload without authorization.

## Validation

Build/test the selected macOS scheme. Verify the `FTMacOSSDK` dependency, pre-`NSApplicationMain` single initialization, receiver exclusivity, Application ID selection, lifecycle views, network behavior, optional trace allowlist, matching dSYM identity, and privacy canaries.
