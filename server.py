#!/usr/bin/env python3
"""YFinance MCP Server - Hosted on Azure Functions via custom handler."""

import logging
import os
import sys
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Reduce noisy logging from dependencies
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server (stateless_http is passed to run() for Azure Functions hosting)
mcp = FastMCP("YFinance MCP Server")


class StockInfo(BaseModel):
    """Stock information model"""

    symbol: str
    name: str = ""
    current_price: float = 0.0
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None


class HistoricalDataRequest(BaseModel):
    """Request model for historical data"""

    symbol: str
    period: str = Field(
        default="1mo", description="Period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max"
    )
    interval: str = Field(
        default="1d",
        description="Interval: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo",
    )


@mcp.tool()
async def get_stock_info(symbol: str) -> Dict[str, Any]:
    """
    Get basic stock information including current price, market cap, and key metrics.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing stock information
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        return {
            "symbol": symbol.upper(),
            "name": info.get("longName", ""),
            "current_price": info.get("currentPrice", 0.0),
            "previous_close": info.get("previousClose"),
            "open": info.get("open"),
            "day_high": info.get("dayHigh"),
            "day_low": info.get("dayLow"),
            "market_cap": info.get("marketCap"),
            # P/E Ratios
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            # Valuation Metrics
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_value": info.get("enterpriseValue"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            # Profitability Metrics
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "gross_margins": info.get("grossMargins"),
            "ebitda_margins": info.get("ebitdaMargins"),
            # Earnings & Returns
            "earnings_per_share": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "return_on_assets": info.get("returnOnAssets"),
            "return_on_equity": info.get("returnOnEquity"),
            # Dividend Information
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "ex_dividend_date": info.get("exDividendDate"),
            # Financial Health
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            # Growth Metrics
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_per_share": info.get("revenuePerShare"),
            "book_value": info.get("bookValue"),
            # Trading Metrics
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "52_week_change": info.get("52WeekChange"),
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "avg_volume_10days": info.get("averageVolume10days"),
            "beta": info.get("beta"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "shares_short": info.get("sharesShort"),
            "short_ratio": info.get("shortRatio"),
            "short_percent_of_float": info.get("shortPercentOfFloat"),
            # Analyst Metrics
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "recommendation_mean": info.get("recommendationMean"),
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            # Company Information
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "website": info.get("website"),
            "full_time_employees": info.get("fullTimeEmployees"),
            "business_summary": (
                info.get("businessSummary", "")[:500] + "..."
                if info.get("businessSummary", "")
                else ""
            ),
        }
    except Exception as e:
        logger.error("Error getting stock info for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get stock info for {symbol}"}


@mcp.tool()
async def get_historical_data(
    symbol: str, period: str = "1mo", interval: str = "1d"
) -> Dict[str, Any]:
    """
    Get historical stock price data.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        period: Time period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)

    Returns:
        Dictionary containing historical price data
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return {"error": f"No data found for symbol {symbol}"}

        data = []
        for date, row in hist.iterrows():
            data.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if "Volume" in row else 0,
                }
            )

        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "data": data,
            "count": len(data),
        }
    except Exception as e:
        logger.error("Error getting historical data for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get historical data for {symbol}"}


@mcp.tool()
async def get_dividends(symbol: str) -> Dict[str, Any]:
    """
    Get dividend history for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing dividend history
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        dividends = ticker.dividends

        if dividends.empty:
            return {
                "symbol": symbol.upper(),
                "dividends": [],
                "message": "No dividend data available",
            }

        dividend_data = []
        for date, dividend in dividends.items():
            dividend_data.append(
                {"date": date.strftime("%Y-%m-%d"), "dividend": float(dividend)}
            )

        return {
            "symbol": symbol.upper(),
            "dividends": dividend_data,
            "count": len(dividend_data),
        }
    except Exception as e:
        logger.error("Error getting dividends for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get dividends for {symbol}"}


@mcp.tool()
async def get_splits(symbol: str) -> Dict[str, Any]:
    """
    Get stock split history for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing split history
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        splits = ticker.splits

        if splits.empty:
            return {
                "symbol": symbol.upper(),
                "splits": [],
                "message": "No split data available",
            }

        split_data = []
        for date, split in splits.items():
            split_data.append(
                {"date": date.strftime("%Y-%m-%d"), "split_ratio": float(split)}
            )

        return {
            "symbol": symbol.upper(),
            "splits": split_data,
            "count": len(split_data),
        }
    except Exception as e:
        logger.error("Error getting splits for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get splits for {symbol}"}


