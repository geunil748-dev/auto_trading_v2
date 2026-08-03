"""Canonical configuration keys for independent market-data adapters."""

from auto_trading_v2.config.alpaca_market_data_keys import ALPACA_MARKET_DATA_KEYS
from auto_trading_v2.config.twelve_data_keys import TWELVE_DATA_KEYS

MARKET_DATA_KEYS = frozenset({*ALPACA_MARKET_DATA_KEYS, *TWELVE_DATA_KEYS})
