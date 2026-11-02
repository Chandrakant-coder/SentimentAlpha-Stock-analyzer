import re
from typing import List, Dict, Any, Tuple
from app.core.logging import logger

# Curated Nifty 50 reference universe with symbols, official names, aliases, and sectors
DEFAULT_NIFTY_STOCKS = [
    {
        "symbol": "RELIANCE",
        "ticker": "RELIANCE.NS",
        "company_name": "Reliance Industries Limited",
        "sector": "Energy & Petrochemicals",
        "aliases": ["Reliance", "RIL", "Jio", "Reliance Retail"],
    },
    {
        "symbol": "TCS",
        "ticker": "TCS.NS",
        "company_name": "Tata Consultancy Services",
        "sector": "Information Technology",
        "aliases": ["Tata Consultancy Services", "Tata Consultancy", "TCS"],
    },
    {
        "symbol": "HDFCBANK",
        "ticker": "HDFCBANK.NS",
        "company_name": "HDFC Bank Limited",
        "sector": "Banking & Financials",
        "aliases": ["HDFC Bank", "HDFC", "HDFCBank"],
    },
    {
        "symbol": "INFY",
        "ticker": "INFY.NS",
        "company_name": "Infosys Limited",
        "sector": "Information Technology",
        "aliases": ["Infosys", "Infy"],
    },
    {
        "symbol": "ICICIBANK",
        "ticker": "ICICIBANK.NS",
        "company_name": "ICICI Bank Limited",
        "sector": "Banking & Financials",
        "aliases": ["ICICI Bank", "ICICI"],
    },
    {
        "symbol": "BHARTIARTL",
        "ticker": "BHARTIARTL.NS",
        "company_name": "Bharti Airtel Limited",
        "sector": "Telecommunications",
        "aliases": ["Bharti Airtel", "Airtel"],
    },
    {
        "symbol": "SBIN",
        "ticker": "SBIN.NS",
        "company_name": "State Bank of India",
        "sector": "Banking & Financials",
        "aliases": ["State Bank of India", "SBI", "State Bank"],
    },
    {
        "symbol": "ITC",
        "ticker": "ITC.NS",
        "company_name": "ITC Limited",
        "sector": "Fast Moving Consumer Goods",
        "aliases": ["ITC Limited", "ITC Ltd", "ITC"],
    },
    {
        "symbol": "LT",
        "ticker": "LT.NS",
        "company_name": "Larsen & Toubro Limited",
        "sector": "Engineering & Construction",
        "aliases": ["Larsen & Toubro", "L&T", "Larsen and Toubro"],
    },
    {
        "symbol": "KOTAKBANK",
        "ticker": "KOTAKBANK.NS",
        "company_name": "Kotak Mahindra Bank",
        "sector": "Banking & Financials",
        "aliases": ["Kotak Mahindra Bank", "Kotak Bank", "Kotak"],
    },
    {
        "symbol": "HINDUNILVR",
        "ticker": "HINDUNILVR.NS",
        "company_name": "Hindustan Unilever Limited",
        "sector": "Fast Moving Consumer Goods",
        "aliases": ["Hindustan Unilever", "HUL"],
    },
    {
        "symbol": "TATAMOTORS",
        "ticker": "TATAMOTORS.NS",
        "company_name": "Tata Motors Limited",
        "sector": "Automobile",
        "aliases": ["Tata Motors", "TaMo", "JLR"],
    },
    {
        "symbol": "BAJFINANCE",
        "ticker": "BAJFINANCE.NS",
        "company_name": "Bajaj Finance Limited",
        "sector": "Banking & Financials",
        "aliases": ["Bajaj Finance", "Bajaj Finserv"],
    },
    {
        "symbol": "MARUTI",
        "ticker": "MARUTI.NS",
        "company_name": "Maruti Suzuki India Limited",
        "sector": "Automobile",
        "aliases": ["Maruti Suzuki", "Maruti"],
    },
    {
        "symbol": "SUNPHARMA",
        "ticker": "SUNPHARMA.NS",
        "company_name": "Sun Pharmaceutical Industries",
        "sector": "Pharmaceuticals",
        "aliases": ["Sun Pharma", "Sun Pharmaceuticals"],
    },
    {
        "symbol": "TITAN",
        "ticker": "TITAN.NS",
        "company_name": "Titan Company Limited",
        "sector": "Consumer Durables",
        "aliases": ["Titan Company", "Titan", "Tanishq"],
    },
    {
        "symbol": "WIPRO",
        "ticker": "WIPRO.NS",
        "company_name": "Wipro Limited",
        "sector": "Information Technology",
        "aliases": ["Wipro"],
    },
    {
        "symbol": "ADANIENT",
        "ticker": "ADANIENT.NS",
        "company_name": "Adani Enterprises Limited",
        "sector": "Metals & Mining",
        "aliases": ["Adani Enterprises", "Adani Group", "Adani"],
    },
    {
        "symbol": "NTPC",
        "ticker": "NTPC.NS",
        "company_name": "NTPC Limited",
        "sector": "Power & Energy",
        "aliases": ["NTPC Limited", "NTPC"],
    },
    {
        "symbol": "POWERGRID",
        "ticker": "POWERGRID.NS",
        "company_name": "Power Grid Corporation of India",
        "sector": "Power & Energy",
        "aliases": ["Power Grid", "PowerGrid", "PGCIL"],
    },
]

