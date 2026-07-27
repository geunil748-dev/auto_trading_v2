"""Explicit protected settings for MSSQL migrations and temporary test databases."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from auto_trading_v2.config.loader import (
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
    _read_env_file,
    _select_env_file,
)
from auto_trading_v2.config.models import MssqlAdministrationSettings, SecretValue
from auto_trading_v2.config.validation import validate_mssql_url


def _resolve(
    key: str,
    *,
    explicit: Mapping[str, str],
    dotenv: Mapping[str, str],
    process: Mapping[str, str],
) -> str | None:
    if key in explicit:
        return explicit[key]
    if key in dotenv:
        return dotenv[key]
    return process.get(key)


def _validated_url(key: str, raw: str | None) -> SecretValue | None:
    if raw is None or not raw.strip():
        return None
    return validate_mssql_url(key, raw, expected_database="master")


def load_mssql_administration_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> MssqlAdministrationSettings:
    """Load protected administration URLs without opening a database connection."""

    selected = _select_env_file(env_file)
    dotenv = _read_env_file(selected)
    explicit = {} if environ is None else environ
    process = os.environ if process_environ is None else process_environ

    admin_raw = _resolve(
        MSSQL_ADMIN_URL_KEY,
        explicit=explicit,
        dotenv=dotenv,
        process=process,
    )
    test_admin_raw = _resolve(
        MSSQL_TEST_ADMIN_URL_KEY,
        explicit=explicit,
        dotenv=dotenv,
        process=process,
    )
    return MssqlAdministrationSettings(
        admin_url=_validated_url(MSSQL_ADMIN_URL_KEY, admin_raw),
        test_admin_url=_validated_url(MSSQL_TEST_ADMIN_URL_KEY, test_admin_raw),
    )
