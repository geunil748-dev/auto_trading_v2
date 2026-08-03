import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOMAIN_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2" / "domain" / "recommendations"
SERVICE = (
    PROJECT_ROOT / "src" / "auto_trading_v2" / "application" / "services" / "recommendation.py"
)


def test_recommendation_domain_is_framework_and_runtime_independent() -> None:
    imports: set[str] = set()
    text = ""
    for path in DOMAIN_ROOT.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        text += source
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])

    assert imports.isdisjoint(
        {"sqlalchemy", "alembic", "clr", "pythonnet", "os", "requests", "httpx"}
    )
    for forbidden in ("TradeIntent", "broker", "KIS", "Telegram", ".env"):
        assert forbidden not in text


def test_recommendation_service_has_no_execution_or_notification_link() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    for forbidden in (
        "TradeIntent",
        "PaperOrder",
        "PaperFill",
        "PaperPosition",
        "broker",
        "KIS",
        "Telegram",
    ):
        assert forbidden not in text


def test_changed_python_files_are_utf8_without_bom_and_at_most_300_lines() -> None:
    changed = [
        path
        for path in PROJECT_ROOT.rglob("*.py")
        if "recommendation" in path.name.lower()
        or "recommendations" in {part.lower() for part in path.parts}
    ]
    assert changed
    for path in changed:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        text = raw.decode("utf-8")
        assert len(text.splitlines()) <= 300, path
        markers = (
            chr(0xFFFD) * 3,
            chr(0xFFFD),
            chr(0x00EC),
            chr(0x00EA),
            chr(0x00ED),
        )
        assert not any(marker in text for marker in markers), path
