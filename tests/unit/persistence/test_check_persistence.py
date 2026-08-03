from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / "scripts" / "check_persistence.py"


def test_persistence_diagnostic_contains_only_read_operations() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    forbidden_methods = {"begin", "commit", "rollback", "execute_many"}
    forbidden_names = {
        "create_development_database",
        "create_test_database",
        "drop_test_database",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_methods
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_names


def test_persistence_diagnostic_does_not_render_errors_or_settings() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "str(exc)" not in source
    assert "repr(exc)" not in source
    assert "database_url.reveal" not in source
    assert "admin_url" not in source
    assert "test_admin_url" not in source
