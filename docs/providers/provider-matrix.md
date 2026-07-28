# Market-data provider matrix

`verified_at=2026-07-28`. Provider limits and product access can change; re-check official terms
before enabling a provider.

| Provider code / candidate | Official | Current role | P2.1A status |
| --- | --- | --- | --- |
| `TWELVE_DATA_TIME_SERIES` | Yes | Completed US-equity daily price input | Actual `/time_series` adapter implemented |
| `ALPACA` | Yes | Future second-source validation; Basic feed coverage must be evaluated | Not implemented |
| `YAHOO_FINANCE_EXPERIMENTAL` | No | Research/personal-use experimental fallback candidate | Not implemented; never a production canonical default |
| `KIS` | Yes | Future RAW daily adapter after market-data credentials are available | Not implemented; existing clean KIS worktree preserved |
| `TOSS_SECURITIES` | Yes | Future account, actual execution, and user-action integration after approval/access | Not implemented |
| `ALPHA_VANTAGE` | Yes | Possible auxiliary source; small free daily budget and adjusted daily premium limits | Not implemented |
| `FINNHUB` | Yes | Future company-news/context feature source | Not implemented |
| `SEC_EDGAR` | Yes | Future filings/XBRL feature source | Not implemented |
| `FRED` | Yes | Future macroeconomic feature source | Not implemented |

Selection is explicit: the caller supplies a provider code and receives that provider's independent
outcome. The system does not call Yahoo, Alpaca, KIS, or any other source after a Twelve Data error
or credit rejection. Different providers never contribute bars to the same technical
`FeatureSnapshot`.

Twelve Data free operational defaults are 8 credits per minute and 800 credits per UTC day. They
are configurable adapter safeguards rather than Domain rules. See the
[Twelve Data provider contract](twelve-data.md).
