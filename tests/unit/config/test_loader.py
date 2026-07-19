from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import auto_trading_v2.config as config_package
import auto_trading_v2.config.loader as loader_module
from auto_trading_v2.config import (
    MissingSettingError,
    SettingSource,
    UnsafeSettingError,
    inspect_environment_file,
    load_settings,
    load_settings_with_diagnostics,
    repository_env_file,
)
from auto_trading_v2.config.loader import (
    DB_PROVIDER_KEY,
    ENVIRONMENT_KEY,
    LOG_LEVEL_KEY,
)

from .helpers import DOTNET_DATABASE_ENVIRONMENT, valid_process_environment, write_env


def test_explicit_env_file_loads_repository_style_settings(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, {**DOTNET_DATABASE_ENVIRONMENT, ENVIRONMENT_KEY: "paper"})

    result = load_settings_with_diagnostics(env_file, process_environ={})

    assert result.settings.environment == "paper"
    assert result.diagnostics.source_for(DB_PROVIDER_KEY) is SettingSource.DOTENV
    assert result.diagnostics.source_for(LOG_LEVEL_KEY) is SettingSource.DEFAULT


def test_repository_env_path_is_independent_of_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = repository_env_file()
    monkeypatch.chdir(tmp_path)
    assert repository_env_file() == expected
    assert expected == loader_module.REPOSITORY_ROOT / ".env"


@pytest.mark.parametrize("content", [None, "", "# UTF-8 한글 주석\n"])
def test_missing_or_empty_env_reports_required_database_without_parent_search(
    tmp_path: Path,
    content: str | None,
) -> None:
    env_file = tmp_path / "child" / ".env"
    env_file.parent.mkdir()
    if content is not None:
        env_file.write_text(content, encoding="utf-8")
    write_env(tmp_path / ".env", DOTNET_DATABASE_ENVIRONMENT)

    with pytest.raises(MissingSettingError) as caught:
        load_settings(env_file, process_environ={})

    assert caught.value.key == DB_PROVIDER_KEY


def test_utf8_bom_and_korean_comments_are_supported(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    content = "# 한글 설정 설명\n" + "\n".join(
        f"{key}={value}" for key, value in DOTNET_DATABASE_ENVIRONMENT.items()
    )
    env_file.write_text(f"{content}\n", encoding="utf-8-sig")

    settings = load_settings(env_file, process_environ={})

    assert settings.environment == "development"


def test_precedence_is_explicit_then_dotenv_then_process_then_default(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        {
            **DOTNET_DATABASE_ENVIRONMENT,
            ENVIRONMENT_KEY: "paper",
        },
    )
    process = valid_process_environment(**{ENVIRONMENT_KEY: "test", LOG_LEVEL_KEY: "warning"})

    result = load_settings_with_diagnostics(
        env_file,
        {ENVIRONMENT_KEY: "development"},
        process_environ=process,
    )

    assert result.settings.environment == "development"
    assert result.settings.log_level == "WARNING"
    assert result.diagnostics.source_for(ENVIRONMENT_KEY) is SettingSource.EXPLICIT
    assert result.diagnostics.source_for(DB_PROVIDER_KEY) is SettingSource.DOTENV
    assert result.diagnostics.source_for(LOG_LEVEL_KEY) is SettingSource.PROCESS


def test_dotenv_key_presence_wins_even_when_value_is_blank(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, {DB_PROVIDER_KEY: ""})

    with pytest.raises(MissingSettingError):
        load_settings(env_file, process_environ=valid_process_environment())


def test_inventory_returns_counts_without_unknown_names(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        {
            DB_PROVIDER_KEY: "dotnet",
            "AUTO_TRADING_V2_FUTURE_OPTION": "value",
            "LEGACY_CREDENTIAL_NAME": "value",
        },
    )

    inventory = inspect_environment_file(env_file)

    assert inventory.canonical_configured_count == 1
    assert inventory.canonical_missing_count == len(loader_module.CANONICAL_KEYS) - 1
    assert inventory.unknown_key_count == 2
    assert inventory.legacy_key_count == 1
    assert "FUTURE_OPTION" not in repr(inventory)
    assert "LEGACY_CREDENTIAL_NAME" not in repr(inventory)


def test_symlink_env_file_is_rejected_without_following_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.env"
    write_env(target, DOTNET_DATABASE_ENVIRONMENT)
    link = tmp_path / ".env"
    try:
        link.symlink_to(target)
    except OSError:
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda path: path == link or original_is_symlink(path),
        )

    with pytest.raises(UnsafeSettingError):
        load_settings(link, process_environ={})


def test_package_import_does_not_trigger_dotenv_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("dotenv must not load during package import")

    monkeypatch.setattr(loader_module, "dotenv_values", fail_if_called)
    importlib.reload(config_package)