@mcp.tool()
async def get_financials(symbol: str, quarterly: bool = False) -> Dict[str, Any]:
    """
    Get financial statements for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        quarterly: If True, get quarterly data; if False, get annual data

    Returns:
        Dictionary containing financial statements
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        if quarterly:
            income_stmt = ticker.quarterly_income_stmt
            balance_sheet = ticker.quarterly_balance_sheet
            cash_flow = ticker.quarterly_cashflow
        else:
            income_stmt = ticker.income_stmt
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow

        result = {
            "symbol": symbol.upper(),
            "quarterly": quarterly,
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {},
        }

        if not income_stmt.empty:
            result["income_statement"] = income_stmt.to_dict()

        if not balance_sheet.empty:
            result["balance_sheet"] = balance_sheet.to_dict()

        if not cash_flow.empty:
            result["cash_flow"] = cash_flow.to_dict()

        return result
    except Exception as e:
        logger.error("Error getting financials for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get financials for {symbol}"}


@mcp.tool()
async def get_earnings(symbol: str) -> Dict[str, Any]:
    """
    Get earnings data for a stock.
    Note: Uses income statement data as 'earnings' property is deprecated.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing earnings data extracted from financial statements
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        annual_income = ticker.income_stmt
        quarterly_income = ticker.quarterly_income_stmt

        result = {
            "symbol": symbol.upper(),
            "annual_earnings": {},
            "quarterly_earnings": {},
            "note": "Earnings data extracted from income statements (Net Income)",
        }

        if annual_income is not None and not annual_income.empty:
            net_income_rows = annual_income[
                annual_income.index.str.contains("Net Income", case=False, na=False)
            ]
            if not net_income_rows.empty:
                net_income_data = net_income_rows.iloc[0].to_dict()
                annual_earnings = {}
                for date, value in net_income_data.items():
                    date_str = (
                        date.strftime("%Y-%m-%d")
                        if hasattr(date, "strftime")
                        else str(date)
                    )
                    annual_earnings[date_str] = (
                        float(value)
                        if value is not None and not pd.isna(value)
                        else None
                    )
                result["annual_earnings"] = annual_earnings

        if quarterly_income is not None and not quarterly_income.empty:
            net_income_rows = quarterly_income[
                quarterly_income.index.str.contains("Net Income", case=False, na=False)
            ]
            if not net_income_rows.empty:
                net_income_data = net_income_rows.iloc[0].to_dict()
                quarterly_earnings = {}
                for date, value in net_income_data.items():
                    date_str = (
                        date.strftime("%Y-%m-%d")
                        if hasattr(date, "strftime")
                        else str(date)
                    )
                    quarterly_earnings[date_str] = (
                        float(value)
                        if value is not None and not pd.isna(value)
                        else None
                    )
                result["quarterly_earnings"] = quarterly_earnings

        return result
    except Exception as e:
        logger.error("Error getting earnings for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get earnings for {symbol}"}


