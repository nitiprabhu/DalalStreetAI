# 🇮🇳 AI Trading Agent Dashboard - Indian Stocks

An intelligent trading dashboard focused on Indian stock markets (NSE/BSE) with AI-powered analysis, data caching, and real-time insights.

## Features

### ✅ Current Features
- **Indian Stock Focus**: Optimized for NSE and BSE exchanges
- **AI-Powered Analysis**: GPT-4o-mini powered trading decisions (BUY/SELL/HOLD)
- **Data Caching**: Intelligent caching system to avoid repeated API calls
- **Real-time Charts**: Interactive candlestick charts with technical indicators
- **Technical Analysis**: RSI, MACD, Moving Averages
- **Session Management**: Smart session state handling
- **Popular Stocks**: Quick selection of popular Indian stocks
- **History Tracking**: Complete analysis history with CSV export

### 🔧 Technical Improvements
- **Warning Suppression**: Clean logs without yfinance spam
- **Session State Fix**: Results reset when switching symbols
- **Exchange Support**: NSE (.NS) and BSE (.BO) symbol formatting
- **Cache Management**: 1-hour cache validity with automatic refresh
- **Error Handling**: Robust error handling and user feedback

## Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API Key

### Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd trading-agent-prod-fixed
   cp env.template .env
   ```

2. **Configure Environment**
   Edit `.env` file and add your OpenAI API key:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000

## Usage

### Stock Analysis
1. Select exchange (NSE/BSE)
2. Enter stock symbol (e.g., RELIANCE, TCS, HDFCBANK)
3. Click "🔍 Analyze Now" for AI analysis
4. View real-time charts and technical indicators

### Popular Indian Stocks
- **NSE**: RELIANCE, TCS, HDFCBANK, INFY, HINDUNILVR, ITC, SBIN, BHARTIARTL, KOTAKBANK, LT
- **BSE**: RELIANCE, TCS, HDFCBANK, INFY, HINDUNILVR

### Data Caching
- Stock data is cached for 1 hour to reduce API calls
- Cache status is shown in the UI
- Fresh data is fetched when cache expires

## API Endpoints

### Backend API (FastAPI)
- `GET /analyze/{symbol}?exchange={NSE|BSE}` - Get AI analysis
- `GET /data/{symbol}?exchange={NSE|BSE}` - Get stock data with caching
- `GET /history/{symbol}?exchange={NSE|BSE}` - Get analysis history
- `GET /popular-indian-stocks` - Get popular Indian stocks list

## Architecture

### Backend (FastAPI)
- **Data Source**: yfinance with Indian exchange support
- **AI Engine**: OpenAI GPT-4o-mini via LangChain
- **Database**: PostgreSQL with optimized schema and indexing
- **Caching**: 1-hour TTL for stock data and indicators
- **Connection Pooling**: Efficient database connections

### Frontend (Streamlit)
- **UI Framework**: Streamlit with Plotly charts
- **State Management**: Smart session state handling
- **Charts**: Interactive candlestick, RSI, MACD
- **Responsive**: Wide layout with sidebar controls

### Data Flow
1. User selects symbol and exchange
2. Backend checks cache for existing data
3. If cache miss, fetch from yfinance
4. Calculate technical indicators (RSI, MACD)
5. Run AI analysis with LangChain
6. Cache results and return to frontend
7. Frontend displays analysis and charts

## Configuration

### Environment Variables
```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# PostgreSQL Database Configuration
POSTGRES_DB=trading_agent
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=trading_password
DATABASE_URL=postgresql://trading_user:trading_password@database:5432/trading_agent

# Application Configuration
APP_ENV=production
DEBUG=false
CACHE_TTL_HOURS=1
DEFAULT_EXCHANGE=NSE
DEFAULT_SYMBOL=RELIANCE
```

### Cache Settings
- **TTL**: 1 hour (configurable)
- **Storage**: PostgreSQL database with JSONB columns
- **Scope**: Per symbol and exchange
- **Performance**: Indexed queries for fast retrieval

## Development

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload

# Frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Database Schema
```sql
-- Analysis decisions
CREATE TABLE decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD')),
    reason TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(10) DEFAULT 'NSE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stock data cache
CREATE TABLE stock_data_cache (
    symbol VARCHAR(20) PRIMARY KEY,
    data JSONB NOT NULL,
    indicators JSONB NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(10) DEFAULT 'NSE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_decisions_symbol ON decisions(symbol);
CREATE INDEX idx_decisions_timestamp ON decisions(timestamp);
CREATE INDEX idx_stock_cache_last_updated ON stock_data_cache(last_updated);
```

## Future Enhancements

### Planned Features
- [ ] User authentication system
- [ ] Multi-user support with individual histories
- [ ] Portfolio tracking
- [ ] Alert system
- [ ] Advanced technical indicators
- [ ] News sentiment analysis
- [ ] Mobile-responsive design

### Deployment Options
- [x] PostgreSQL database container
- [ ] Nginx reverse proxy for HTTPS
- [ ] Redis for advanced caching
- [ ] Kubernetes deployment
- [ ] CI/CD pipeline

## Troubleshooting

### Common Issues
1. **No data found**: Check if symbol exists on selected exchange
2. **API errors**: Verify OpenAI API key is valid
3. **Cache issues**: Clear browser cache or restart containers
4. **Docker issues**: Ensure Docker and Docker Compose are running

### Logs
```bash
# View container logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart services
docker-compose restart
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Create an issue with detailed information

---

**Note**: This is a trading analysis tool for educational purposes. Always do your own research before making investment decisions.
