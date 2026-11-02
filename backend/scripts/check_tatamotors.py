"""Check what ticker works for Tata Motors on yfinance."""
import sys
sys.path.insert(0, '.')
import yfinance as yf

for ticker in ["TATAMOTORS.NS", "TATAMOTORS.BO", "TTM"]:
    print(f"\n--- {ticker} ---")
    try:
        t = yf.Ticker(ticker)
        h = t.history(period="3d", interval="1d", auto_adjust=False)
        if h.empty:
            print("  EMPTY")
        else:
            print(f"  OK: {len(h)} rows, latest close={float(h['Close'].iloc[-1]):.2f} date={h.index[-1]}")
    except Exception as e:
        print(f"  ERROR: {e}")
