"""Official source metadata for the 2018-2026 US equity calendar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfficialScheduleSource:
    code: str
    title: str
    url: str


OFFICIAL_SOURCES = (
    OfficialScheduleSource(
        "NYSE_2018_2020_CALENDAR",
        "NYSE Group 2018, 2019 and 2020 Holiday and Early Closings Calendar",
        "https://ir.theice.com/press/news-details/2017/NYSE-Group-Announces-2018-2019-and-2020-Holiday-and-Early-Closings-Calendar/default.aspx",
    ),
    OfficialScheduleSource(
        "NYSE_2021_2023_CALENDAR",
        "NYSE Group 2021, 2022 and 2023 Holiday and Early Closings Calendar",
        "https://ir.theice.com/press/news-details/2020/NYSE-Group-Announces-2021-2022-and-2023-Holiday-and-Early-Closings-Calendar/default.aspx",
    ),
    OfficialScheduleSource(
        "NYSE_2022_2024_CALENDAR",
        "NYSE Group 2022, 2023 and 2024 Holiday and Early Closings Calendar",
        "https://ir.theice.com/press/news-details/2021/NYSE-Group-Announces-2022-2023-and-2024-Holiday-and-Early-Closings-Calendar/default.aspx",
    ),
    OfficialScheduleSource(
        "NYSE_2023_2025_CALENDAR",
        "NYSE Group 2023, 2024 and 2025 Holiday and Early Closings Calendar",
        "https://ir.theice.com/press/news-details/2022/NYSE-Group-Announces-2023-2024-and-2025-Holiday-and-Early-Closings-Calendar/default.aspx",
    ),
    OfficialScheduleSource(
        "NYSE_2026_CALENDAR",
        "NYSE Holidays and Trading Hours",
        "https://www.nyse.com/markets/hours-calendars",
    ),
    OfficialScheduleSource(
        "NASDAQ_2018_ALERTS",
        "Nasdaq 2018 Equity Trader holiday and national mourning alerts",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2018-98",
    ),
    OfficialScheduleSource(
        "NASDAQ_2019_ALERTS",
        "Nasdaq 2019 Equity Trader holiday alerts",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2019-93",
    ),
    OfficialScheduleSource(
        "NASDAQ_2020_ALERTS",
        "Nasdaq 2020 Equity Trader holiday alerts",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2020-85",
    ),
    *(
        OfficialScheduleSource(
            f"NASDAQ_{year}_CALENDAR",
            f"Nasdaq Trading Calendar {year}",
            f"https://www.nasdaqtrader.com/content/technicalsupport/{year}tradingcalendar.pdf",
        )
        for year in range(2021, 2025)
    ),
    OfficialScheduleSource(
        "NASDAQ_2025_CALENDAR",
        "Nasdaq Trading Calendar 2025",
        "https://www.nasdaqtrader.com/content/technicalsupport/tradingcalendar.pdf",
    ),
    OfficialScheduleSource(
        "NASDAQ_2026_CALENDAR",
        "Nasdaq U.S. Equity and Options Markets Holiday Schedule 2026",
        "https://www.nasdaqtrader.com/Trader.aspx?id=Calendar",
    ),
    OfficialScheduleSource(
        "NYSE_2018_MOURNING_NOTICE",
        "NYSE national day of mourning notice for President George H. W. Bush",
        "https://www.nyse.com/publicdocs/nyse/markets/arca-options/rule-interpretations/2018/NYSE%20Arca%20Options%2018-06.pdf",
    ),
    OfficialScheduleSource(
        "NASDAQ_2018_MOURNING_NOTICE",
        "Nasdaq national day of mourning notice for President George H. W. Bush",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2018-98",
    ),
    OfficialScheduleSource(
        "NYSE_2025_MOURNING_NOTICE",
        "NYSE national day of mourning notice for President Jimmy Carter",
        "https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx",
    ),
    OfficialScheduleSource(
        "NASDAQ_2025_MOURNING_NOTICE",
        "Nasdaq national day of mourning notice for President Jimmy Carter",
        "https://ir.nasdaq.com/news-releases/news-release-details/nasdaq-announces-closure-its-us-markets-honor-national-day-0",
    ),
)
