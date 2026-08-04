# HarmonyOS adapter

Official access guide: https://docs.guance.com/real-user-monitoring/harmonyos/app-access/

## Detect

Confirm HarmonyOS applications from `oh-package.json5`, `build-profile.json5`, module configuration, ArkTS entry abilities, products/build modes, and maintained HAR sources. Exclude `oh_modules` and generated build output.

Inspect existing `@guancecloud/ft_sdk`, optional `@guancecloud/ft_sdk_ext`/`@guancecloud/ft_native`, legacy unscoped packages, `FTSDKConfig`, entry-ability initialization, HTTP interceptors, WebView, and symbol/native setup.

## Plan

Use the current scoped OHPM packages or the official local HAR path. When local HAR is required, preserve correct root-level `overrides` so optional packages resolve the local core SDK. Do not mix legacy and scoped imports.

Verify the selected SDK/package versions and HarmonyOS/DevEco compatibility. Map receiver and Application ID through the current `FTSDKConfig`. Initialize once at the documented ability/application lifecycle point.

Only add optional ext/native packages for capabilities in the approved plan. Avoid duplicate HTTP/WebView collection.

## Privacy and validation

Review permissions, custom tags/global context, request URL handling, WebView data, and native-crash fields. Use bounded business-prefixed tags only after approval.

Run OHPM resolution plus repository build/test commands. Verify scoped dependency convergence, initialization count, correct product Application ID, receiver selection, HTTP behavior/trace allowlist, WebView ownership, optional native behavior, and absence of privacy canaries.
