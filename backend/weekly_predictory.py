import yfinance as yf
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import date, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json
import re

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INDICES_TO_PREDICT = ["^NSEI", "^BSESN"] # Nifty 50 and Sensex

# --- LLM and Prompt Setup ---
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

prediction_prompt = ChatPromptTemplate.from_template("""
You are an expert market analyst specializing in Indian indices. Your task is to provide a day-by-day closing price prediction for {symbol} for the entire upcoming week ({week_start_date} to {week_end_date}).

Analyze the provided historical data and recent trends to make an informed prediction for each day.

**Historical Data Summary:**
- Current Price: {current_price:,.2f}
- 52-Week High: {year_high:,.2f}
- 52-Week Low: {year_low:,.2f}
- 50-Day Average: {fifty_day_avg:,.2f}
- 200-Day Average: {two_hundred_day_avg:,.2f}

**Your Task:**
1.  **Weekly Reasoning:** Provide a brief, overall reasoning for your weekly forecast.
2.  **Daily Predictions:** Provide a list of predicted closing prices for each day from Monday to Friday. Each price must be a valid JSON number (e.g., 25800.00), not a string and with no commas.

Provide your output as a single, valid JSON object only.

**JSON Output Format:**
{{
    "weekly_reasoning": "...",
    "daily_predictions": [
        {{"day": "Monday", "predicted_price": 0.0}},
        {{"day": "Tuesday", "predicted_price": 0.0}},
        {{"day": "Wednesday", "predicted_price": 0.0}},
        {{"day": "Thursday", "predicted_price": 0.0}},
        {{"day": "Friday", "predicted_price": 0.0}}
    ]
}}
""")

def get_db_connection():
  return psycopg2.connect(DATABASE_URL)

def evaluate_last_week_predictions():
  """Finds last week's predictions and evaluates their day-wise performance."""
  print("Evaluating last week's day-wise predictions...")
  conn = get_db_connection()
  cur = conn.cursor(cursor_factory=RealDictCursor)

  today = date.today()
  last_week_start = today - timedelta(days=today.weekday() + 7)

  cur.execute("SELECT * FROM weekly_index_predictions WHERE week_start_date = %s AND actual_closing_price IS NULL", (last_week_start,))
  predictions_to_evaluate = cur.fetchall()

  if not predictions_to_evaluate:
    print("No predictions from last week to evaluate.")
    conn.close()
    return

  for pred in predictions_to_evaluate:
    try:
      symbol = pred['symbol']
      predicted_days = pred['daily_predictions_json']

      # Fetch the entire week's actual data
      actual_hist = yf.download(symbol, start=pred['week_start_date'], end=pred['week_end_date'] + timedelta(days=1), progress=False)

      performance_lines = []
      total_diff_percent = 0

      if not predicted_days:
        print(f"Skipping evaluation for {symbol} due to missing daily prediction data.")
        continue

      for i, daily_pred in enumerate(predicted_days):
        day_date = pred['week_start_date'] + timedelta(days=i)
        if day_date in actual_hist.index:
          actual_price = actual_hist.loc[day_date]['Close']
          predicted_price = daily_pred['predicted_price']
          diff_percent = ((actual_price - predicted_price) / predicted_price) * 100 if predicted_price > 0 else 0
          performance_lines.append(f"- {daily_pred['day']}: Off by {diff_percent:.2f}%")
          total_diff_percent += diff_percent

      avg_diff = total_diff_percent / len(predicted_days) if predicted_days else 0
      final_actual_price = actual_hist['Close'].iloc[-1]
      summary = f"Avg Daily Error: {avg_diff:.2f}%. " + " ".join(performance_lines)

      cur.execute("""
                UPDATE weekly_index_predictions
                SET actual_closing_price = %s, performance_summary = %s
                WHERE id = %s
            """, (final_actual_price, summary, pred['id']))
      print(f"Evaluated {symbol}: {summary}")
    except Exception as e:
      print(f"Error evaluating {pred.get('symbol', 'N/A')}: {e}")

  conn.commit()
  cur.close()
  conn.close()

def generate_new_weekly_predictions():
  """Generates and saves new day-wise predictions for the upcoming week."""
  print("Generating new day-wise predictions...")
  conn = get_db_connection()
  cur = conn.cursor()

  today = date.today()
  week_start = today + timedelta(days=(7 - today.weekday()) % 7)
  week_end = week_start + timedelta(days=4)

  for symbol in INDICES_TO_PREDICT:
    try:
      cur.execute("SELECT id FROM weekly_index_predictions WHERE symbol = %s AND week_start_date = %s", (symbol, week_start))
      if cur.fetchone():
        print(f"Prediction for {symbol} for week starting {week_start} already exists. Skipping.")
        continue

      stock = yf.Ticker(symbol)
      hist = stock.history(period="1y")
      data_summary = {
        "current_price": hist['Close'].iloc[-1],
        "year_high": hist['High'].max(), "year_low": hist['Low'].min(),
        "fifty_day_avg": hist['Close'][-50:].mean(), "two_hundred_day_avg": hist['Close'][-200:].mean(),
      }

      chain = prediction_prompt | llm | StrOutputParser()
      raw_response = chain.invoke({
        "symbol": symbol, "week_start_date": week_start.strftime("%Y-%m-%d"), "week_end_date": week_end.strftime("%Y-%m-%d"), **data_summary
      })

      json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
      if not json_match: raise ValueError("Could not find valid JSON in LLM response.")
      response = json.loads(json_match.group())

      cur.execute("""
                INSERT INTO weekly_index_predictions
                (symbol, prediction_date, week_start_date, week_end_date, daily_predictions_json, weekly_reasoning)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (symbol, today, week_start, week_end, json.dumps(response['daily_predictions']), response['weekly_reasoning']))
      print(f"Generated new day-wise prediction for {symbol}.")
    except Exception as e:
      print(f"Error generating prediction for {symbol}: {e}")
      conn.rollback()

  conn.commit()
  cur.close()
  conn.close()


if __name__ == "__main__":
  print("--- Starting Weekly Index Prediction Job ---")
  evaluate_last_week_predictions()
  generate_new_weekly_predictions()
  print("--- Weekly Index Prediction Job Finished ---")

