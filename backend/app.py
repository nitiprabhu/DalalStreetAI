import yfinance as yf
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import pandas as pd
import ta
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from datetime import date, datetime, timedelta
import json
import re
from fastapi import FastAPI, Query

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_password@localhost:5432/trading_agent")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_INDICES = [
    {"symbol": "^NSEI", "name": "Nifty 50"},
    {"symbol": "^BSESN", "name": "Sensex"}
]

# --- LLM and Prompt Setup ---
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
master_prompt = ChatPromptTemplate.from_template("""
You are an expert financial analyst for the Indian stock market. Your goal is to provide a clear, evidence-based recommendation by following a structured reasoning process.

**Item for Analysis: {symbol} ({exchange})**

**1. Quantitative Data:**
- Close Price: ₹{close_price:,.2f}
- RSI: {rsi}
- MACD Difference: {macd_diff}
- P/E Ratio: {pe_ratio} (Note: 'N/A' for indices)

**2. News & Sentiment:**
- Recent News Sentiment Score (from -1.0 to +1.0): {sentiment_score}

**3. Past Performance Feedback (Your own track record for this item):**
- {past_performance}

**Your Task: Analyze the data and provide your output as a valid JSON object only. Do not include any other text or markdown formatting.**
Follow these steps precisely:
1.  **Technical Summary:** Analyze the technical indicators. Is momentum bullish, bearish, or neutral?
2.  **Fundamental Summary:** Analyze the P/E ratio. If analyzing an index, state that this is not applicable.
3.  **Sentiment Summary:** Interpret the news sentiment. Is the market buzz positive, negative, or neutral?
4.  **Synthesis & Final Summary:** Combine all points. Acknowledge conflicting signals. State primary risks.
5.  **Final Decision:** Provide a final decision ('BUY', 'SELL', or 'HOLD') and a confidence level ('High', 'Medium', 'Low').

**JSON Output Format:**
{{
    "decision": "...",
    "confidence": "...",
    "technical_summary": "...",
    "fundamental_summary": "...",
    "sentiment_summary": "...",
    "final_summary": "..."
}}
""")

# --- Helper Functions ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def format_indian_symbol(symbol: str, exchange: str = "NSE") -> str:
    if symbol.startswith('^'): return symbol
    if not any(symbol.upper().endswith(suffix) for suffix in [".NS", ".BO"]):
        return f"{symbol.upper()}{'.NS' if exchange.upper() == 'NSE' else '.BO'}"
    return symbol.upper()

# --- Core Analysis Function ---
def run_full_analysis(symbol: str, exchange: str) -> dict:
    try:
        is_index = symbol.startswith('^')
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo", interval="1d")
        if hist.empty: return {"error": "Could not fetch historical data."}

        technicals = {
            "RSI": round(ta.momentum.RSIIndicator(hist["Close"]).rsi().iloc[-1], 2),
            "MACD_diff": round(ta.trend.MACD(hist["Close"]).macd_diff().iloc[-1], 2),
            "Close": float(round(hist["Close"].iloc[-1], 2))
        }

        pe_ratio = 'N/A' if is_index else round(stock.info.get('trailingPE', 0), 2)
        sentiment = {"score": -0.1}

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT decision, profit_loss FROM decisions WHERE symbol = %s AND profit_loss IS NOT NULL ORDER BY timestamp DESC LIMIT 3", (symbol,))
        past_decisions = cur.fetchall()

        if not past_decisions:
            past_performance_summary = "No past performance data available for this item."
        else:
            avg_pnl = sum(d['profit_loss'] for d in past_decisions if d['profit_loss'] is not None) / len(past_decisions)
            recent_calls = ", ".join([d['decision'] for d in past_decisions])
            past_performance_summary = f"Your last {len(past_decisions)} recommendations were [{recent_calls}]. Average P&L: {avg_pnl:.2f}%."
        cur.close()
        conn.close()

        parser = JsonOutputParser()
        chain = master_prompt | llm | parser

        response_dict = chain.invoke({
            "symbol": symbol, "exchange": exchange, "close_price": technicals['Close'],
            "rsi": technicals['RSI'], "macd_diff": technicals['MACD_diff'],
            "pe_ratio": pe_ratio, "sentiment_score": sentiment['score'],
            "past_performance": past_performance_summary
        })

        analysis_json = response_dict
        analysis_json['price_at_decision'] = technicals['Close']
        return analysis_json

    except Exception as e:
        return {"error": f"Error in full analysis for {symbol}: {e}"}

