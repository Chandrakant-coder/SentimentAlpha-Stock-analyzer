"""
Probe yfinance to see exactly what it returns for RELIANCE.NS and MARUTI.NS today.
Run with: conda run -n GenAI python scripts/yf_probe.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime
import yfinance as yf
import pandas as pd

tickers = ["RELIANCE.NS", "MARUTI.NS", "TCS.NS", "HDFCBANK.NS"]

for ticker in tickers:
    print(f"\n{'='*60}")
    print(f"Ticker: {ticker}")
    print(f"{'='*60}")

    # --- auto_adjust=False (what the app uses after fix) ---
    df_raw = yf.download(
        ticker,
        period="5d",
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )
    print(f"\nauto_adjust=False  (unadjusted OHLC + Adj Close):")
    print(df_raw.tail(5).to_string())

    # --- auto_adjust=True (what Yahoo Finance website shows) ---
    df_adj = yf.download(
        ticker,
        period="5d",
        interval="1d",
        auto_adjust=True,
        actions=False,
        progress=False,
        threads=False,
    )
    print(f"\nauto_adjust=True (adjusted, what Yahoo website Close column shows):")
    print(df_adj.tail(5).to_string())

    # Latest available date
    if not df_raw.empty:
        last_date = df_raw.index[-1]
        print(f"\nLatest available date from yfinance: {last_date.date()}")
        if not df_raw.empty and "Close" in df_raw.columns:
            # Handle MultiIndex
            try:
                close_val = float(df_raw["Close"].iloc[-1])
            except Exception:
                close_val = float(df_raw["Close"][ticker].iloc[-1])
            print(f"Latest unadjusted Close: {close_val:.2f}")
        if not df_adj.empty and "Close" in df_adj.columns:
            try:
                adj_close_val = float(df_adj["Close"].iloc[-1])
            except Exception:
                adj_close_val = float(df_adj["Close"][ticker].iloc[-1])
            print(f"Latest adjusted Close  : {adj_close_val:.2f}")

print(f"\n\nProbe complete at {datetime.datetime.now().isoformat()}")
print(f"Current UTC time: {datetime.datetime.utcnow().isoformat()}")
