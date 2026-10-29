"""The domain core imports no framework code (docs/v2/03-ARCHITECTURE.md, rule 1).

These modules take and return plain data, so they can be tested without a database and can't
grow hidden dependencies on Django, DRF or another app's models. Walking the AST is cheaper
than an import-linter dependency.
"""

import ast
from pathlib import Path

import pytest

APPS = Path(__file__).resolve().parents[2]
DOMAIN_CORE = [
    *sorted((APPS / "versioning" / "domain").glob("*.py")),
    APPS / "sharing" / "policy.py",
    APPS / "common" / "errors.py",
]
FORBIDDEN = ("django", "rest_framework", "drf_spectacular", "allauth", "apps", "config")
ALLOWED = ("apps.common.errors",)  # framework-free itself


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: only siblings inside the same domain package
                if node.level > 1 or path.parent.name != "domain":
                    modules.append("." * node.level + (node.module or ""))
            elif node.module:
                modules.append(node.module)
    return modules


@pytest.mark.parametrize("path", DOMAIN_CORE, ids=lambda p: str(p.relative_to(APPS)))
def test_domain_core_imports_no_framework(path):
    bad = [
        module
        for module in imported_modules(path)
        if module.startswith(".")
        or (module.split(".")[0] in FORBIDDEN and not module.startswith(ALLOWED))
    ]
    assert bad == [], f"{path.name} imports {bad}"


def test_the_check_catches_forbidden_imports(tmp_path):
    sample = tmp_path / "domain" / "bad.py"
    sample.parent.mkdir()
    sample.write_text("from django.db import models\nimport rest_framework\nfrom ..x import y\n")
    assert imported_modules(sample) == ["django.db", "rest_framework", "..x"]
