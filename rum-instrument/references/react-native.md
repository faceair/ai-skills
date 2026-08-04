# React Native adapter

Primary-source registry: `official-sources.json#react_native`.

## Detect

Confirm React Native from the `react-native` dependency, Metro configuration, JS/TS application entry, and Android/iOS projects. Current official support is Android and iOS.

Treat it as one framework target with independent `android` and `ios` Application ID slots. Do not separately instrument its native subprojects unless repository evidence proves separate applications.

## Plan

Verify the current `@cloudcare/react-native-mobile` release and its React Native, Android, iOS, Gradle, CocoaPods/SPM, and New Architecture compatibility.

Trace initialization ownership across JavaScript and native layers. Existing native SDK initialization may need bridge-only integration; do not initialize the same platform twice. Record automatic versus manual View, Action, Resource, Error, WebView, native-crash, Logs, Trace, and Replay ownership.

Map each platform's Application ID and the normalized receiver through the current wrapper/native APIs. Never reuse one ID for both platforms.

## Privacy and artifacts

Review JS navigation names/params, fetch/XHR data, native network data, custom properties, WebView bridge, and Replay masking. Do not serialize navigation params or request objects wholesale.

Plan Android mapping/native symbols and Apple dSYM per actual platform build. Keep release identity consistent across JS bundle and native binaries.

## Validation

Run JS lint/type/test plus Android and iOS builds/tests available in the repository. Verify one initializer per platform, correct ID selection, no duplicate JS/native events, stable navigation views, unchanged requests, trace allowlist, WebView ownership, artifact identity, and privacy canaries.
