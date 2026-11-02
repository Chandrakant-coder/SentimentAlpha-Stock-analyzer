import sys
sys.path.insert(0, '.')
import yfinance as yf

# Try common variations
tickers = ["TATAMOTORS.NS", "TATAMOTORS.BO", "TATA-MOTORS.NS", "TATAMTRDVR.NS"]
for ticker in tickers:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        print(f"{ticker}: last_price={getattr(info, 'last_price', 'N/A')} currency={getattr(info, 'currency', 'N/A')}")
    except Exception as e:
        print(f"{ticker}: ERROR {e}")
