import sys, datetime
sys.path.insert(0, '.')
import yfinance as yf
import pandas as pd

print("yfinance version:", yf.__version__)
print("Probe time:", datetime.datetime.now())

for ticker in ["RELIANCE.NS", "MARUTI.NS"]:
    print(f"\n--- {ticker} ---")
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d", auto_adjust=False)
        print("auto_adjust=False:")
        print(hist[["Open","High","Low","Close","Volume"]].tail(5))
        hist2 = t.history(period="5d", interval="1d", auto_adjust=True)
        print("auto_adjust=True:")
        print(hist2[["Open","High","Low","Close","Volume"]].tail(5))
    except Exception as e:
        print("ERROR:", e)
