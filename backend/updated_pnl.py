import yfinance as yf
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import pandas as pd

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_password@localhost:5432/trading_agent")

def update_profit_loss():
  """
  Connects to the database and updates the profit_loss for past decisions
  by comparing the decision price to the current market price.
  """
  conn = None
  try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
            SELECT id, symbol, decision, price_at_decision FROM decisions 
            WHERE profit_loss IS NULL AND decision IN ('BUY', 'SELL')
        """)
    decisions = cur.fetchall()

    if not decisions:
      print("P&L Updater: No new decisions to update.")
      return

    print(f"P&L Updater: Found {len(decisions)} decisions to process.")
    symbols = list(set([d['symbol'] for d in decisions]))

    # Fetch current market prices for all unique symbols in one batch
    data = yf.download(symbols, period="1d", progress=False)
    if data.empty:
      print("P&L Updater: Could not fetch current market prices from yfinance.")
      return

    # --- FINAL ROBUST PRICE EXTRACTION LOGIC ---
    close_prices = data['Close']
    latest_prices_dict = {}

    # yfinance returns a Series for one stock, and a DataFrame for multiple.
    # This handles both cases correctly.
    if isinstance(close_prices, pd.Series):
      # Handle the single-stock case
      latest_prices_dict[symbols[0]] = close_prices.iloc[-1]
    else:
      # Handle the multi-stock case
      latest_prices_dict = close_prices.iloc[-1].to_dict()

    for dec in decisions:
      try:
        current_price = latest_prices_dict.get(dec['symbol'])
        decision_price = dec.get('price_at_decision')

        if current_price is None or pd.isna(current_price):
          print(f"P&L Updater: Could not find current price for {dec['symbol']}. Skipping.")
          continue

        if decision_price is None:
          print(f"P&L Updater: Decision price is missing for ID {dec['id']}. Skipping.")
          continue

        # NEW: Check for unchanged price, which could indicate a holiday or non-trading day.
        # We use a small tolerance for floating point comparison.
        if abs(float(current_price) - float(decision_price)) < 0.01:
          print(f"P&L Updater: Price for {dec['symbol']} is unchanged. Likely a holiday. Skipping P&L calculation for now.")
          continue

        pnl_percent = ((float(current_price) - float(decision_price)) / float(decision_price)) * 100

        if dec['decision'] == 'SELL':
          pnl_percent *= -1

        cur.execute("UPDATE decisions SET profit_loss = %s WHERE id = %s", (pnl_percent, dec['id']))
        print(f"P&L Updater: Updated P&L for {dec['symbol']} (ID: {dec['id']}) to {pnl_percent:.2f}%")

      except Exception as e:
        print(f"P&L Updater: Error processing decision ID {dec.get('id')} for {dec.get('symbol')}: {e}")

    conn.commit()
    print("P&L Updater: Performance review complete.")

  except Exception as e:
    print(f"P&L Updater: A critical error occurred: {e}")
    if conn:
      conn.rollback()
  finally:
    if conn:
      cur.close()
      conn.close()

if __name__ == "__main__":
  print("P&L Updater: Starting performance review.")
  update_profit_loss()
  print("P&L Updater: Review complete. Sleeping for 12 hours.")

