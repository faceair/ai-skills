#!/usr/bin/env python3
"""Detect candidate Guance RUM application targets without changing the repository."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


EXCLUDED_DIRS = {
    ".agents",
    ".cache",
    ".claude",
    ".codex",
    ".copilot",
    ".cursor",
    ".gemini",
    ".git",
    ".gradle",
    ".idea",
    ".jest-cache",
    ".kimi-code",
    ".next",
    ".nuxt",
    ".opencode",
    ".pi",
    ".qoder",
    ".rum",
    ".turbo",
    ".venv",
    ".zcode",
    "Assets/Plugins",
    "DerivedData",
    "Pods",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "examples",
    "fixtures",
    "node_modules",
    "oh_modules",
    "out",
    "target",
    "test",
    "tests",
    "unpackage",
    "vendor",
}

EXCLUDED_RELATIVE_DIRS = {
    ".config/agents/skills",
    ".config/opencode/skills",
    ".github/skills",
}

RUNTIME_SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cjs",
    ".cpp",
    ".cs",
    ".cts",
    ".dart",
    ".h",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".m",
    ".mjs",
    ".mm",
    ".mts",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}

WEB_DEPENDENCIES = {
    "@angular/core",
    "@cloudcare/browser-rum",
    "@sveltejs/kit",
    "electron",
    "next",
    "nuxt",
    "react",
    "react-dom",
    "svelte",
    "vite",
    "vue",
}

MINIAPP_DEPENDENCIES = {
    "@cloudcare/rum-miniapp",
    "@tarojs/taro",
    "@wepy/core",
    "mpvue",
    "wepy",
}

JAVASCRIPT_DEPENDENCY_MARKERS = {
    "@cloudcare/browser-rum": "browser-rum-package",
    "@cloudcare/rum-miniapp": "miniapp-rum-package",
    "@cloudcare/react-native-mobile": "react-native-rum-package",
}

MANIFEST_RUM_MARKERS = {
    "@guancecloud/ft_sdk": ("harmony-rum-sdk", {"oh-package.json5"}),
    "com.cloudcare.ft.mobile.sdk.tracker.agent:ft-sdk": (
        "android-rum-sdk",
        {"build.gradle", "build.gradle.kts", "libs.versions.toml"},
    ),
    "ft_mobile_agent_flutter": ("flutter-rum-package", {"pubspec.yaml"}),
    "datakit-sdk-cpp": ("cpp-rum-sdk", {"CMakeLists.txt", "conanfile.py", "vcpkg.json"}),
    "datakit-uniapp-native-plugin": ("uniapp-rum-plugin", {"manifest.json", "package.json"}),
}

RUNTIME_RUM_MARKERS = {
    "DATAFLUX_RUM": "browser-rum-global",
    "FTMobileSDK": "apple-rum-sdk",
    "FTSDKConfig": "native-rum-config",
    "datafluxRum": "javascript-rum-api",
}

HYBRID_PLATFORMS = {"react-native", "flutter", "uniapp", "unity"}

PLATFORM_MARKERS = {
    "web": {"browser-rum-package", "browser-rum-global", "javascript-rum-api"},
    "miniapp": {"miniapp-rum-package", "javascript-rum-api"},
    "android": {"android-rum-sdk", "native-rum-config"},
    "apple": {"apple-rum-sdk", "native-rum-config"},
    "harmonyos": {"harmony-rum-sdk", "native-rum-config"},
    "react-native": {
        "react-native-rum-package",
        "android-rum-sdk",
        "apple-rum-sdk",
        "native-rum-config",
    },
    "flutter": {
        "flutter-rum-package",
        "browser-rum-package",
        "browser-rum-global",
        "android-rum-sdk",
        "apple-rum-sdk",
        "native-rum-config",
    },
    "uniapp": {
        "uniapp-rum-plugin",
        "miniapp-rum-package",
        "browser-rum-package",
        "android-rum-sdk",
        "apple-rum-sdk",
        "native-rum-config",
    },
    "cpp": {"cpp-rum-sdk"},
    "unity": {"android-rum-sdk", "apple-rum-sdk", "native-rum-config"},
}


@dataclass
class Candidate:
    platform: str
    root: Path
    variants: set[str] = field(default_factory=set)
    evidence: set[Path] = field(default_factory=set)
    app_id_slots: set[str] = field(default_factory=set)
    confidence: str = "high"

    def merge(
        self,
        *,
        variants: Iterable[str] = (),
        evidence: Iterable[Path] = (),
        app_id_slots: Iterable[str] = (),
        confidence: str | None = None,
    ) -> None:
        self.variants.update(variants)
        self.evidence.update(evidence)
        self.app_id_slots.update(app_id_slots)
        if confidence == "low" or (confidence == "medium" and self.confidence == "high"):
            self.confidence = confidence


def walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept: list[str] = []
        for dirname in dirnames:
            relative = (current_path / dirname).relative_to(root).as_posix()
            if (
                dirname in EXCLUDED_DIRS
                or relative in EXCLUDED_DIRS
                or relative in EXCLUDED_RELATIVE_DIRS
            ):
                continue
            if (current_path / dirname).is_symlink():
                continue
            kept.append(dirname)
        dirnames[:] = kept
        files.extend(current_path / name for name in filenames)
    return files


def read_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def strip_comments_and_strings(text: str) -> str:
    """Keep executable tokens while removing comments and quoted examples."""
    result: list[str] = []
    state = "code"
    interpolation_depths: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""

        if state == "code":
            if interpolation_depths and char == "{":
                interpolation_depths[-1] += 1
                result.append(char)
                index += 1
                continue
            if interpolation_depths and char == "}":
                interpolation_depths[-1] -= 1
                result.append(" ")
                index += 1
                if interpolation_depths[-1] == 0:
                    interpolation_depths.pop()
                    state = "template"
                continue
            if char == "/" and following == "/":
                result.extend((" ", " "))
                state = "line-comment"
                index += 2
                continue
            if char == "/" and following == "*":
                result.extend((" ", " "))
                state = "block-comment"
                index += 2
                continue
            if char in {"'", '"'}:
                result.append(" ")
                state = {"'": "single", '"': "double"}[char]
                index += 1
                continue
            if char == "`":
                result.append(" ")
                state = "template"
                index += 1
                continue
            result.append(char)
            index += 1
            continue

        if state == "line-comment":
            result.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
            index += 1
            continue

        if state == "block-comment":
            result.append("\n" if char == "\n" else " ")
            if char == "*" and following == "/":
                result.append(" ")
                state = "code"
                index += 2
            else:
                index += 1
            continue

        if state == "template":
            result.append("\n" if char == "\n" else " ")
            if char == "\\":
                if following:
                    result.append("\n" if following == "\n" else " ")
                    index += 2
                else:
                    index += 1
                continue
            if char == "`":
                state = "code"
                index += 1
                continue
            if char == "$" and following == "{":
                result.append(" ")
                interpolation_depths.append(1)
                state = "code"
                index += 2
                continue
            index += 1
            continue

        result.append("\n" if char == "\n" else " ")
        if char == "\\":
            if following:
                result.append("\n" if following == "\n" else " ")
                index += 2
            else:
                index += 1
            continue
        closing = {"single": "'", "double": '"'}[state]
        if char == closing:
            state = "code"
        index += 1

    return "".join(result)


def executable_text(path: Path, text: str | None = None) -> str:
    if text is None:
        text = read_text(path)
    if path.suffix.lower() in {".html", ".svelte", ".vue"}:
        scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", text, flags=re.IGNORECASE | re.DOTALL)
        text = "\n".join(scripts)
    return strip_comments_and_strings(text)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def dependency_names(package: dict) -> set[str]:
    names: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = package.get(section)
        if isinstance(values, dict):
            names.update(name for name in values if isinstance(name, str))
    return names


def relative(path: Path, root: Path) -> str:
    value = path.relative_to(root).as_posix()
    return value or "."


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def git_value(root: Path, *arguments: str) -> str | None:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    value = process.stdout.strip()
    return value if process.returncode == 0 and value else None


def uniapp_variants(manifest: Path) -> list[str]:
    text = read_text(manifest)
    variants: list[str] = []
    if "app-plus" in text:
        variants.extend(["android", "ios"])
    if any(marker in text for marker in ('"mp-', "'mp-")):
        variants.append("miniapp")
    if '"h5"' in text or "'h5'" in text:
        variants.append("web")
    return variants or ["android", "ios"]


def detect(root: Path) -> dict:
    root = root.resolve()
    files = walk_files(root)
    by_name: dict[str, list[Path]] = {}
    for path in files:
        by_name.setdefault(path.name, []).append(path)

    candidates: dict[tuple[str, Path], Candidate] = {}
    warnings: list[str] = []

    def add(
        platform: str,
        target_root: Path,
        *,
        variants: Iterable[str] = (),
        evidence: Iterable[Path] = (),
        app_id_slots: Iterable[str] = (),
        confidence: str = "high",
    ) -> None:
        target_root = target_root.resolve()
        if not is_within(target_root, root):
            return
        key = (platform, target_root)
        if key not in candidates:
            candidates[key] = Candidate(platform=platform, root=target_root, confidence=confidence)
        candidates[key].merge(
            variants=variants,
            evidence=evidence,
            app_id_slots=app_id_slots,
            confidence=confidence,
        )

    # JavaScript and framework targets.
    for manifest in by_name.get("package.json", []):
        package = read_json(manifest)
        dependencies = dependency_names(package)
        target_root = manifest.parent

        if "react-native" in dependencies:
            variants = [name for name in ("android", "ios") if (target_root / name).exists()]
            if not variants:
                variants = ["android", "ios"]
                warnings.append(
                    f"{relative(target_root, root)}: React Native platforms inferred as android+ios; confirm build targets"
                )
            add(
                "react-native",
                target_root,
                variants=variants,
                evidence=[manifest],
                app_id_slots=variants,
            )
            continue

        if "@dcloudio/uni-app" in dependencies or (
            (target_root / "pages.json").is_file() and (target_root / "manifest.json").is_file()
        ):
            uni_manifest = target_root / "manifest.json"
            variants = uniapp_variants(uni_manifest)
            if variants == ["android", "ios"] and "app-plus" not in read_text(uni_manifest):
                warnings.append(
                    f"{relative(target_root, root)}: UniApp variants inferred as android+ios; confirm release targets"
                )
            slots = [variant for variant in variants if variant in {"android", "ios", "web", "miniapp"}]
            evidence = [manifest]
            for name in ("pages.json", "manifest.json"):
                path = target_root / name
                if path.is_file():
                    evidence.append(path)
            add("uniapp", target_root, variants=variants, evidence=evidence, app_id_slots=slots)
            continue

        if dependencies & MINIAPP_DEPENDENCIES:
            add(
                "miniapp",
                target_root,
                variants=["framework"],
                evidence=[manifest],
                app_id_slots=["miniapp"],
                confidence="medium",
            )
            continue

        if dependencies & WEB_DEPENDENCIES:
            variants = ["browser"]
            if "electron" in dependencies:
                variants = ["electron"]
            elif dependencies & {"next", "nuxt", "@sveltejs/kit"}:
                variants = ["ssr"]
            add(
                "web",
                target_root,
                variants=variants,
                evidence=[manifest],
                app_id_slots=["web"],
                confidence="medium" if dependencies == {"vite"} else "high",
            )

    # HBuilderX UniApp projects may not have package.json.
    for manifest in by_name.get("manifest.json", []):
        target_root = manifest.parent
        pages = target_root / "pages.json"
        if not pages.is_file() or ("uniapp", target_root.resolve()) in candidates:
            continue
        variants = uniapp_variants(manifest)
        if variants == ["android", "ios"] and "app-plus" not in read_text(manifest):
            warnings.append(
                f"{relative(target_root, root)}: UniApp variants inferred as android+ios; confirm release targets"
            )
        add(
            "uniapp",
            target_root,
            variants=variants,
            evidence=[manifest, pages],
            app_id_slots=variants,
        )

    # Flutter targets.
    for manifest in by_name.get("pubspec.yaml", []):
        text = read_text(manifest)
        if "sdk: flutter" not in text and "\nflutter:" not in text:
            continue
        target_root = manifest.parent
        variants = [name for name in ("android", "ios", "web") if (target_root / name).exists()]
        slots = [name for name in variants if name in {"android", "ios", "web"}]
        add("flutter", target_root, variants=variants, evidence=[manifest], app_id_slots=slots)

    # HarmonyOS targets.
    for manifest in by_name.get("build-profile.json5", []):
        target_root = manifest.parent
        evidence = [manifest]
        oh_package = target_root / "oh-package.json5"
        if oh_package.is_file():
            evidence.append(oh_package)
        add(
            "harmonyos",
            target_root,
            variants=["harmonyos"],
            evidence=evidence,
            app_id_slots=["harmonyos"],
        )

    # Unity targets.
    for marker in by_name.get("ProjectVersion.txt", []):
        if marker.parent.name != "ProjectSettings":
            continue
        target_root = marker.parent.parent
        variants: list[str] = []
        plugins = target_root / "Assets" / "Plugins"
        if (plugins / "Android").exists():
            variants.append("android")
        if (plugins / "iOS").exists():
            variants.append("ios")
        if not variants:
            variants = ["android", "ios"]
            warnings.append(
                f"{relative(target_root, root)}: Unity platforms inferred as android+ios; confirm build settings"
            )
        add("unity", target_root, variants=variants, evidence=[marker], app_id_slots=variants)

    # Native MiniApp roots.
    for marker in by_name.get("project.config.json", []):
        target_root = marker.parent
        lifecycle = [path for name in ("app.json", "app.js", "app.ts") for path in [target_root / name] if path.is_file()]
        if lifecycle:
            add(
                "miniapp",
                target_root,
                variants=["native"],
                evidence=[marker, *lifecycle],
                app_id_slots=["miniapp"],
            )

    # Android application modules.
    for manifest in by_name.get("AndroidManifest.xml", []):
        if manifest.parent.name == "main" and manifest.parent.parent.name == "src":
            target_root = manifest.parents[2]
        else:
            target_root = manifest.parent
        build_files = [target_root / name for name in ("build.gradle", "build.gradle.kts") if (target_root / name).is_file()]
        if build_files:
            add(
                "android",
                target_root,
                variants=["android"],
                evidence=[manifest, *build_files],
                app_id_slots=["android"],
            )

    # Apple application projects.
    for project_file in by_name.get("project.pbxproj", []):
        if project_file.parent.suffix != ".xcodeproj":
            continue
        project_text = read_text(project_file)
        variants: list[str] = []
        if "IPHONEOS_DEPLOYMENT_TARGET" in project_text or "SDKROOT = iphoneos" in project_text:
            variants.append("ios")
        if "TVOS_DEPLOYMENT_TARGET" in project_text or "SDKROOT = appletvos" in project_text:
            variants.append("tvos")
        if "MACOSX_DEPLOYMENT_TARGET" in project_text or "SDKROOT = macosx" in project_text:
            variants.append("macos")
        if not variants:
            variants = ["apple"]
        add(
            "apple",
            project_file.parent.parent,
            variants=variants,
            evidence=[project_file],
            app_id_slots=variants,
            confidence="medium",
        )

    # C++ executable projects.
    for manifest in by_name.get("CMakeLists.txt", []):
        text = read_text(manifest)
        if not re.search(r"\bproject\s*\(", text) or not re.search(r"\badd_executable\s*\(", text):
            continue
        add(
            "cpp",
            manifest.parent,
            variants=["windows-linux"],
            evidence=[manifest],
            app_id_slots=["cpp"],
            confidence="low",
        )

    # Remove native/build candidates owned by framework targets.
    hybrid_roots = [candidate.root for candidate in candidates.values() if candidate.platform in HYBRID_PLATFORMS]
    filtered: list[Candidate] = []
    for candidate in candidates.values():
        owned = False
        if candidate.platform in {"android", "apple", "cpp"}:
            for hybrid_root in hybrid_roots:
                if candidate.root != hybrid_root and is_within(candidate.root, hybrid_root):
                    owned = True
                    break
        if not owned:
            filtered.append(candidate)

    # Search only executable source and real dependency manifests. Never emit
    # matching lines or values, and never treat documentation/code samples as
    # proof of an installed SDK.
    occurrences: list[tuple[Path, str]] = []

    for manifest in by_name.get("package.json", []):
        dependencies = dependency_names(read_json(manifest))
        for dependency, label in JAVASCRIPT_DEPENDENCY_MARKERS.items():
            if dependency in dependencies:
                occurrences.append((manifest, label))

    for path in files:
        for marker, (label, filenames) in MANIFEST_RUM_MARKERS.items():
            if path.name in filenames and marker in read_text(path):
                occurrences.append((path, label))
        if path.suffix.lower() in RUNTIME_SOURCE_SUFFIXES and not path.name.endswith(".d.ts"):
            raw_text = read_text(path)
            present_markers = [
                (marker, label) for marker, label in RUNTIME_RUM_MARKERS.items() if marker in raw_text
            ]
            if not present_markers:
                continue
            text = executable_text(path, raw_text)
            for marker, label in present_markers:
                if marker in text:
                    occurrences.append((path, label))

    targets: list[dict] = []
    for candidate in sorted(filtered, key=lambda item: (relative(item.root, root), item.platform)):
        existing: dict[str, list[str]] = {}
        for path, label in occurrences:
            if label in PLATFORM_MARKERS[candidate.platform] and is_within(path, candidate.root):
                existing.setdefault(label, []).append(relative(path, root))
        targets.append(
            {
                "id": f"{candidate.platform}:{relative(candidate.root, root)}",
                "path": relative(candidate.root, root),
                "platform": candidate.platform,
                "variants": sorted(candidate.variants),
                "application_id_slots": sorted(candidate.app_id_slots),
                "confidence": candidate.confidence,
                "evidence": sorted(relative(path, root) for path in candidate.evidence),
                "existing_rum_markers": {
                    label: sorted(set(paths)) for label, paths in sorted(existing.items())
                },
            }
        )

    if not targets:
        warnings.append("No supported RUM application target was detected; inspect entry points manually")
    for target in targets:
        if target["confidence"] == "low":
            warnings.append(f"{target['id']}: low-confidence candidate requires manual confirmation")

    dirty = git_value(root, "status", "--short")
    return {
        "schema_version": 1,
        "repository": {
            "root": str(root),
            "git_commit": git_value(root, "rev-parse", "HEAD"),
            "dirty_paths": dirty.splitlines() if dirty else [],
        },
        "targets": targets,
        "warnings": sorted(set(warnings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default=".", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    arguments = parser.parse_args()

    if not arguments.repository.is_dir():
        parser.error(f"repository is not a directory: {arguments.repository}")

    result = detect(arguments.repository)
    text = json.dumps(result, ensure_ascii=False, indent=2 if arguments.pretty else None, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