@mcp.tool()
async def get_news(symbol: str, count: int = 10) -> Dict[str, Any]:
    """
    Get recent news for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        count: Number of news articles to return (default: 10)

    Returns:
        Dictionary containing news articles
    """
    try:
        count = max(1, min(count, 100))
        ticker = yf.Ticker(symbol.upper())
        news = ticker.news

        if not news:
            return {
                "symbol": symbol.upper(),
                "news": [],
                "message": "No news available",
            }

        news = news[:count]

        news_data = []
        for article in news:
            content = article.get("content", {})
            thumbnail_url = ""
            if content.get("thumbnail") and content["thumbnail"].get("resolutions"):
                thumbnail_url = content["thumbnail"]["resolutions"][0].get("url", "")

            pub_time = 0
            if content.get("pubDate"):
                try:
                    pub_time = int(
                        datetime.fromisoformat(
                            content["pubDate"].replace("Z", "+00:00")
                        ).timestamp()
                    )
                except (ValueError, KeyError, AttributeError):
                    pub_time = 0

            news_data.append(
                {
                    "title": content.get("title", ""),
                    "link": content.get("canonicalUrl", {}).get("url", ""),
                    "publisher": content.get("provider", {}).get("displayName", ""),
                    "providerPublishTime": pub_time,
                    "type": content.get("contentType", ""),
                    "thumbnail": thumbnail_url,
                    "summary": content.get("summary", ""),
                }
            )

        return {"symbol": symbol.upper(), "news": news_data, "count": len(news_data)}
    except Exception as e:
        logger.error("Error getting news for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get news for {symbol}"}


@mcp.tool()
async def get_recommendations(symbol: str) -> Dict[str, Any]:
    """
    Get analyst recommendations for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing analyst recommendations
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        recommendations = ticker.recommendations

        if recommendations is None or recommendations.empty:
            return {
                "symbol": symbol.upper(),
                "recommendations": [],
                "message": "No recommendations available",
            }

        rec_data = []
        for _, row in recommendations.iterrows():
            period = row.get("period", "")
            total_recommendations = (
                row.get("strongBuy", 0)
                + row.get("buy", 0)
                + row.get("hold", 0)
                + row.get("sell", 0)
                + row.get("strongSell", 0)
            )

            rec_data.append(
                {
                    "period": period,
                    "strong_buy": int(row.get("strongBuy", 0)),
                    "buy": int(row.get("buy", 0)),
                    "hold": int(row.get("hold", 0)),
                    "sell": int(row.get("sell", 0)),
                    "strong_sell": int(row.get("strongSell", 0)),
                    "total": total_recommendations,
                }
            )

        return {
            "symbol": symbol.upper(),
            "recommendations": rec_data,
            "count": len(rec_data),
            "note": "Recommendations show analyst count by rating for different time periods",
        }
    except Exception as e:
        logger.error("Error getting recommendations for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get recommendations for {symbol}"}


@mcp.tool()
async def search_stocks(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search for stocks by company name or ticker symbol.

    This tool searches Yahoo Finance's database for stocks matching your query.
    Works best with specific company names or partial ticker symbols.

    Examples of effective queries:
    - "Microsoft" (company name)
    - "AAPL" (ticker symbol)
    - "Tesla" (company name)
    - "JPM" (partial ticker)

    Note: Complex multi-word queries may return fewer results. For best results,
    search for one company at a time.

    Args:
        query: Search query - company name or ticker symbol (e.g., 'Microsoft', 'AAPL')
        limit: Maximum number of results to return (default: 10, max recommended: 25)

    Returns:
        Dictionary containing search results with symbol, name, type, exchange,
        sector, industry, relevance score, and other metadata
    """
    try:
        limit = max(1, min(limit, 25))
        search_obj = yf.Search(query, max_results=limit)
        search_results = search_obj.quotes

        if not search_results:
            return {"query": query, "results": [], "message": "No results found"}

        results = []
        for result in search_results[:limit]:
            results.append(
                {
                    "symbol": result.get("symbol", ""),
                    "name": result.get("longname", result.get("shortname", "")),
                    "type": result.get("quoteType", ""),
                    "exchange": result.get("exchange", ""),
                    "sector": result.get("sector", ""),
                    "industry": result.get("industry", ""),
                    "score": result.get("score", 0),
                    "is_yahoo_finance": result.get("isYahooFinance", False),
                }
            )

        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error("Error searching stocks for query '%s': %s", query, str(e), exc_info=True)
        return {"error": f"Failed to search stocks for query '{query}'"}


