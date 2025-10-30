import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime
import os

# -------------------------------------------------
# ==== CONFIG ====
st.set_page_config(page_title="Alpaca Multi-Ticker Dashboard", layout="wide")

API_KEY = st.secrets["API_KEY"]
API_SECRET = st.secrets["API_SECRET"]
BASE_URL = "https://paper-api.alpaca.markets/v2"
CSV_FILE = "orderbook_history.csv"

# -------------------------------------------------
# Initialise CSV
if not os.path.isfile(CSV_FILE):
    pd.DataFrame(columns=["timestamp", "symbol", "type", "price", "quantity"]).to_csv(CSV_FILE, index=False)

# -------------------------------------------------
# Helper: fetch data
@st.cache_data(ttl=5)
def fetch_level2(symbol):
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET
    }

    # ---- Level-2 (paid) ----
    url = f"{BASE_URL}/v2/stocks/{symbol}/book?level=2"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        if "snapshot" in data:
            snap = data["snapshot"]
            bids = [[float(p), int(q)] for p, q in zip(snap.get("bp", []), snap.get("bs", []))]
            asks = [[float(p), int(q)] for p, q in zip(snap.get("ap", []), snap.get("as", []))]
            return bids[:5], asks[:5]

    # ---- Fallback to best quote (free) ----
    url = f"{BASE_URL}/v2/stocks/{symbol}/quote"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        q = r.json()["quote"]
        return [[float(q["bp"]), int(q["bs"])]], [[float(q["ap"]), int(q["as"])]]

    return [], []

# -------------------------------------------------
# Save to CSV (now with symbol)
def save_to_csv(symbol, bids, asks):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for p, q in bids:
        rows.append([ts, symbol, "bid", p, q])
    for p, q in asks:
        rows.append([ts, symbol, "ask", p, q])
    if rows:
        df = pd.DataFrame(rows, columns=["timestamp", "symbol", "type", "price", "quantity"])
        df.to_csv(CSV_FILE, mode="a", header=False, index=False)

# -------------------------------------------------
# Plot
def plot_book(bids, asks, symbol):
    fig, ax = plt.subplots(figsize=(7, 4))
    if bids:
        bp = [p for p, _ in bids]
        bq = [q for _, q in bids]
        ax.bar(bp, bq, width=0.015, color="#2ca02c", label="Bids")
    if asks:
        ap = [p for p, _ in asks]
        aq = [q for _, q in asks]
        ax.bar(ap, aq, width=0.015, color="#d62728", label="Asks")

    ax.set_xlabel("Price ($)")
    ax.set_ylabel("Qty")
    ax.set_title(f"{symbol}")
    ax.legend(fontsize=9)
    plt.tight_layout()
    return fig

# -------------------------------------------------
# UI
st.title("Alpaca Multi-Ticker Level-2 Dashboard")
st.caption("Paper trading – real-time (auto-refresh 5 s)")

# Input: multiple tickers
ticker_input = st.text_input("Tickers (comma-separated)", value="AAPL, MSFT, TSLA")
SYMBOLS = [s.strip().upper() for s in ticker_input.split(",") if s.strip()]

if not SYMBOLS:
    st.warning("Enter at least one ticker.")
    st.stop()

# Auto-refresh
refresh = st.button("Refresh Now")
placeholder = st.empty()

# -------------------------------------------------
# Main display
with placeholder.container():
    cols = st.columns(len(SYMBOLS))  # One column per ticker

    for idx, symbol in enumerate(SYMBOLS):
        with cols[idx]:
            st.subheader(f"**{symbol}**")
            bids, asks = fetch_level2(symbol)

            if bids or asks:
                save_to_csv(symbol, bids, asks)

                # Tables
                bid_df = pd.DataFrame(bids, columns=["Price", "Qty"])
                ask_df = pd.DataFrame(asks, columns=["Price", "Qty"])
                bid_df["Price"] = bid_df["Price"].map("${:,.2f}".format)
                ask_df["Price"] = ask_df["Price"].map("${:,.2f}".format)

                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Bids**")
                    st.dataframe(bid_df.style.applymap(lambda x: "color: green", subset=["Price"]), use_container_width=True)
                with c2:
                    st.write("**Asks**")
                    st.dataframe(ask_df.style.applymap(lambda x: "color: red", subset=["Price"]), use_container_width=True)

                spread = asks[0][0] - bids[0][0] if bids and asks else 0
                st.success(f"**Spread:** ${spread:.2f}")

                # Chart
                st.pyplot(plot_book(bids, asks, symbol))

            else:
                st.error("No data")

# -------------------------------------------------
# CSV download (all tickers)
if os.path.isfile(CSV_FILE):
    with open(CSV_FILE, "rb") as f:
        st.download_button(
            label="Download Full CSV History (All Tickers)",
            data=f,
            file_name="multi_ticker_orderbook.csv",
            mime="text/csv"
        )

# Auto-refresh
time.sleep(5)
st.rerun()
