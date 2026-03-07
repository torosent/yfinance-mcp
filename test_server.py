"""Tests for all YFinance MCP Server tools using mocked yfinance data."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from server import (
    batch_download,
    get_analyst_estimates,
    get_analyst_ratings,
    get_calendar,
    get_dividends,
    get_earnings,
    get_esg_data,
    get_financials,
    get_historical_data,
    get_insider_holdings,
    get_multiple_quotes,
    get_news,
    get_option_chain,
    get_recommendations,
    get_sec_filings,
    get_splits,
    get_stock_info,
    screen_stocks,
    search_stocks,
)

# ---------------------------------------------------------------------------
# Helpers to build mock objects
# ---------------------------------------------------------------------------

SAMPLE_INFO = {
    "longName": "Apple Inc.",
    "currentPrice": 250.0,
    "previousClose": 248.0,
    "open": 249.0,
    "dayHigh": 252.0,
    "dayLow": 247.0,
    "marketCap": 3_000_000_000_000,
    "trailingPE": 28.5,
    "forwardPE": 26.0,
    "pegRatio": 1.5,
    "priceToSalesTrailing12Months": 8.0,
    "priceToBook": 40.0,
    "enterpriseValue": 3_100_000_000_000,
    "enterpriseToRevenue": 8.5,
    "enterpriseToEbitda": 22.0,
    "profitMargins": 0.25,
    "operatingMargins": 0.30,
    "grossMargins": 0.45,
    "ebitdaMargins": 0.35,
    "trailingEps": 6.5,
    "forwardEps": 7.0,
    "returnOnAssets": 0.20,
    "returnOnEquity": 1.5,
    "dividendYield": 0.005,
    "dividendRate": 1.0,
    "payoutRatio": 0.15,
    "exDividendDate": 1700000000,
    "debtToEquity": 180.0,
    "currentRatio": 1.0,
    "quickRatio": 0.9,
    "totalCash": 60_000_000_000,
    "totalDebt": 110_000_000_000,
    "freeCashflow": 100_000_000_000,
    "operatingCashflow": 120_000_000_000,
    "revenueGrowth": 0.08,
    "earningsGrowth": 0.10,
    "revenuePerShare": 25.0,
    "bookValue": 4.0,
    "fiftyTwoWeekHigh": 260.0,
    "fiftyTwoWeekLow": 160.0,
    "52WeekChange": 0.40,
    "volume": 50_000_000,
    "averageVolume": 55_000_000,
    "averageVolume10days": 53_000_000,
    "beta": 1.2,
    "sharesOutstanding": 15_000_000_000,
    "floatShares": 14_800_000_000,
    "sharesShort": 100_000_000,
    "shortRatio": 1.5,
    "shortPercentOfFloat": 0.007,
    "targetHighPrice": 300.0,
    "targetLowPrice": 200.0,
    "targetMeanPrice": 270.0,
    "targetMedianPrice": 275.0,
    "recommendationMean": 2.0,
    "recommendationKey": "buy",
    "numberOfAnalystOpinions": 40,
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "United States",
    "website": "https://www.apple.com",
    "fullTimeEmployees": 160000,
    "businessSummary": "Apple Inc. designs, manufactures, and markets smartphones.",
}


def _make_history_df():
    dates = pd.date_range("2024-01-02", periods=3, freq="D")
    return pd.DataFrame(
        {
            "Open": [150.0, 151.0, 152.0],
            "High": [155.0, 156.0, 157.0],
            "Low": [149.0, 150.0, 151.0],
            "Close": [154.0, 155.0, 156.0],
            "Volume": [1000000, 1100000, 1200000],
        },
        index=dates,
    )


def _make_dividends_series():
    dates = pd.date_range("2023-01-15", periods=4, freq="QE")
    return pd.Series([0.23, 0.24, 0.24, 0.25], index=dates, name="Dividends")


def _make_splits_series():
    dates = pd.date_range("2020-08-31", periods=1)
    return pd.Series([4.0], index=dates, name="Stock Splits")


def _make_income_stmt():
    dates = pd.to_datetime(["2024-09-30", "2023-09-30"])
    return pd.DataFrame(
        {"Total Revenue": [400e9, 380e9], "Net Income": [100e9, 95e9]},
        index=dates,
    ).T


def _make_balance_sheet():
    dates = pd.to_datetime(["2024-09-30", "2023-09-30"])
    return pd.DataFrame(
        {"Total Assets": [350e9, 340e9], "Total Liabilities": [280e9, 270e9]},
        index=dates,
    ).T


def _make_cashflow():
    dates = pd.to_datetime(["2024-09-30", "2023-09-30"])
    return pd.DataFrame(
        {"Operating Cash Flow": [120e9, 110e9], "Free Cash Flow": [100e9, 90e9]},
        index=dates,
    ).T


def _make_recommendations_df():
    return pd.DataFrame(
        {
            "period": ["0m", "-1m"],
            "strongBuy": [15, 14],
            "buy": [20, 19],
            "hold": [5, 6],
            "sell": [1, 1],
            "strongSell": [0, 0],
        }
    )


def _make_options_df():
    return pd.DataFrame(
        {
            "contractSymbol": ["AAPL240315C00150000"],
            "strike": [150.0],
            "lastPrice": [5.0],
            "bid": [4.8],
            "ask": [5.2],
            "volume": [1000],
            "openInterest": [5000],
            "impliedVolatility": [0.25],
            "inTheMoney": [True],
        }
    )


def _make_estimates_df():
    return pd.DataFrame(
        {"avg": [6.5, 7.0], "low": [5.5, 6.0], "high": [7.5, 8.0]},
        index=["Current Quarter", "Next Quarter"],
    )


def _make_upgrades_df():
    dates = pd.to_datetime(["2024-01-15", "2024-02-10"])
    return pd.DataFrame(
        {
            "Firm": ["Morgan Stanley", "Goldman Sachs"],
            "ToGrade": ["Overweight", "Buy"],
            "FromGrade": ["Equal-Weight", "Neutral"],
            "Action": ["up", "up"],
        },
        index=dates,
    )


def _make_insider_transactions_df():
    return pd.DataFrame(
        {
            "Insider": ["Tim Cook"],
            "Position": ["CEO"],
            "Transaction": ["Sale"],
            "Start Date": [datetime(2024, 1, 10)],
            "Shares": [50000],
            "Value": [12500000],
        }
    )


def _make_institutional_holders_df():
    return pd.DataFrame(
        {
            "Holder": ["Vanguard Group"],
            "Shares": [1_300_000_000],
            "pctHeld": [0.08],
            "Value": [325_000_000_000],
        }
    )


def _make_major_holders_df():
    return pd.DataFrame({"Value": {0: "0.07%", 1: "60.00%"}})


def _make_sec_filings():
    return [
        {
            "type": "10-K",
            "date": "2024-10-31",
            "title": "Annual Report",
            "edgarUrl": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
        },
        {
            "type": "10-Q",
            "date": "2024-07-31",
            "title": "Quarterly Report",
            "edgarUrl": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
        },
    ]


def _make_calendar():
    return {
        "Earnings Date": [datetime(2025, 4, 24), datetime(2025, 4, 28)],
        "Ex-Dividend Date": datetime(2025, 2, 7),
        "Dividend Date": datetime(2025, 2, 13),
        "Earnings Average": 2.35,
        "Earnings Low": 2.20,
        "Earnings High": 2.50,
        "Revenue Average": 124_000_000_000,
        "Revenue Low": 120_000_000_000,
        "Revenue High": 128_000_000_000,
    }


def _make_news():
    return [
        {
            "content": {
                "title": "Apple Announces New Product",
                "canonicalUrl": {"url": "https://example.com/news/1"},
                "provider": {"displayName": "Reuters"},
                "pubDate": "2024-03-01T12:00:00Z",
                "contentType": "STORY",
                "thumbnail": {
                    "resolutions": [{"url": "https://example.com/img.jpg"}]
                },
                "summary": "Apple unveiled a new product today.",
            }
        },
        {
            "content": {
                "title": "Apple Stock Rises",
                "canonicalUrl": {"url": "https://example.com/news/2"},
                "provider": {"displayName": "Bloomberg"},
                "pubDate": "2024-03-02T10:00:00Z",
                "contentType": "STORY",
                "thumbnail": None,
                "summary": "Shares rose 3% in early trading.",
            }
        },
    ]


def _build_ticker_mock(**overrides):
    """Build a mock yf.Ticker with sensible defaults."""
    ticker = MagicMock()
    ticker.info = overrides.get("info", SAMPLE_INFO)
    ticker.history.return_value = overrides.get("history", _make_history_df())
    ticker.dividends = overrides.get("dividends", _make_dividends_series())
    ticker.splits = overrides.get("splits", _make_splits_series())
    ticker.income_stmt = overrides.get("income_stmt", _make_income_stmt())
    ticker.quarterly_income_stmt = overrides.get(
        "quarterly_income_stmt", _make_income_stmt()
    )
    ticker.balance_sheet = overrides.get("balance_sheet", _make_balance_sheet())
    ticker.quarterly_balance_sheet = overrides.get(
        "quarterly_balance_sheet", _make_balance_sheet()
    )
    ticker.cashflow = overrides.get("cashflow", _make_cashflow())
    ticker.quarterly_cashflow = overrides.get("quarterly_cashflow", _make_cashflow())
    ticker.news = overrides.get("news", _make_news())
    ticker.recommendations = overrides.get(
        "recommendations", _make_recommendations_df()
    )
    ticker.options = overrides.get("options", ("2025-03-21", "2025-04-18"))
    chain_mock = MagicMock()
    chain_mock.calls = _make_options_df()
    chain_mock.puts = _make_options_df()
    ticker.option_chain.return_value = chain_mock
    ticker.earnings_estimate = overrides.get(
        "earnings_estimate", _make_estimates_df()
    )
    ticker.revenue_estimate = overrides.get(
        "revenue_estimate", _make_estimates_df()
    )
    ticker.eps_trend = overrides.get("eps_trend", _make_estimates_df())
    ticker.eps_revisions = overrides.get("eps_revisions", _make_estimates_df())
    ticker.growth_estimates = overrides.get(
        "growth_estimates", _make_estimates_df()
    )
    ticker.analyst_price_targets = overrides.get(
        "analyst_price_targets",
        {"current": 250, "low": 200, "mean": 270, "median": 275, "high": 300},
    )
    ticker.upgrades_downgrades = overrides.get(
        "upgrades_downgrades", _make_upgrades_df()
    )
    ticker.major_holders = overrides.get("major_holders", _make_major_holders_df())
    ticker.insider_transactions = overrides.get(
        "insider_transactions", _make_insider_transactions_df()
    )
    ticker.institutional_holders = overrides.get(
        "institutional_holders", _make_institutional_holders_df()
    )
    ticker.mutualfund_holders = overrides.get(
        "mutualfund_holders", _make_institutional_holders_df()
    )
    ticker.sustainability = overrides.get("sustainability", None)
    ticker.sec_filings = overrides.get("sec_filings", _make_sec_filings())
    ticker.calendar = overrides.get("calendar", _make_calendar())
    return ticker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetStockInfo:
    @patch("server.yf.Ticker")
    async def test_returns_stock_info(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_stock_info("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["current_price"] == 250.0
        assert result["market_cap"] == 3_000_000_000_000
        assert result["sector"] == "Technology"
        assert "error" not in result

    @patch("server.yf.Ticker")
    async def test_lowercased_symbol_is_uppercased(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_stock_info("aapl")
        assert result["symbol"] == "AAPL"
        mock_ticker_cls.assert_called_with("AAPL")

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network error")
        result = await get_stock_info("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetHistoricalData:
    @patch("server.yf.Ticker")
    async def test_returns_ohlcv_data(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_historical_data("AAPL", period="5d", interval="1d")

        assert result["symbol"] == "AAPL"
        assert result["period"] == "5d"
        assert result["interval"] == "1d"
        assert result["count"] == 3
        row = result["data"][0]
        assert "open" in row and "close" in row and "volume" in row

    @patch("server.yf.Ticker")
    async def test_empty_history(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(history=pd.DataFrame())
        result = await get_historical_data("INVALID")
        assert "error" in result

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_historical_data("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetDividends:
    @patch("server.yf.Ticker")
    async def test_returns_dividends(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_dividends("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["count"] == 4
        assert result["dividends"][0]["dividend"] == 0.23

    @patch("server.yf.Ticker")
    async def test_empty_dividends(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(
            dividends=pd.Series([], dtype=float)
        )
        result = await get_dividends("AAPL")
        assert result["dividends"] == []
        assert "message" in result

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_dividends("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetSplits:
    @patch("server.yf.Ticker")
    async def test_returns_splits(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_splits("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["count"] == 1
        assert result["splits"][0]["split_ratio"] == 4.0

    @patch("server.yf.Ticker")
    async def test_empty_splits(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(
            splits=pd.Series([], dtype=float)
        )
        result = await get_splits("AAPL")
        assert result["splits"] == []

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_splits("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetFinancials:
    @patch("server.yf.Ticker")
    async def test_annual_financials(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_financials("MSFT", quarterly=False)

        assert result["symbol"] == "MSFT"
        assert result["quarterly"] is False
        assert result["income_statement"] != {}
        assert result["balance_sheet"] != {}
        assert result["cash_flow"] != {}

    @patch("server.yf.Ticker")
    async def test_quarterly_financials(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_financials("MSFT", quarterly=True)
        assert result["quarterly"] is True

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_financials("MSFT")
        assert "error" in result


@pytest.mark.asyncio
class TestGetEarnings:
    @patch("server.yf.Ticker")
    async def test_returns_earnings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_earnings("GOOGL")

        assert result["symbol"] == "GOOGL"
        assert "annual_earnings" in result
        assert "quarterly_earnings" in result
        assert "note" in result

    @patch("server.yf.Ticker")
    async def test_empty_income_statement(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(
            income_stmt=pd.DataFrame(), quarterly_income_stmt=pd.DataFrame()
        )
        result = await get_earnings("GOOGL")
        assert result["annual_earnings"] == {}
        assert result["quarterly_earnings"] == {}

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_earnings("GOOGL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetNews:
    @patch("server.yf.Ticker")
    async def test_returns_news(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_news("TSLA", count=5)

        assert result["symbol"] == "TSLA"
        assert result["count"] == 2
        assert result["news"][0]["title"] == "Apple Announces New Product"
        assert result["news"][0]["publisher"] == "Reuters"

    @patch("server.yf.Ticker")
    async def test_empty_news(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(news=[])
        result = await get_news("TSLA")
        assert result["news"] == []
        assert "message" in result

    @patch("server.yf.Ticker")
    async def test_count_is_clamped(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_news("TSLA", count=200)
        # count clamped to 100, but only 2 articles available
        assert result["count"] == 2

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_news("TSLA")
        assert "error" in result


@pytest.mark.asyncio
class TestGetRecommendations:
    @patch("server.yf.Ticker")
    async def test_returns_recommendations(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_recommendations("NVDA")

        assert result["symbol"] == "NVDA"
        assert result["count"] == 2
        rec = result["recommendations"][0]
        assert rec["strong_buy"] == 15
        assert rec["total"] == 41

    @patch("server.yf.Ticker")
    async def test_empty_recommendations(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(recommendations=None)
        result = await get_recommendations("NVDA")
        assert result["recommendations"] == []

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_recommendations("NVDA")
        assert "error" in result


@pytest.mark.asyncio
class TestSearchStocks:
    @patch("server.yf.Search")
    async def test_returns_results(self, mock_search_cls):
        mock_search = MagicMock()
        mock_search.quotes = [
            {
                "symbol": "TSLA",
                "longname": "Tesla, Inc.",
                "quoteType": "EQUITY",
                "exchange": "NMS",
                "sector": "Consumer Cyclical",
                "industry": "Auto Manufacturers",
                "score": 100,
                "isYahooFinance": True,
            }
        ]
        mock_search_cls.return_value = mock_search
        result = await search_stocks("Tesla", limit=5)

        assert result["query"] == "Tesla"
        assert result["count"] == 1
        assert result["results"][0]["symbol"] == "TSLA"

    @patch("server.yf.Search")
    async def test_no_results(self, mock_search_cls):
        mock_search = MagicMock()
        mock_search.quotes = []
        mock_search_cls.return_value = mock_search
        result = await search_stocks("xyznonexistent")
        assert result["results"] == []

    @patch("server.yf.Search")
    async def test_handles_exception(self, mock_search_cls):
        mock_search_cls.side_effect = Exception("fail")
        result = await search_stocks("test")
        assert "error" in result


@pytest.mark.asyncio
class TestGetMultipleQuotes:
    @patch("server.yf.Tickers")
    async def test_returns_multiple_quotes(self, mock_tickers_cls):
        mock_tickers = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.info = SAMPLE_INFO
        mock_tickers.tickers = {"AAPL": mock_ticker, "MSFT": mock_ticker}
        mock_tickers_cls.return_value = mock_tickers

        result = await get_multiple_quotes(["AAPL", "MSFT"])
        assert result["count"] == 2
        assert "AAPL" in result["quotes"]
        assert result["quotes"]["AAPL"]["current_price"] == 250.0

    @patch("server.yf.Tickers")
    async def test_handles_exception(self, mock_tickers_cls):
        mock_tickers_cls.side_effect = Exception("fail")
        result = await get_multiple_quotes(["AAPL"])
        assert "error" in result


@pytest.mark.asyncio
class TestGetOptionChain:
    @patch("server.yf.Ticker")
    async def test_lists_expirations(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_option_chain("AAPL")

        assert result["symbol"] == "AAPL"
        assert "expirations" in result
        assert result["count"] == 2

    @patch("server.yf.Ticker")
    async def test_returns_chain_for_date(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_option_chain("AAPL", expiration_date="2025-03-21")

        assert result["expiration_date"] == "2025-03-21"
        assert result["calls_count"] == 1
        assert result["puts_count"] == 1
        assert result["calls"][0]["strike"] == 150.0

    @patch("server.yf.Ticker")
    async def test_invalid_expiration(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_option_chain("AAPL", expiration_date="2099-01-01")
        assert "error" in result

    @patch("server.yf.Ticker")
    async def test_no_options(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(options=())
        result = await get_option_chain("AAPL")
        assert "message" in result

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_option_chain("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetAnalystEstimates:
    @patch("server.yf.Ticker")
    async def test_returns_estimates(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_analyst_estimates("AMZN")

        assert result["symbol"] == "AMZN"
        assert len(result["earnings_estimate"]) == 2
        assert result["earnings_estimate"][0]["period"] == "Current Quarter"

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_analyst_estimates("AMZN")
        assert "error" in result


@pytest.mark.asyncio
class TestGetAnalystRatings:
    @patch("server.yf.Ticker")
    async def test_returns_ratings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_analyst_ratings("META")

        assert result["symbol"] == "META"
        assert result["price_targets"]["low"] == 200
        assert len(result["upgrades_downgrades"]) == 2
        assert result["upgrades_downgrades"][0]["firm"] == "Morgan Stanley"

    @patch("server.yf.Ticker")
    async def test_no_targets(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(analyst_price_targets=None)
        result = await get_analyst_ratings("META")
        assert result["price_targets"] is None

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_analyst_ratings("META")
        assert "error" in result


@pytest.mark.asyncio
class TestGetInsiderHoldings:
    @patch("server.yf.Ticker")
    async def test_returns_holdings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_insider_holdings("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["insider_transactions"][0]["insider"] == "Tim Cook"
        assert result["institutional_holders"][0]["holder"] == "Vanguard Group"

    @patch("server.yf.Ticker")
    async def test_empty_holdings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(
            major_holders=None,
            insider_transactions=None,
            institutional_holders=None,
            mutualfund_holders=None,
        )
        result = await get_insider_holdings("AAPL")
        assert result["insider_transactions"] == []
        assert result["institutional_holders"] == []

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_insider_holdings("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestBatchDownload:
    @patch("server.yf.download")
    async def test_single_symbol(self, mock_download):
        mock_download.return_value = _make_history_df()
        result = await batch_download(["AAPL"], period="5d", interval="1d")

        assert result["symbols"] == ["AAPL"]
        assert len(result["data"]["AAPL"]) == 3

    @patch("server.yf.download")
    async def test_empty_download(self, mock_download):
        mock_download.return_value = pd.DataFrame()
        result = await batch_download(["INVALID"])
        assert "error" in result

    @patch("server.yf.download")
    async def test_handles_exception(self, mock_download):
        mock_download.side_effect = Exception("fail")
        result = await batch_download(["AAPL"])
        assert "error" in result


@pytest.mark.asyncio
class TestScreenStocks:
    @patch("server.yf.screen")
    @patch("server.yf", create=True)
    async def test_returns_screener_results(self, mock_yf, mock_screen):
        mock_yf.PREDEFINED_SCREENER_QUERIES = {"most_actives": {}}
        mock_screen.return_value = {
            "title": "Most Active",
            "description": "Most actively traded",
            "quotes": [
                {
                    "symbol": "TSLA",
                    "longName": "Tesla, Inc.",
                    "regularMarketPrice": 200.0,
                    "regularMarketChangePercent": 3.5,
                    "regularMarketVolume": 100_000_000,
                    "marketCap": 600_000_000_000,
                    "trailingPE": 50.0,
                }
            ],
        }
        # Need to patch hasattr check and the dict on the yf module
        import server

        original = getattr(server.yf, "PREDEFINED_SCREENER_QUERIES", None)
        server.yf.PREDEFINED_SCREENER_QUERIES = {"most_actives": {}}
        try:
            result = await screen_stocks("most_actives")
            assert result["count"] == 1
            assert result["results"][0]["symbol"] == "TSLA"
        finally:
            if original is None:
                del server.yf.PREDEFINED_SCREENER_QUERIES
            else:
                server.yf.PREDEFINED_SCREENER_QUERIES = original

    async def test_invalid_preset(self):
        result = await screen_stocks("totally_invalid_preset_xyz")
        assert "error" in result


@pytest.mark.asyncio
class TestGetEsgData:
    @patch("server.yf.Ticker")
    async def test_no_esg_data(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(sustainability=None)
        result = await get_esg_data("MSFT")

        assert result["symbol"] == "MSFT"
        assert "message" in result

    @patch("server.yf.Ticker")
    async def test_with_esg_data(self, mock_ticker_cls):
        esg_df = pd.DataFrame({"Value": [25.0, 10.0]}, index=["totalEsg", "envScore"])
        mock_ticker_cls.return_value = _build_ticker_mock(sustainability=esg_df)
        result = await get_esg_data("MSFT")
        assert "esg_scores" in result

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_esg_data("MSFT")
        assert "error" in result


@pytest.mark.asyncio
class TestGetSecFilings:
    @patch("server.yf.Ticker")
    async def test_returns_filings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_sec_filings("AAPL", count=5)

        assert result["symbol"] == "AAPL"
        assert result["count"] == 2
        assert result["filings"][0]["type"] == "10-K"

    @patch("server.yf.Ticker")
    async def test_no_filings(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(sec_filings=[])
        result = await get_sec_filings("AAPL")
        assert result["filings"] == []

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_sec_filings("AAPL")
        assert "error" in result


@pytest.mark.asyncio
class TestGetCalendar:
    @patch("server.yf.Ticker")
    async def test_returns_calendar(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock()
        result = await get_calendar("AAPL")

        assert result["symbol"] == "AAPL"
        assert len(result["earnings_dates"]) == 2
        assert result["ex_dividend_date"] == "2025-02-07"
        assert result["earnings_estimate"]["average"] == 2.35

    @patch("server.yf.Ticker")
    async def test_empty_calendar(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _build_ticker_mock(calendar={})
        result = await get_calendar("AAPL")
        assert "message" in result

    @patch("server.yf.Ticker")
    async def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("fail")
        result = await get_calendar("AAPL")
        assert "error" in result