@mcp.tool()
async def get_multiple_quotes(symbols: List[str]) -> Dict[str, Any]:
    """
    Get current quotes for multiple stocks at once.

    Args:
        symbols: List of stock ticker symbols (e.g., ['AAPL', 'GOOGL', 'MSFT'])

    Returns:
        Dictionary containing quotes for all requested symbols
    """
    try:
        symbols = [symbol.upper() for symbol in symbols]
        tickers = yf.Tickers(" ".join(symbols))

        results = {}
        for symbol in symbols:
            try:
                ticker = tickers.tickers[symbol]
                info = ticker.info

                results[symbol] = {
                    "symbol": symbol,
                    "name": info.get("longName", ""),
                    "current_price": info.get("currentPrice", 0.0),
                    "previous_close": info.get("previousClose", 0.0),
                    "change": info.get("currentPrice", 0.0)
                    - info.get("previousClose", 0.0),
                    "change_percent": (
                        ((info.get("currentPrice", 0.0) - (info.get("previousClose") or 0.0))
                         / (info.get("previousClose") or 1.0))
                        * 100
                    ) if info.get("previousClose") else 0.0,
                    "volume": info.get("volume", 0),
                    "market_cap": info.get("marketCap"),
                    # P/E Ratios
                    "trailing_pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "peg_ratio": info.get("pegRatio"),
                    # Key Valuation Metrics
                    "price_to_sales": info.get("priceToSalesTrailing12Months"),
                    "price_to_book": info.get("priceToBook"),
                    "dividend_yield": info.get("dividendYield"),
                    "beta": info.get("beta"),
                    # Profitability
                    "profit_margins": info.get("profitMargins"),
                    "operating_margins": info.get("operatingMargins"),
                    # Analyst Data
                    "target_mean_price": info.get("targetMeanPrice"),
                    "recommendation_key": info.get("recommendationKey"),
                }
            except Exception as e:
                results[symbol] = {
                    "error": f"Failed to get data for {symbol}"
                }

        return {"symbols": symbols, "quotes": results, "count": len(symbols)}
    except Exception as e:
        logger.error("Error getting multiple quotes: %s", str(e), exc_info=True)
        return {"error": "Failed to get multiple quotes"}


