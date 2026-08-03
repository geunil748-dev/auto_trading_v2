"""Explicit protected settings for MSSQL migrations and temporary test databases."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from auto_trading_v2.config.loader import _read_env_file, _select_env_file
from auto_trading_v2.config.models import (
    MssqlAdministrationSettings,
    MssqlAdministrationTransport,
    SecretValue,
)
from auto_trading_v2.config.mssql_administration_keys import (
    MSSQL_ADMIN_TRANSPORT_KEY,
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_TRANSPORT_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
)
from auto_trading_v2.config.validation import normalize_choice, validate_mssql_url


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


def _validated_transport(key: str, raw: str | None) -> MssqlAdministrationTransport:
    if raw is None or not raw.strip():
        return MssqlAdministrationTransport.TCP_URL
    value = normalize_choice(
        key,
        raw,
        {transport.value for transport in MssqlAdministrationTransport},
    )
    return MssqlAdministrationTransport(value)


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
    admin_transport_raw = _resolve(
        MSSQL_ADMIN_TRANSPORT_KEY,
        explicit=explicit,
        dotenv=dotenv,
        process=process,
    )
    test_admin_transport_raw = _resolve(
        MSSQL_TEST_ADMIN_TRANSPORT_KEY,
        explicit=explicit,
        dotenv=dotenv,
        process=process,
    )
    return MssqlAdministrationSettings(
        admin_url=_validated_url(MSSQL_ADMIN_URL_KEY, admin_raw),
        test_admin_url=_validated_url(MSSQL_TEST_ADMIN_URL_KEY, test_admin_raw),
        admin_transport=_validated_transport(
            MSSQL_ADMIN_TRANSPORT_KEY,
            admin_transport_raw,
        ),
        test_admin_transport=_validated_transport(
            MSSQL_TEST_ADMIN_TRANSPORT_KEY,
            test_admin_transport_raw,
        ),
    )
