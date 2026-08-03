from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_rum_targets.py"
SPEC = importlib.util.spec_from_file_location("detect_rum_targets", SCRIPT)
assert SPEC and SPEC.loader
DETECTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DETECTOR
SPEC.loader.exec_module(DETECTOR)


class DetectRumTargetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def targets(self):
        return DETECTOR.detect(self.root)["targets"]

    def test_detects_existing_web_rum_without_emitting_source_values(self):
        self.write(
            "package.json",
            json.dumps({"dependencies": {"vue": "3.5.0", "@cloudcare/browser-rum": "3.0.0"}}),
        )
        self.write(
            "public/index.html",
            "<script>DATAFLUX_RUM.init({clientToken: 'do-not-emit-this-value'})</script>",
        )

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("web", targets[0]["platform"])
        self.assertEqual(["web"], targets[0]["application_id_slots"])
        self.assertIn("browser-rum-global", targets[0]["existing_rum_markers"])
        self.assertNotIn("do-not-emit-this-value", json.dumps(targets))

    def test_excludes_agent_skills_and_generated_plan_from_markers(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("public/index.html", "<script>window.DATAFLUX_RUM.init({})</script>\n")
        for relative in (
            ".agents/skills/rum-instrument/references/web.md",
            ".claude/skills/rum-instrument/SKILL.md",
            ".codex/skills/rum-instrument/SKILL.md",
            ".cursor/skills/rum-instrument/SKILL.md",
            ".github/skills/rum-instrument/SKILL.md",
            ".rum/plan.json",
        ):
            self.write(relative, "DATAFLUX_RUM datafluxRum @cloudcare/browser-rum\n")

        targets = self.targets()

        self.assertEqual(
            {"browser-rum-global": ["public/index.html"]},
            targets[0]["existing_rum_markers"],
        )

    def test_detector_result_is_stable_after_plan_generation(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("public/index.html", "<script>window.DATAFLUX_RUM.init({})</script>\n")
        before = self.targets()
        self.write(
            ".rum/plan.json",
            json.dumps({"sdk": "@cloudcare/browser-rum", "initializer": "DATAFLUX_RUM.init({})"}),
        )

        self.assertEqual(before, self.targets())

    def test_package_marker_requires_manifest_dependency(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write(
            "src/IntegrationExample.vue",
            """<script lang="ts">
            const sample = `npm install @cloudcare/browser-rum
            datafluxRum.init({ applicationId: "example" })`;
            </script>
            """,
        )

        target = self.targets()[0]

        self.assertNotIn("browser-rum-package", target["existing_rum_markers"])
        self.assertNotIn("javascript-rum-api", target["existing_rum_markers"])

        self.write(
            "package.json",
            json.dumps({"dependencies": {"vue": "3.5.0", "@cloudcare/browser-rum": "3.3.5"}}),
        )
        target = self.targets()[0]
        self.assertEqual(["package.json"], target["existing_rum_markers"]["browser-rum-package"])

    def test_runtime_marker_ignores_comments_and_string_examples(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("src/rum.d.ts", "declare const DATAFLUX_RUM: unknown;\n")
        self.write(
            "src/rum.ts",
            """
            // DATAFLUX_RUM.init({})
            const example = `datafluxRum.init({
              ${receiver === 'public' ? `site: '${site}'` : `datakitOrigin: '${origin}'`}
            })`;
            window.DATAFLUX_RUM.onReady(() => window.DATAFLUX_RUM.init({}));
            """,
        )

        target = self.targets()[0]

        self.assertEqual(["src/rum.ts"], target["existing_rum_markers"]["browser-rum-global"])
        self.assertNotIn("javascript-rum-api", target["existing_rum_markers"])

    def test_detects_runtime_markers_in_modern_web_source_extensions(self):
        self.write("package.json", json.dumps({"dependencies": {"react": "19.0.0"}}))
        self.write("src/main.jsx", "window.DATAFLUX_RUM.init({})\n")
        self.write("src/bootstrap.mjs", "datafluxRum.init({})\n")
        self.write(
            "src/App.svelte",
            """
            <p>DATAFLUX_RUM.init({}) is documentation, not executable code.</p>
            <script>
              window.DATAFLUX_RUM.init({})
            </script>
            """,
        )

        target = self.targets()[0]

        self.assertEqual(
            ["src/App.svelte", "src/main.jsx"],
            target["existing_rum_markers"]["browser-rum-global"],
        )
        self.assertEqual(
            ["src/bootstrap.mjs"],
            target["existing_rum_markers"]["javascript-rum-api"],
        )

    def test_svelte_markup_example_is_not_a_runtime_marker(self):
        self.write("package.json", json.dumps({"dependencies": {"svelte": "5.0.0"}}))
        self.write("src/App.svelte", "<p>Example: DATAFLUX_RUM.init({})</p>\n")

        target = self.targets()[0]

        self.assertEqual({}, target["existing_rum_markers"])

    def test_flutter_owns_native_subprojects_and_keeps_web_as_variant(self):
        self.write("pubspec.yaml", "name: mobile\n\ndependencies:\n  flutter:\n    sdk: flutter\n")
        self.write("web/index.html", "<html></html>\n")
        self.write("android/app/build.gradle", "plugins { id 'com.android.application' }\n")
        self.write("android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write("ios/Runner.xcodeproj/project.pbxproj", "// project\n")

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("flutter", targets[0]["platform"])
        self.assertEqual(["android", "ios", "web"], targets[0]["variants"])
        self.assertEqual(["android", "ios", "web"], targets[0]["application_id_slots"])

    def test_excludes_generated_and_example_projects(self):
        self.write("build/web/package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("examples/demo/package.json", json.dumps({"dependencies": {"react": "19.0.0"}}))

        result = DETECTOR.detect(self.root)

        self.assertEqual([], result["targets"])
        self.assertTrue(any("No supported" in warning for warning in result["warnings"]))

    def test_detects_react_native_as_one_target_with_two_slots(self):
        self.write("apps/mobile/package.json", json.dumps({"dependencies": {"react-native": "0.80.0"}}))
        self.write("apps/mobile/android/app/build.gradle", "plugins { id 'com.android.application' }\n")
        self.write("apps/mobile/android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write("apps/mobile/ios/App.xcodeproj/project.pbxproj", "// project\n")

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("react-native", targets[0]["platform"])
        self.assertEqual(["android", "ios"], targets[0]["application_id_slots"])

    def test_detects_hbuilder_uniapp_without_package_json(self):
        self.write("apps/uni/manifest.json", '{"app-plus": {}, "h5": {}}\n')
        self.write("apps/uni/pages.json", '{"pages": []}\n')

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("uniapp", targets[0]["platform"])
        self.assertEqual(["android", "ios", "web"], targets[0]["application_id_slots"])

    def test_detects_native_desktop_and_miniapp_families(self):
        self.write("apps/mini/project.config.json", "{}\n")
        self.write("apps/mini/app.json", "{}\n")
        self.write("apps/android/app/build.gradle.kts", "plugins { id(\"com.android.application\") }\n")
        self.write("apps/android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write(
            "apps/apple/App.xcodeproj/project.pbxproj",
            "IPHONEOS_DEPLOYMENT_TARGET = 17.0;\nSDKROOT = iphoneos;\n",
        )
        self.write("apps/harmony/build-profile.json5", "{}\n")
        self.write("apps/harmony/oh-package.json5", "{}\n")
        self.write("apps/cpp/CMakeLists.txt", "project (Desktop LANGUAGES CXX)\nadd_executable (desktop main.cpp)\n")
        self.write("apps/unity/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.0\n")

        targets = self.targets()
        platforms = {target["platform"] for target in targets}

        self.assertEqual(
            {"miniapp", "android", "apple", "harmonyos", "cpp", "unity"},
            platforms,
        )
        apple = next(target for target in targets if target["platform"] == "apple")
        self.assertEqual(["ios"], apple["application_id_slots"])


if __name__ == "__main__":
    unittest.main()