# --- FastAPI App and Endpoints ---
app = FastAPI()

@app.get("/health")
def health_check(): return {"status": "ok"}

@app.get("/indices/summary")
def get_indices_summary():
    try:
        tickers = " ".join([index['symbol'] for index in DEFAULT_INDICES])
        data = yf.download(tickers, period="2d", progress=False)

        results = []
        for index in DEFAULT_INDICES:
            hist = data[('Close', index['symbol'])] if isinstance(data.columns, pd.MultiIndex) else data['Close']
            if len(hist) > 1:
                price = hist.iloc[-1]
                change = price - hist.iloc[-2]
                change_percent = (change / hist.iloc[-2]) * 100 if hist.iloc[-2] != 0 else 0
                results.append({
                    "name": index['name'], "symbol": index['symbol'],
                    "price": round(price, 2), "change": round(change, 2),
                    "change_percent": round(change_percent, 2)
                })
        return results
    except Exception:
        return []

@app.post("/users/create")
def create_or_login_user(username: str = Query(...)):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, username FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            if not user:
                cur.execute("INSERT INTO users (username) VALUES (%s) RETURNING id, username", (username,))
                user = cur.fetchone()
                conn.commit()
            return user
    finally:
        conn.close()

@app.get("/analyze/{user_id}/{symbol}")
def analyze_stock(user_id: int, symbol: str, exchange: str = "NSE"):
    formatted_symbol = format_indian_symbol(symbol, exchange)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM decisions WHERE symbol = %s AND DATE(timestamp) = CURRENT_DATE ORDER BY timestamp DESC LIMIT 1", (formatted_symbol,))
    existing_analysis = cur.fetchone()

    if existing_analysis:
        analysis_data = {key: existing_analysis.get(key) for key in ['decision', 'confidence', 'technical_summary', 'fundamental_summary', 'sentiment_summary', 'final_summary', 'price_at_decision']}
        cur.close()
        conn.close()
        return {"cached": True, "analysis": analysis_data}

    analysis_result = run_full_analysis(formatted_symbol, exchange)

    if "error" in analysis_result:
        cur.close()
        conn.close()
        return {"error": analysis_result["error"]}

    cur.execute("""
        INSERT INTO decisions (symbol, exchange, price_at_decision, decision, confidence, technical_summary, fundamental_summary, sentiment_summary, final_summary)
        VALUES (%(symbol)s, %(exchange)s, %(price_at_decision)s, %(decision)s, %(confidence)s, %(technical_summary)s, %(fundamental_summary)s, %(sentiment_summary)s, %(final_summary)s)
        RETURNING *
    """, {'symbol': formatted_symbol, 'exchange': exchange, **analysis_result})
    new_decision = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {"cached": False, "analysis": new_decision}

