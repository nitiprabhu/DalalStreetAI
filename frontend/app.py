import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from datetime import date
import os

# --- Configuration & Helper Functions ---
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(page_title="AI Trading Agent | DalalStreetAI", layout="wide")

@st.cache_data(ttl=600)
def get_current_prices(symbols):
    """
    A robust function to fetch current prices for a list of stock symbols,
    handling both single and multiple symbol cases correctly and gracefully
    managing missing data.
    """
    if not symbols:
        return {}

    data = yf.download(symbols, period="2d", progress=False)
    if data.empty:
        return {s: {"price": 0, "change": 0, "change_percent": 0} for s in symbols}

    prices = {}
    close_prices = data['Close']

    for symbol in symbols:
        hist = close_prices[symbol] if isinstance(close_prices, pd.DataFrame) else close_prices

        if isinstance(hist, pd.Series) and len(hist) > 1 and not pd.isna(hist.iloc[-1]):
            price = hist.iloc[-1]
            prev_price = hist.iloc[-2]

            if not pd.isna(prev_price) and prev_price != 0:
                change = price - prev_price
                change_percent = (change / prev_price) * 100
                prices[symbol] = {"price": price, "change": change, "change_percent": change_percent}
            else:
                prices[symbol] = {"price": price, "change": 0, "change_percent": 0}
        else:
            prices[symbol] = {"price": 0, "change": 0, "change_percent": 0}

    return prices

# --- Session State & Login Persistence ---
if "user" not in st.session_state: st.session_state.user = None
if "latest_result" not in st.session_state: st.session_state.latest_result = None

if st.session_state.user is None:
    try:
        username_in_query = st.query_params.get("user")
        if username_in_query:
            res = requests.post(f"{BACKEND}/users/create", params={"username": username_in_query})
            if res.ok: st.session_state.user = res.json()
    except Exception: pass

# --- Sidebar ---
with st.sidebar:
    st.header("🔑 Login / Register")
    if st.session_state.user:
        st.success(f"Logged in as **{st.session_state.user['username']}**")
        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.latest_result = None
            st.query_params.clear()
            st.rerun()
    else:
        username = st.text_input("Username", placeholder="Enter username")
        if st.button("Login"):
            if username.strip():
                res = requests.post(f"{BACKEND}/users/create", params={"username": username.strip()})
                st.session_state.user = res.json()
                st.query_params["user"] = username.strip()
                st.rerun()

    if st.session_state.user:
        st.divider()
        app_mode = st.radio("Choose a Page", ("My Dashboard", "My Portfolio", "Master Recommendations", "Agent Performance"))

# --- Main App ---
if not st.session_state.user:
    st.title("Welcome to DalalStreetAI")
    st.info("Please log in using the sidebar to continue.")
