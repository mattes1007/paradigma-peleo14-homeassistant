"""Run the unchanged official HACS JSON schemas against this working tree.

This is a local schema check, not the GitHub HACS action/repository validator.
Pass the path to a downloaded hacs/integration checkout as the sole argument.
Only the source package initializer is bypassed to avoid starting HACS itself.
"""
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType

source = Path(sys.argv[1]).resolve() / "custom_components/hacs"
root = Path(__file__).resolve().parents[2]
package = ModuleType("qa_hacs_source")
package.__path__ = [str(source)]
sys.modules[package.__name__] = package
schemas = importlib.import_module("qa_hacs_source.utils.validate")
for path, schema in (
    (root / "hacs.json", schemas.HACS_MANIFEST_JSON_SCHEMA),
    (root / "custom_components/paradigma/manifest.json", schemas.INTEGRATION_MANIFEST_JSON_SCHEMA),
):
    schema(json.loads(path.read_text()))
    print(f"Official HACS schema PASS: {path.relative_to(root)}")
print("Full GitHub HACS action NOT executed; this check covers the two JSON schemas only.")