@mcp.tool()
async def get_option_chain(
    symbol: str, expiration_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get options chain data for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        expiration_date: Option expiration date in YYYY-MM-DD format.
                        If not provided, returns available expiration dates.

    Returns:
        Dictionary containing available expirations, or calls/puts data
        with strike, bid, ask, volume, open interest, and implied volatility
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        expirations = ticker.options

        if not expirations:
            return {
                "symbol": symbol.upper(),
                "message": "No options data available",
            }

        if expiration_date is None:
            return {
                "symbol": symbol.upper(),
                "expirations": list(expirations),
                "count": len(expirations),
            }

        if expiration_date not in expirations:
            return {
                "error": f"Invalid expiration date. Available: {list(expirations[:10])}",
            }

        chain = ticker.option_chain(expiration_date)

        def format_options(df):
            records = []
            for _, row in df.iterrows():
                records.append({
                    "contract_symbol": row.get("contractSymbol", ""),
                    "strike": float(row.get("strike", 0)),
                    "last_price": float(row.get("lastPrice", 0)),
                    "bid": float(row.get("bid", 0)),
                    "ask": float(row.get("ask", 0)),
                    "volume": int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
                    "open_interest": int(row.get("openInterest", 0)) if pd.notna(row.get("openInterest")) else 0,
                    "implied_volatility": float(row.get("impliedVolatility", 0)),
                    "in_the_money": bool(row.get("inTheMoney", False)),
                })
            return records

        return {
            "symbol": symbol.upper(),
            "expiration_date": expiration_date,
            "calls": format_options(chain.calls),
            "puts": format_options(chain.puts),
            "calls_count": len(chain.calls),
            "puts_count": len(chain.puts),
        }
    except Exception as e:
        logger.error("Error getting option chain for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get option chain for {symbol}"}


@mcp.tool()
async def get_analyst_estimates(symbol: str) -> Dict[str, Any]:
    """
    Get analyst estimates including EPS forecasts, revenue estimates, and growth projections.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing earnings estimates, revenue estimates,
        EPS trends, EPS revisions, and growth estimates
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        result = {"symbol": symbol.upper()}

        def df_to_records(df):
            if df is None or df.empty:
                return []
            records = []
            for idx, row in df.iterrows():
                record = {"period": str(idx)}
                for col in df.columns:
                    val = row[col]
                    record[col] = float(val) if pd.notna(val) and isinstance(val, (int, float)) else str(val) if pd.notna(val) else None
                records.append(record)
            return records

        result["earnings_estimate"] = df_to_records(ticker.earnings_estimate)
        result["revenue_estimate"] = df_to_records(ticker.revenue_estimate)
        result["eps_trend"] = df_to_records(ticker.eps_trend)
        result["eps_revisions"] = df_to_records(ticker.eps_revisions)
        result["growth_estimates"] = df_to_records(ticker.growth_estimates)

        return result
    except Exception as e:
        logger.error("Error getting analyst estimates for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get analyst estimates for {symbol}"}


@mcp.tool()
async def get_analyst_ratings(symbol: str) -> Dict[str, Any]:
    """
    Get analyst price targets and upgrade/downgrade history.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing current price targets (low/mean/median/high)
        and recent analyst rating changes with firm names
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        result = {"symbol": symbol.upper()}

        price_targets = ticker.analyst_price_targets
        if price_targets:
            result["price_targets"] = {
                "current": price_targets.get("current"),
                "low": price_targets.get("low"),
                "mean": price_targets.get("mean"),
                "median": price_targets.get("median"),
                "high": price_targets.get("high"),
            }
        else:
            result["price_targets"] = None

        upgrades_downgrades = ticker.upgrades_downgrades
        if upgrades_downgrades is not None and not upgrades_downgrades.empty:
            ratings = []
            for idx, row in upgrades_downgrades.head(20).iterrows():
                ratings.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "firm": row.get("Firm", ""),
                    "to_grade": row.get("ToGrade", ""),
                    "from_grade": row.get("FromGrade", ""),
                    "action": row.get("Action", ""),
                })
            result["upgrades_downgrades"] = ratings
            result["ratings_count"] = len(upgrades_downgrades)
        else:
            result["upgrades_downgrades"] = []

        return result
    except Exception as e:
        logger.error("Error getting analyst ratings for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get analyst ratings for {symbol}"}