else:
    if app_mode == "My Dashboard":
        st.title("😀 My Trading Dashboard")

        indices = requests.get(f"{BACKEND}/indices/summary").json()
        if indices:
            cols = st.columns(len(indices))
            for i, index in enumerate(indices):
                with cols[i]:
                    delta = f"{index['change']:,.2f} ({index['change_percent']:.2f}%)"
                    st.metric(label=index['name'], value=f"{index['price']:,.2f}", delta=delta)
                    if st.button(f"Analyze {index['name']}", key=f"analyze_{index.get('symbol', index['name'])}"):
                        with st.spinner(f"🤖 AI agent is analyzing {index['name']}..."):
                            res = requests.get(f"{BACKEND}/analyze/{st.session_state.user['id']}/{index['symbol']}", params={"exchange": "INDEX"})
                            st.session_state.latest_result = res.json()
                            st.session_state.analyzed_item = index['symbol']
        st.divider()

        st.subheader("🗓️ AI Weekly Market Forecast")
        try:
            forecast_data = requests.get(f"{BACKEND}/indices/weekly-forecast").json()
            fc_cols = st.columns(2)
            with fc_cols[0]:
                st.markdown("<h5>Forecast for Next Week</h5>", unsafe_allow_html=True)
                if forecast_data.get("forecasts"):
                    for forecast in forecast_data["forecasts"]:
                        st.info(f"**{forecast['symbol']} Reasoning:** {forecast['weekly_reasoning']}")
                        if forecast.get('daily_predictions_json'):
                            df_preds = pd.DataFrame(forecast['daily_predictions_json'])
                            st.dataframe(df_preds.set_index('day'))
                else: st.write("New weekly forecast is being generated.")
            with fc_cols[1]:
                st.markdown("<h5>Last Week's Performance</h5>", unsafe_allow_html=True)
                if forecast_data.get("evaluations"):
                    for evaluation in forecast_data["evaluations"]:
                        st.warning(f"**{evaluation['symbol']} Review for {evaluation['week_end_date']}:**\n- {evaluation['performance_summary']}")
                else: st.write("No performance evaluation available yet.")
        except Exception as e: st.error(f"Could not load weekly forecast data: {e}")
        st.divider()

        with st.sidebar:
            st.subheader("📌 My Watchlist")
            wl = requests.get(f"{BACKEND}/watchlist/{st.session_state.user['id']}").json()
            watchlist = wl if isinstance(wl, list) else []
            if watchlist:
                selected_str = st.selectbox("Select stock", [f"{s['symbol']} ({s['exchange']})" for s in watchlist])
                symbol, exchange = selected_str.split(" ")[0], selected_str.split("(")[1][:-1]
                if st.button("🗑️ Remove From Watchlist"):
                    requests.delete(f"{BACKEND}/watchlist/remove", params={"user_id": st.session_state.user["id"], "symbol": symbol, "exchange": exchange})
                    st.rerun()

                # This button is now separate from the display logic
                if st.button("Analyze Selected Stock", key="analyze_watchlist_stock"):
                    with st.spinner(f"🤖 AI agent is analyzing {symbol}..."):
                        res = requests.get(f"{BACKEND}/analyze/{st.session_state.user['id']}/{symbol}", params={"exchange": exchange})
                        st.session_state.latest_result = res.json()
                        st.session_state.analyzed_item = symbol

            else:
                st.write("Your watchlist is empty.")

            with st.form("add_stock_form", clear_on_submit=True):
                new_symbol = st.text_input("Add Stock or Index (e.g. INFY, ^NSEI)")
                new_exchange = st.selectbox("Exchange", ["NSE", "BSE"])
                if st.form_submit_button("➕ Add to Watchlist"):
                    requests.post(f"{BACKEND}/watchlist/add", params={"user_id": st.session_state.user["id"], "symbol": new_symbol, "exchange": new_exchange})
                    st.rerun()

        # --- DEDICATED CONTAINER FOR ANALYSIS RESULTS ---
        st.subheader("📊 Deep-Dive Analysis")
        analysis_container = st.container(border=True)

        if st.session_state.latest_result:
            with analysis_container:
                res = st.session_state.latest_result
                analyzed_item = st.session_state.get("analyzed_item", "item")
                st.markdown(f"#### Analysis for **{analyzed_item}**")

                if "error" in res:
                    st.error(res["error"])
                elif "analysis" in res:
                    analysis = res["analysis"]
                    is_cached = res.get("cached", False)
                    decision, confidence = analysis.get('decision', 'N/A'), analysis.get('confidence', 'N/A')
                    color = {"BUY": "darkgreen", "SELL": "darkred", "HOLD": "orange"}.get(decision)

                    st.markdown(f"### <span style='color:{color};'>Decision: {decision}</span> (Confidence: {confidence})", unsafe_allow_html=True)
                    st.caption(f"Price at decision: ₹{analysis.get('price_at_decision', 0):,.2f} | Source: {'Database Cache' if is_cached else 'Live AI Analysis'}")

                    with st.expander("📝 Final Summary & Risks"): st.write(analysis.get('final_summary', 'N/A'))
                    with st.expander("📈 Technical Summary"): st.write(analysis.get('technical_summary', 'N/A'))
                    with st.expander("🏢 Fundamental Summary"): st.write(analysis.get('fundamental_summary', 'N/A'))
                    with st.expander("📰 Sentiment Summary"): st.write(analysis.get('sentiment_summary', 'N/A'))
        else:
            with analysis_container:
                st.info("Click an 'Analyze' button to see the AI's deep-dive analysis here.")

    elif app_mode == "My Portfolio":
        st.title("💼 My Paper Trading Portfolio")
        with st.expander("📈 Add a New Holding"):
            with st.form("portfolio_form", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns(4)
                p_symbol = c1.text_input("Symbol")
                p_exchange = c2.selectbox("Exchange", ["NSE", "BSE"])
                p_quantity = c3.number_input("Quantity", min_value=0.01, format="%.2f")
                p_price = c4.number_input("Purchase Price", min_value=0.01, format="%.2f")
                if st.form_submit_button("Add to Portfolio"):
                    requests.post(f"{BACKEND}/portfolio/add", params={"user_id": st.session_state.user['id'], "symbol": p_symbol, "exchange": p_exchange, "quantity": p_quantity, "purchase_price": p_price})
                    st.success(f"Added {p_quantity} shares of {p_symbol}.")

        holdings = requests.get(f"{BACKEND}/portfolio/{st.session_state.user['id']}").json()
        if not holdings: st.info("Your portfolio is empty.")
        else:
            st.session_state.original_holdings = holdings
            df = pd.DataFrame(holdings)
            price_data = get_current_prices(df['symbol'].unique().tolist())

            df['current_price'] = df['symbol'].apply(lambda x: price_data.get(x, {}).get('price', 0))
            df['market_value'] = df['current_price'] * df['quantity']
            df['pnl'] = (df['current_price'] - df['purchase_price']) * df['quantity']
            df['pnl_%'] = (df['pnl'] / (df['purchase_price'] * df['quantity'])).fillna(0) * 100

            total_investment = (df['purchase_price'] * df['quantity']).sum()
            total_market_value, total_pnl = df['market_value'].sum(), df['pnl'].sum()
            total_pnl_percent = (total_pnl / total_investment) * 100 if total_investment > 0 else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Portfolio Value", f"₹{total_market_value:,.2f}")
            c2.metric("Total P&L", f"₹{total_pnl:,.2f}", f"{total_pnl_percent:.2f}%")

            st.subheader("Your Holdings")
            edited_df = st.data_editor(df, hide_index=True, num_rows="dynamic", key="portfolio_editor", disabled=['id', 'symbol', 'exchange', 'purchase_date', 'current_price', 'market_value', 'pnl', 'pnl_%'])
            if st.button("Save Portfolio Changes"):
                original_ids, edited_ids = {h['id'] for h in st.session_state.original_holdings}, set(edited_df['id'])
                ids_to_delete = original_ids - edited_ids
                deleted_count = 0
                for holding_id in ids_to_delete:
                    if requests.delete(f"{BACKEND}/portfolio/remove/{holding_id}").status_code == 200: deleted_count += 1
                if deleted_count > 0: st.success(f"Successfully removed {deleted_count} holding(s)."), st.rerun()
                else: st.info("No changes to save.")

    elif app_mode == "Master Recommendations":
        st.title("🏆 Master AI Recommendations")
        st.info("Latest unique BUY/SELL signals from the AI in the last 3 days.")
        recs = requests.get(f"{BACKEND}/recommendations/latest").json()
        if recs:
            df = pd.DataFrame(recs).set_index('id')
            st.dataframe(df[['timestamp', 'symbol', 'decision', 'confidence', 'price_at_decision', 'final_summary']])
        else: st.write("No recent recommendations found.")

    elif app_mode == "Agent Performance":
        st.title("🤖 AI Agent Performance Dashboard")
        st.info("This dashboard shows the historical performance of the AI's BUY/SELL recommendations.")
        try:
            summary = requests.get(f"{BACKEND}/performance/summary").json()
            if not summary or summary.get('total_trades', 0) == 0:
                st.warning("No performance data available yet.")
            else:
                st.subheader("Key Performance Metrics")
                col1, col2, col3 = st.columns(3)
                col1.metric("Win Rate", f"{summary.get('win_rate_percent', 0)}%")
                col2.metric("Average P&L per Trade", f"{summary.get('average_pnl_percent', 0)}%")
                col3.metric("Total Scored Trades", summary.get('total_trades', 0))
                st.subheader("Top Performers")
                col1, col2 = st.columns(2)
                with col1:
                    st.success("✅ Best Trade")
                    if summary.get('best_trade'): st.json(summary['best_trade'])
                with col2:
                    st.error("❌ Worst Trade")
                    if summary.get('worst_trade'): st.json(summary['worst_trade'])
        except Exception as e: st.error(f"Could not load performance data: {e}")