@app.post("/watchlist/add")
def add_to_watchlist(user_id: int, symbol: str, exchange: str = "NSE"):
    formatted = format_indian_symbol(symbol, exchange)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("INSERT INTO watchlist (user_id, symbol, exchange) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (user_id, formatted, exchange))
            conn.commit()
            cur.execute("SELECT symbol, exchange FROM watchlist WHERE user_id=%s", (user_id,))
            return {"watchlist": cur.fetchall()}
    finally:
        conn.close()

@app.get("/watchlist/{user_id}")
def get_watchlist(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT symbol, exchange FROM watchlist WHERE user_id=%s", (user_id,))
            return cur.fetchall()
    finally:
        conn.close()

@app.delete("/watchlist/remove")
def remove_from_watchlist(user_id: int, symbol: str, exchange: str = "NSE"):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM watchlist WHERE user_id=%s AND symbol=%s AND exchange=%s", (user_id, symbol, exchange))
            conn.commit()
            return {"status": "success", "message": f"{symbol} removed."}
    finally:
        conn.close()

@app.get("/recommendations/latest")
def get_latest_recommendations():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT ON (symbol) * FROM decisions WHERE decision IN ('BUY', 'SELL') AND timestamp > NOW() - INTERVAL '72 hours' ORDER BY symbol, timestamp DESC")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/performance/summary")
def get_performance_summary():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total_trades FROM decisions WHERE profit_loss IS NOT NULL AND decision IN ('BUY', 'SELL')")
            total_trades = cur.fetchone()['total_trades']
            if total_trades == 0: return {"win_rate_percent": 0, "average_pnl_percent": 0, "total_trades": 0, "best_trade": None, "worst_trade": None}
            cur.execute("SELECT COUNT(*) as profitable_trades FROM decisions WHERE profit_loss > 0 AND decision IN ('BUY', 'SELL')")
            profitable_trades = cur.fetchone()['profitable_trades']
            win_rate = (profitable_trades / total_trades) * 100
            cur.execute("SELECT AVG(profit_loss) as avg_pnl FROM decisions WHERE profit_loss IS NOT NULL AND decision IN ('BUY', 'SELL')")
            avg_pnl = cur.fetchone()['avg_pnl'] or 0
            cur.execute("SELECT symbol, decision, profit_loss, timestamp FROM decisions WHERE profit_loss IS NOT NULL ORDER BY profit_loss DESC LIMIT 1")
            best_trade = cur.fetchone()
            cur.execute("SELECT symbol, decision, profit_loss, timestamp FROM decisions WHERE profit_loss IS NOT NULL ORDER BY profit_loss ASC LIMIT 1")
            worst_trade = cur.fetchone()
            return {"win_rate_percent": round(win_rate, 2), "average_pnl_percent": round(avg_pnl, 2), "total_trades": total_trades, "best_trade": best_trade, "worst_trade": worst_trade}
    finally:
        conn.close()

@app.post("/portfolio/add")
def add_holding(user_id: int, symbol: str, exchange: str, quantity: float, purchase_price: float, purchase_date: date = None):
    formatted = format_indian_symbol(symbol, exchange)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO portfolio_holdings (user_id, symbol, exchange, quantity, purchase_price, purchase_date) VALUES (%s, %s, %s, %s, %s, %s)",
                        (user_id, formatted, exchange, quantity, purchase_price, purchase_date or date.today()))
            conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

@app.get("/portfolio/{user_id}")
def get_portfolio(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolio_holdings WHERE user_id=%s ORDER BY symbol", (user_id,))
            return cur.fetchall()
    finally:
        conn.close()

@app.delete("/portfolio/remove/{holding_id}")
def remove_holding(holding_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM portfolio_holdings WHERE id = %s", (holding_id,))
            conn.commit()
            if cur.rowcount == 0: return {"status": "error", "message": "Holding not found."}
            return {"status": "success", "message": f"Holding {holding_id} removed."}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

@app.get("/indices/weekly-forecast")
def get_weekly_forecast():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT symbol, week_end_date, daily_predictions_json, weekly_reasoning FROM weekly_index_predictions WHERE week_start_date >= CURRENT_DATE - INTERVAL '3 days' ORDER BY prediction_date DESC, symbol")
        forecasts = cur.fetchall()
        cur.execute("SELECT symbol, week_end_date, performance_summary FROM weekly_index_predictions WHERE actual_closing_price IS NOT NULL ORDER BY week_end_date DESC, symbol LIMIT 2")
        evaluations = cur.fetchall()
        return {"forecasts": forecasts, "evaluations": evaluations}
    finally:
        cur.close()
        conn.close()

