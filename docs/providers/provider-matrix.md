# Market-data provider matrix

`verified_at=2026-07-29`. Provider limits and product access can change; re-check official terms
before enabling a provider.

| Provider code / candidate | Official | Current role | P3 status |
| --- | --- | --- | --- |
| `TWELVE_DATA_TIME_SERIES` | Yes | `PRIMARY_FEATURE_SOURCE` | Sequential P3 batch source with budget preflight |
| `ALPACA_IEX_STOCK_BARS` | Yes | `VALIDATION_ONLY` | Implemented; rejected as a P3 feature source |
| `YAHOO_FINANCE_EXPERIMENTAL` | No | `EXPERIMENTAL` research candidate | Not implemented; never an automatic fallback |
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

P3 estimates the maximum batch credit cost before the first symbol. Unknown or insufficient daily
budget fails closed with zero network requests. Minute limits remain the provider limiter's
sequential wait policy. Members are never processed concurrently, and a run never changes provider.

Twelve Data free operational defaults are 8 credits per minute and 800 credits per UTC day. They
are configurable adapter safeguards rather than Domain rules. See the
[Twelve Data provider contract](twelve-data.md).
Alpaca request throttling defaults to 200 requests per rolling minute as an adapter safeguard.
See the [Alpaca IEX validation contract](alpaca-iex.md).
