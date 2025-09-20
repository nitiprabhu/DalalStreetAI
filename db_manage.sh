#!/bin/bash

# Database Management Script for AI Trading Agent
echo "🗄️  AI Trading Agent - Database Management"
echo "=========================================="

# Check if docker-compose is running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Docker containers are not running. Please start them first:"
    echo "   docker-compose up -d"
    exit 1
fi

# Function to show menu
show_menu() {
    echo ""
    echo "Select an option:"
    echo "1) Connect to database shell"
    echo "2) View database tables"
    echo "3) View recent decisions"
    echo "4) View cached data"
    echo "5) Clear old cache (older than 24 hours)"
    echo "6) Clear old decisions (older than 30 days)"
    echo "7) Show database statistics"
    echo "8) Backup database"
    echo "9) Exit"
    echo ""
}

# Function to connect to database shell
db_shell() {
    echo "🔌 Connecting to PostgreSQL shell..."
    docker-compose exec database psql -U trading_user -d trading_agent
}

# Function to view tables
view_tables() {
    echo "📋 Database Tables:"
    docker-compose exec database psql -U trading_user -d trading_agent -c "\dt"
}

# Function to view recent decisions
view_decisions() {
    echo "📊 Recent Trading Decisions:"
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT * FROM recent_decisions LIMIT 10;"
}

# Function to view cached data
view_cache() {
    echo "💾 Cached Stock Data:"
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT symbol, exchange, last_updated FROM stock_data_cache ORDER BY last_updated DESC LIMIT 10;"
}

# Function to clear old cache
clear_old_cache() {
    echo "🧹 Clearing old cache data..."
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT clean_old_cache();"
    echo "✅ Old cache cleared!"
}

# Function to clear old decisions
clear_old_decisions() {
    echo "🧹 Clearing old decisions..."
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT clean_old_decisions();"
    echo "✅ Old decisions cleared!"
}

# Function to show database statistics
show_stats() {
    echo "📈 Database Statistics:"
    echo ""
    echo "Total Decisions:"
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT COUNT(*) as total_decisions FROM decisions;"
    echo ""
    echo "Cached Symbols:"
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT COUNT(*) as cached_symbols FROM stock_data_cache;"
    echo ""
    echo "Recent Activity (Last 24 hours):"
    docker-compose exec database psql -U trading_user -d trading_agent -c "SELECT COUNT(*) as recent_decisions FROM decisions WHERE timestamp > NOW() - INTERVAL '24 hours';"
}

# Function to backup database
backup_db() {
    echo "💾 Creating database backup..."
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="trading_agent_backup_${timestamp}.sql"
    
    docker-compose exec database pg_dump -U trading_user -d trading_agent > "$backup_file"
    
    if [ $? -eq 0 ]; then
        echo "✅ Backup created: $backup_file"
    else
        echo "❌ Backup failed!"
    fi
}

# Main menu loop
while true; do
    show_menu
    read -p "Enter your choice (1-9): " choice
    
    case $choice in
        1) db_shell ;;
        2) view_tables ;;
        3) view_decisions ;;
        4) view_cache ;;
        5) clear_old_cache ;;
        6) clear_old_decisions ;;
        7) show_stats ;;
        8) backup_db ;;
        9) echo "👋 Goodbye!"; exit 0 ;;
        *) echo "❌ Invalid option. Please try again." ;;
    esac
    
    read -p "Press Enter to continue..."
done