@mcp.tool()
async def get_insider_holdings(symbol: str) -> Dict[str, Any]:
    """
    Get insider and institutional ownership data for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing major holders breakdown, insider transactions,
        institutional holders, and mutual fund holders
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        result = {"symbol": symbol.upper()}

        # Major holders breakdown
        major = ticker.major_holders
        if major is not None and not major.empty:
            result["major_holders"] = major.to_dict().get("Value", {})
        else:
            result["major_holders"] = {}

        # Insider transactions (recent)
        insider_tx = ticker.insider_transactions
        if insider_tx is not None and not insider_tx.empty:
            txns = []
            for _, row in insider_tx.head(20).iterrows():
                txns.append({
                    "insider": row.get("Insider", ""),
                    "position": row.get("Position", ""),
                    "transaction": row.get("Transaction", ""),
                    "date": row.get("Start Date").strftime("%Y-%m-%d") if hasattr(row.get("Start Date"), "strftime") else str(row.get("Start Date", "")),
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0,
                    "value": float(row.get("Value", 0)) if pd.notna(row.get("Value")) else 0,
                })
            result["insider_transactions"] = txns
        else:
            result["insider_transactions"] = []

        # Institutional holders (top 10)
        inst = ticker.institutional_holders
        if inst is not None and not inst.empty:
            holders = []
            for _, row in inst.iterrows():
                holders.append({
                    "holder": row.get("Holder", ""),
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0,
                    "pct_held": float(row.get("pctHeld", 0)) if pd.notna(row.get("pctHeld")) else 0,
                    "value": float(row.get("Value", 0)) if pd.notna(row.get("Value")) else 0,
                })
            result["institutional_holders"] = holders
        else:
            result["institutional_holders"] = []

        # Mutual fund holders (top 10)
        mf = ticker.mutualfund_holders
        if mf is not None and not mf.empty:
            funds = []
            for _, row in mf.iterrows():
                funds.append({
                    "holder": row.get("Holder", ""),
                    "shares": int(row.get("Shares", 0)) if pd.notna(row.get("Shares")) else 0,
                    "pct_held": float(row.get("pctHeld", 0)) if pd.notna(row.get("pctHeld")) else 0,
                    "value": float(row.get("Value", 0)) if pd.notna(row.get("Value")) else 0,
                })
            result["mutualfund_holders"] = funds
        else:
            result["mutualfund_holders"] = []

        return result
    except Exception as e:
        logger.error("Error getting insider holdings for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get insider holdings for {symbol}"}


@mcp.tool()
async def batch_download(
    symbols: List[str],
    period: str = "1mo",
    interval: str = "1d",
) -> Dict[str, Any]:
    """
    Download historical price data for multiple stocks efficiently in one call.

    Args:
        symbols: List of stock ticker symbols (e.g., ['AAPL', 'GOOGL', 'MSFT'])
        period: Time period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)
        interval: Data interval (1d,5d,1wk,1mo,3mo)

    Returns:
        Dictionary containing OHLCV data keyed by ticker symbol
    """
    try:
        symbols = [s.upper() for s in symbols]
        data = yf.download(symbols, period=period, interval=interval, progress=False)

        if data.empty:
            return {"error": "No data returned for the given symbols"}

        result = {"symbols": symbols, "period": period, "interval": interval, "data": {}}

        for symbol in symbols:
            try:
                if len(symbols) == 1:
                    sym_data = data
                else:
                    sym_data = data.xs(symbol, level="Ticker", axis=1) if "Ticker" in str(data.columns.names) else data

                records = []
                for date, row in sym_data.iterrows():
                    records.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "open": float(row["Open"]) if pd.notna(row.get("Open")) else None,
                        "high": float(row["High"]) if pd.notna(row.get("High")) else None,
                        "low": float(row["Low"]) if pd.notna(row.get("Low")) else None,
                        "close": float(row["Close"]) if pd.notna(row.get("Close")) else None,
                        "volume": int(row["Volume"]) if pd.notna(row.get("Volume")) else 0,
                    })
                result["data"][symbol] = records
            except Exception:
                result["data"][symbol] = []

        return result
    except Exception as e:
        logger.error("Error in batch download: %s", str(e), exc_info=True)
        return {"error": "Failed to download batch data"}


@mcp.tool()
async def screen_stocks(preset: str) -> Dict[str, Any]:
    """
    Screen stocks using predefined Yahoo Finance screener queries.

    Args:
        preset: Screener preset name. Available presets:
                aggressive_small_caps, day_gainers, day_losers,
                growth_technology_stocks, most_actives, most_shorted_stocks,
                small_cap_gainers, undervalued_growth_stocks,
                undervalued_large_caps, conservative_foreign_funds,
                high_yield_bond

    Returns:
        Dictionary containing screener results with stock symbols and key metrics
    """
    try:
        valid_presets = list(yf.PREDEFINED_SCREENER_QUERIES.keys()) if hasattr(yf, "PREDEFINED_SCREENER_QUERIES") else []

        if preset not in valid_presets:
            return {
                "error": f"Invalid preset. Available: {valid_presets}",
            }

        screen_result = yf.screen(preset)

        if not screen_result or "quotes" not in screen_result:
            return {"preset": preset, "results": [], "message": "No results found"}

        results = []
        for quote in screen_result["quotes"][:25]:
            results.append({
                "symbol": quote.get("symbol", ""),
                "name": quote.get("longName", quote.get("shortName", "")),
                "price": quote.get("regularMarketPrice"),
                "change_percent": quote.get("regularMarketChangePercent"),
                "volume": quote.get("regularMarketVolume"),
                "market_cap": quote.get("marketCap"),
                "pe_ratio": quote.get("trailingPE") or quote.get("forwardPE"),
            })

        return {
            "preset": preset,
            "title": screen_result.get("title", ""),
            "description": screen_result.get("description", ""),
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error("Error screening stocks with preset '%s': %s", preset, str(e), exc_info=True)
        return {"error": f"Failed to screen stocks with preset '{preset}'"}


@mcp.tool()
async def get_esg_data(symbol: str) -> Dict[str, Any]:
    """
    Get ESG (Environmental, Social, Governance) sustainability scores for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing ESG risk scores and ratings
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        sustainability = ticker.sustainability

        if sustainability is None or sustainability.empty:
            return {
                "symbol": symbol.upper(),
                "message": "No ESG data available",
            }

        esg_data = {}
        for idx, row in sustainability.iterrows():
            for col in sustainability.columns:
                val = row[col]
                esg_data[str(idx)] = float(val) if pd.notna(val) and isinstance(val, (int, float)) else str(val) if pd.notna(val) else None

        return {"symbol": symbol.upper(), "esg_scores": esg_data}
    except Exception as e:
        logger.error("Error getting ESG data for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get ESG data for {symbol}"}


