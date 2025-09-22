-- AI Trading Agent Database Schema
-- PostgreSQL initialization script

-- Create tables for trading decisions and data caching
CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD')),
    reason TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(10) DEFAULT 'NSE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create table for stock data caching
CREATE TABLE IF NOT EXISTS stock_data_cache (
    symbol VARCHAR(20) PRIMARY KEY,
    data JSONB NOT NULL,
    indicators JSONB NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(10) DEFAULT 'NSE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_exchange ON decisions(exchange);
CREATE INDEX IF NOT EXISTS idx_stock_cache_last_updated ON stock_data_cache(last_updated);
CREATE INDEX IF NOT EXISTS idx_stock_cache_exchange ON stock_data_cache(exchange);

-- Create a function to clean old cache entries (older than 24 hours)
CREATE OR REPLACE FUNCTION clean_old_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM stock_data_cache 
    WHERE last_updated < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- Create a function to clean old decisions (older than 30 days)
CREATE OR REPLACE FUNCTION clean_old_decisions()
RETURNS void AS $$
BEGIN
    DELETE FROM decisions 
    WHERE timestamp < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Insert some sample data for testing
INSERT INTO decisions (symbol, decision, reason, exchange) VALUES 
('RELIANCE.NS', 'BUY', 'Strong fundamentals and positive market sentiment', 'NSE'),
('TCS.NS', 'HOLD', 'Stable performance with moderate growth prospects', 'NSE'),
('HDFCBANK.NS', 'BUY', 'Excellent financial health and growth potential', 'NSE')
ON CONFLICT DO NOTHING;

-- Create a view for recent decisions
CREATE OR REPLACE VIEW recent_decisions AS
SELECT 
    symbol,
    decision,
    reason,
    timestamp,
    exchange,
    CASE 
        WHEN decision = 'BUY' THEN '🟢'
        WHEN decision = 'SELL' THEN '🔴'
        ELSE '🟡'
    END as decision_emoji
FROM decisions 
ORDER BY timestamp DESC;

-- Grant permissions (if needed for future user authentication)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO trading_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO trading_user;

COMMENT ON TABLE decisions IS 'Stores AI trading decisions and analysis results';
COMMENT ON TABLE stock_data_cache IS 'Caches stock market data and technical indicators';
COMMENT ON VIEW recent_decisions IS 'View of recent trading decisions with emoji indicators';


CREATE TABLE IF NOT EXISTS weekly_reviews (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    week_start DATE,
    week_end DATE,
    total_pnl FLOAT,
    review TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);


-- Users (very simple auth, can be expanded later)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL
);

-- Watchlist: which user watches which stock
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT,
    exchange TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, symbol, exchange)
);

-- User decisions (extends global decisions with user-level link)
CREATE TABLE IF NOT EXISTS user_decisions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    decision_id INT REFERENCES decisions(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_trades (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    status VARCHAR(10) CHECK (status IN ('OPEN', 'CLOSED')),
    entry_timestamp TIMESTAMP NOT NULL,
    entry_price FLOAT NOT NULL,
    exit_timestamp TIMESTAMP,
    exit_price FLOAT,
    pnl FLOAT -- Calculated upon closing the trade
);

ALTER TABLE decisions ADD COLUMN price_at_decision FLOAT;

-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL
);

-- Create Watchlist Table
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    UNIQUE(user_id, symbol, exchange)
);

-- Create Decisions Table
-- CORRECTED: Added the 'price_at_decision' column and consolidated timestamp columns.
CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    exchange TEXT NOT NULL,
    price_at_decision FLOAT,
    profit_loss FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Create a linking table for user-specific decisions
CREATE TABLE IF NOT EXISTS user_decisions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    decision_id INT REFERENCES decisions(id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_decisions_symbol_exchange ON decisions(symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);


-- Renames the 'reason' column to be more descriptive.
ALTER TABLE decisions RENAME COLUMN reason TO final_summary;

-- Adds new columns to store the detailed, structured analysis from the agent.
ALTER TABLE decisions ADD COLUMN technical_summary TEXT;
ALTER TABLE decisions ADD COLUMN fundamental_summary TEXT;
ALTER TABLE decisions ADD COLUMN sentiment_summary TEXT;
ALTER TABLE decisions ADD COLUMN confidence TEXT;

-- Adds a column to the users table for personalization in the future.
ALTER TABLE users ADD COLUMN risk_profile VARCHAR(50) DEFAULT 'Moderate';

-- Add an index for faster lookups by date.
CREATE INDEX IF NOT EXISTS idx_decisions_symbol_date ON decisions(symbol, (timestamp::date));


-- This table stores the AI's weekly predictions for major indices.
CREATE TABLE IF NOT EXISTS weekly_index_predictions (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL, -- e.g., '^NSEI' for Nifty 50
    prediction_date DATE NOT NULL, -- The date the prediction was made (e.g., the Saturday)
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    predicted_price FLOAT NOT NULL,
    prediction_reasoning TEXT,
    actual_closing_price FLOAT, -- To be filled in at the end of the week
    performance_summary TEXT, -- e.g., "Prediction was off by -1.2%"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add an index for faster lookups
CREATE INDEX IF NOT EXISTS idx_weekly_predictions_symbol_date ON weekly_index_predictions(symbol, prediction_date);

-- Drop the old single price column
ALTER TABLE weekly_index_predictions DROP COLUMN IF EXISTS predicted_price;

-- Rename the old reasoning column for clarity
ALTER TABLE weekly_index_predictions RENAME COLUMN IF EXISTS prediction_reasoning TO weekly_reasoning;

-- Add a new JSONB column to store the detailed day-wise forecast
ALTER TABLE weekly_index_predictions ADD COLUMN IF NOT EXISTS daily_predictions_json JSONB;




