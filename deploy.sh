#!/bin/bash

# AI Trading Agent Dashboard - Deployment Script
echo "🇮🇳 AI Trading Agent Dashboard - Indian Stocks"
echo "=============================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp env.template .env
    echo "📝 Please edit .env file and add your OpenAI API key:"
    echo "   OPENAI_API_KEY=your_openai_api_key_here"
    echo ""
    echo "Press Enter when ready to continue..."
    read
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

echo "🚀 Starting AI Trading Agent Dashboard with PostgreSQL..."
echo ""

# Build and start services
echo "📦 Building and starting containers..."
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Access your dashboard:"
echo "   Frontend: http://localhost:8501"
echo "   Backend API: http://localhost:8000"
echo "   Database: localhost:5432 (PostgreSQL)"
echo ""
echo "📋 Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   View specific service logs: docker-compose logs -f [service_name]"
echo "   Stop services: docker-compose down"
echo "   Restart: docker-compose restart"
echo "   Database shell: docker-compose exec database psql -U trading_user -d trading_agent"
echo ""
echo "🗄️  Database Information:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Database: trading_agent"
echo "   Username: trading_user"
echo "   Password: trading_password"
echo ""
echo "🎯 Try analyzing popular Indian stocks:"
echo "   - RELIANCE (NSE)"
echo "   - TCS (NSE)"
echo "   - HDFCBANK (NSE)"
echo "   - INFY (NSE)"
echo ""
echo "💡 The system now uses PostgreSQL for better performance and scalability!"
echo "Happy trading! 📈"
