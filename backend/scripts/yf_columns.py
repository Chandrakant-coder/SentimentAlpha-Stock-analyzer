import sys
sys.path.insert(0, '.')
import yfinance as yf
import pandas as pd

# Test yf.download column structure
print("=== yf.download RELIANCE.NS ===")
df = yf.download("RELIANCE.NS", period="3d", interval="1d", auto_adjust=False,
                 actions=False, progress=False, threads=False)
print("Type of columns:", type(df.columns))
print("Columns:", list(df.columns))
print("Index:", df.index[:3])
print(df.tail(3))

print("\n=== yf.Ticker RELIANCE.NS history() auto_adjust=False ===")
t = yf.Ticker("RELIANCE.NS")
h = t.history(period="3d", interval="1d", auto_adjust=False)
print("Type of columns:", type(h.columns))
print("Columns:", list(h.columns))
print(h.tail(3))

print("\n=== yf.Ticker RELIANCE.NS history() auto_adjust=True ===")
h2 = t.history(period="3d", interval="1d", auto_adjust=True)
print("Columns:", list(h2.columns))
print(h2.tail(3))
