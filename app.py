import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime
import os
from io import StringIO

# -------------------------------------------------
# ==== CONFIG ====
st.set_page_config(page_title="Alpaca Level-2 Dashboard", layout="wide")

API_KEY = st.secrets.get("API_KEY", "PKDBTDSKFSWGVXJIVTU3XTA5BQ")
API_SECRET = st.secrets.get("API_SECRET", "GjU5hVpfkrnHkthZj7tVpccpxHDYF5soeygQsXh8j3oa")
BASE_URL = "https://paper-api.alpaca.markets"   # keep /v2 in the functions
CSV_FILE = "orderbook_history.csv"

# -------------------------------------------------
# Initialise CSV
if not os.path.isfile(CSV_FILE):
    pd.DataFrame(columns=["timestamp", "type", "price", "quantity"]).to_csv(CSV_FILE, index=False)

# -------------------------------------------------
# Helper: fetch data
@st.cache_data(ttl=5)   # refresh cache every 5 s
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

    st.error(f"API error {r.status_code}: {r.text}")
    return [], []


# -------------------------------------------------
# Save to CSV
def save_to_csv(bids, asks):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for p, q in bids:
        rows.append([ts, "bid", p, q])
    for p, q in asks:
        rows.append([ts, "ask", p, q])
    df = pd.DataFrame(rows, columns=["timestamp", "type", "price", "quantity"])
    df.to_csv(CSV_FILE, mode="a", header=False, index=False)


# -------------------------------------------------
# Plot
def plot_book(bids, asks):
    fig, ax = plt.subplots(figsize=(8, 4))
    if bids:
        bp = [p for p, _ in bids]
        bq = [q for _, q in bids]
        ax.bar(bp, bq, width=0.02, color="#2ca02c", label="Bids")
    if asks:
        ap = [p for p, _ in asks]
        aq = [q for _, q in asks]
        ax.bar(ap, aq, width=0.02, color="#d62728", label="Asks")

    ax.set_xlabel("Price ($)")
    ax.set_ylabel("Quantity")
    ax.set_title(f"{SYMBOL} Order Book – {time.strftime('%H:%M:%S')}")
    ax.legend()
    plt.tight_layout()
    return fig


# -------------------------------------------------
# UI
st.title("Alpaca Level-2 Order Book Dashboard")
st.caption("Paper trading – real-time data (auto-refresh 5 s)")

col1, col2 = st.columns([1, 2])

with col1:
    SYMBOL = st.text_input("Ticker", value="AAPL").upper()
    refresh = st.button("Refresh Now")

with col2:
    placeholder = st.empty()   # for live data

# -------------------------------------------------
# Main loop (Streamlit re-runs on interaction)
if st.session_state.get("last_symbol") != SYMBOL:
    st.session_state.pop("last_symbol", None)

bids, asks = fetch_level2(SYMBOL)

if bids or asks:
    # ---- Save ----
    save_to_csv(bids, asks)

    # ---- Tables ----
    bid_df = pd.DataFrame(bids, columns=["Price", "Qty"])
    ask_df = pd.DataFrame(asks, columns=["Price", "Qty"])
    bid_df["Price"] = bid_df["Price"].map("${:,.2f}".format)
    ask_df["Price"] = ask_df["Price"].map("${:,.2f}".format)

    with placeholder.container():
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Bids (Buyers)")
            st.dataframe(bid_df.style.applymap(lambda x: "color: green", subset=["Price"]))
        with c2:
            st.subheader("Asks (Sellers)")
            st.dataframe(ask_df.style.applymap(lambda x: "color: red", subset=["Price"]))

        spread = asks[0][0] - bids[0][0] if bids and asks else 0
        st.success(f"**Spread:** ${spread:.2f} | Updated: {time.strftime('%H:%M:%S')}")

        # ---- Chart ----
        st.pyplot(plot_book(bids, asks))

else:
    st.warning("No data – check ticker, internet, or market hours.")

# -------------------------------------------------
# CSV download
if os.path.isfile(CSV_FILE):
    with open(CSV_FILE, "rb") as f:
        st.download_button(
            label="Download CSV History",
            data=f,
            file_name=f"{SYMBOL}_orderbook_history.csv",
            mime="text/csv"
        )

# Auto-refresh every 5 s
time.sleep(5)
st.rerun()