@mcp.tool()
async def get_sec_filings(symbol: str, count: int = 20) -> Dict[str, Any]:
    """
    Get SEC filings for a stock (10-K, 10-Q, 8-K, etc.).

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
        count: Number of filings to return (default: 20)

    Returns:
        Dictionary containing list of SEC filings with type, date, and links
    """
    try:
        count = max(1, min(count, 50))
        ticker = yf.Ticker(symbol.upper())
        filings = ticker.sec_filings

        if not filings:
            return {
                "symbol": symbol.upper(),
                "filings": [],
                "message": "No SEC filings available",
            }

        filing_data = []
        for filing in filings[:count]:
            filing_data.append({
                "type": filing.get("type", ""),
                "date": filing.get("date", ""),
                "title": filing.get("title", ""),
                "edgar_url": filing.get("edgarUrl", ""),
            })

        return {
            "symbol": symbol.upper(),
            "filings": filing_data,
            "count": len(filing_data),
        }
    except Exception as e:
        logger.error("Error getting SEC filings for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get SEC filings for {symbol}"}


@mcp.tool()
async def get_calendar(symbol: str) -> Dict[str, Any]:
    """
    Get upcoming corporate events calendar for a stock.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Dictionary containing upcoming earnings dates, ex-dividend date,
        dividend date, and earnings/revenue estimates
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        calendar = ticker.calendar

        if not calendar:
            return {
                "symbol": symbol.upper(),
                "message": "No calendar data available",
            }

        def format_date(d):
            if hasattr(d, "strftime"):
                return d.strftime("%Y-%m-%d")
            return str(d) if d else None

        result = {"symbol": symbol.upper()}

        earnings_dates = calendar.get("Earnings Date", [])
        result["earnings_dates"] = [format_date(d) for d in earnings_dates] if isinstance(earnings_dates, list) else [format_date(earnings_dates)]
        result["ex_dividend_date"] = format_date(calendar.get("Ex-Dividend Date"))
        result["dividend_date"] = format_date(calendar.get("Dividend Date"))
        result["earnings_estimate"] = {
            "average": calendar.get("Earnings Average"),
            "low": calendar.get("Earnings Low"),
            "high": calendar.get("Earnings High"),
        }
        result["revenue_estimate"] = {
            "average": calendar.get("Revenue Average"),
            "low": calendar.get("Revenue Low"),
            "high": calendar.get("Revenue High"),
        }

        return result
    except Exception as e:
        logger.error("Error getting calendar for %s: %s", symbol, str(e), exc_info=True)
        return {"error": f"Failed to get calendar for {symbol}"}


if __name__ == "__main__":
    try:
        # Azure Functions sets FUNCTIONS_CUSTOMHANDLER_PORT; fall back to 8000
        port = int(os.environ.get("FUNCTIONS_CUSTOMHANDLER_PORT", "8000"))
        print(f"Starting YFinance MCP server on port {port}...")
        mcp.run(transport="streamable-http", stateless_http=True, port=port)
    except Exception as e:
        print(f"Error while running MCP server: {e}", file=sys.stderr)