class StockEntityMapper:
    """
    Deterministic stock and company entity mapper.
    Matches text against symbols, company names, and aliases with regex boundary protection.
    """

    def __init__(self, stock_list: List[Dict[str, Any]] = None):
        self.stocks = stock_list or DEFAULT_NIFTY_STOCKS
        self._compiled_patterns: List[Tuple[Dict[str, Any], re.Pattern, float, str]] = []
        self._build_patterns()

    def _build_patterns(self):
        """Compile regex patterns for rapid matching with confidence levels"""
        self._compiled_patterns = []
        for stock in self.stocks:
            # 1. Exact ticker symbol: \bRELIANCE\b (High confidence: 1.0)
            sym = stock["symbol"]
            sym_pattern = re.compile(rf"\b{re.escape(sym)}\b", re.IGNORECASE)
            self._compiled_patterns.append((stock, sym_pattern, 1.0, sym))

            # 2. Full company name (High confidence: 1.0)
            name = stock["company_name"]
            name_pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
            self._compiled_patterns.append((stock, name_pattern, 1.0, name))

            # 3. Aliases
            for alias in stock.get("aliases", []):
                # Short uppercase aliases like "SBI", "ITC", "L&T" require strict uppercase or word boundary
                if len(alias) <= 3 and alias.isupper():
                    p = re.compile(rf"\b{re.escape(alias)}\b")  # Case sensitive for short acronyms
                    conf = 0.95
                else:
                    p = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                    conf = 0.90
                self._compiled_patterns.append((stock, p, conf, alias))

    def map_text_to_stocks(self, text: str) -> List[Dict[str, Any]]:
        """
        Scans article title and body for known stocks.
        Returns a list of matched stock dicts with symbol, matched_term, and confidence.
        """
        if not text:
            return []

        matched_stocks: Dict[str, Dict[str, Any]] = {}

        for stock, pattern, conf, term in self._compiled_patterns:
            sym = stock["symbol"]
            if sym in matched_stocks and matched_stocks[sym]["confidence"] >= conf:
                continue

            match = pattern.search(text)
            if match:
                matched_stocks[sym] = {
                    "symbol": sym,
                    "ticker": stock["ticker"],
                    "company_name": stock["company_name"],
                    "sector": stock.get("sector"),
                    "matched_term": match.group(0),
                    "confidence": conf,
                }

        return list(matched_stocks.values())

stock_mapper = StockEntityMapper()
