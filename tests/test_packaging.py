"""Offline checks for the HACS repository contract; no HA imports or network."""
import json
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "paradigma"
REPOSITORY = "https://github.com/mattes1007/paradigma-peleo14-homeassistant"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def leaf_paths(value, prefix=()):
    if isinstance(value, dict):
        return {path for key, child in value.items()
                for path in leaf_paths(child, prefix + (key,))}
    return {prefix}


class PackagingTests(unittest.TestCase):
    def test_single_integration_and_runtime_files(self):
        components = [path for path in (ROOT / "custom_components").iterdir()
                      if path.is_dir() and path.name != "__pycache__"]
        self.assertEqual([path.name for path in components], ["paradigma"])
        for name in ("__init__.py", "config_flow.py", "hub.py", "sensor.py",
                     "number.py", "switch.py", "water_heater.py", "manifest.json",
                     "strings.json", "translations/de.json", "translations/en.json"):
            with self.subTest(file=name):
                self.assertTrue((COMPONENT / name).is_file())

    def test_manifest_metadata(self):
        manifest = read_json(COMPONENT / "manifest.json")
        self.assertEqual(manifest["domain"], COMPONENT.name)
        self.assertEqual(manifest["name"], "Paradigma PELEO 14")
        self.assertEqual(manifest["codeowners"], ["@mattes1007"])
        self.assertEqual(manifest["documentation"], REPOSITORY)
        self.assertEqual(manifest["issue_tracker"], REPOSITORY + "/issues")
        self.assertEqual(manifest["version"], "2.0.0-beta.1")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["requirements"], ["pymodbus==3.13.1"])
        self.assertEqual(manifest["iot_class"], "local_polling")
        self.assertEqual(manifest["integration_type"], "device")

    def test_direct_hacs_installation(self):
        hacs = read_json(ROOT / "hacs.json")
        self.assertFalse(hacs["content_in_root"])
        self.assertFalse(hacs["zip_release"])
        self.assertEqual(hacs["homeassistant"], "2026.10.0")
        self.assertEqual(hacs["name"], read_json(COMPONENT / "manifest.json")["name"])
        self.assertNotIn("filename", hacs)
        self.assertNotIn("render_readme", hacs)

    def test_brand_assets_are_valid_and_match_existing_assets(self):
        for name in ("icon.png", "logo.png"):
            with self.subTest(asset=name):
                data = (COMPONENT / "brand" / name).read_bytes()
                self.assertEqual(data, (ROOT / name).read_bytes())
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                width, height = struct.unpack(">II", data[16:24])
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                if name == "icon.png":
                    self.assertEqual(width, height)

    def test_translation_keys_and_values(self):
        base = read_json(COMPONENT / "strings.json")
        for language in ("de", "en"):
            translated = read_json(COMPONENT / "translations" / f"{language}.json")
            with self.subTest(language=language):
                self.assertEqual(leaf_paths(base), leaf_paths(translated))
                self.assertEqual(translated["config"]["step"]["user"]["data"].keys(),
                                 base["config"]["step"]["user"]["data"].keys())
                for path in leaf_paths(translated):
                    value = translated
                    for key in path:
                        value = value[key]
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), path)

    def test_documentation_links_and_version(self):
        files = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
        for file in files:
            for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(file=file.name, target=target):
                    self.assertTrue((file.parent / target.split("#", 1)[0]).exists())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(read_json(COMPONENT / "manifest.json")["version"], readme)
        self.assertIn(REPOSITORY, readme)
        self.assertTrue((ROOT / "LICENSE").is_file())

    def test_old_maintainer_only_remains_in_attribution(self):
        files = [*(ROOT / ".github").rglob("*.yml"),
                 *(ROOT / ".github").rglob("*.yaml"),
                 COMPONENT / "manifest.json", ROOT / "hacs.json"]
        for file in files:
            with self.subTest(file=file.relative_to(ROOT)):
                self.assertNotIn("nussfuellung", file.read_text(encoding="utf-8"))
        self.assertEqual((ROOT / ".github" / "CODEOWNERS").read_text().strip(),
                         "* @mattes1007")
