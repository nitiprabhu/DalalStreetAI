import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import date
# Make sure to import the function from your main app file
from app import run_full_analysis

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def run_proactive_analysis():
    """
    Finds all unique stocks in user watchlists and ensures they have a
    fresh analysis for the current day.
    """
    print("Agent starting its daily run...")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get all unique stocks from all user watchlists
    cur.execute("SELECT DISTINCT symbol, exchange FROM watchlist;")
    unique_stocks = cur.fetchall()
    print(f"Found {len(unique_stocks)} unique stocks to check.")

    for stock in unique_stocks:
        symbol = stock['symbol']
        exchange = stock['exchange']

        # Check if an analysis for this stock already exists for today
        cur.execute("""
            SELECT id FROM decisions
            WHERE symbol = %s AND DATE(timestamp) = CURRENT_DATE
        """, (symbol,))

        if cur.fetchone():
            print(f"'{symbol}' already has an analysis for today. Skipping.")
            continue

        print(f"'{symbol}' needs a new analysis. Running...")

        # --- THE FIX IS HERE ---
        # We call run_full_analysis without the user_id, as it's not needed for the analysis itself.
        analysis_result = run_full_analysis(symbol=symbol, exchange=exchange)

        if "error" in analysis_result:
            print(f"ERROR: Could not analyze '{symbol}'. Reason: {analysis_result['error']}")
            continue

        # Save the new analysis to the database
        try:
            cur.execute("""
                INSERT INTO decisions (symbol, exchange, price_at_decision, decision, confidence,
                                       technical_summary, fundamental_summary, sentiment_summary, final_summary)
                VALUES (%(symbol)s, %(exchange)s, %(price_at_decision)s, %(decision)s, %(confidence)s,
                        %(technical_summary)s, %(fundamental_summary)s, %(sentiment_summary)s, %(final_summary)s)
            """, {
                'symbol': symbol, 'exchange': exchange, **analysis_result
            })
            conn.commit()
            print(f"Successfully saved new analysis for '{symbol}'.")
        except Exception as e:
            print(f"DATABASE ERROR for '{symbol}': {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("Agent has completed its daily run.")


if __name__ == "__main__":
    run_proactive_analysis()

