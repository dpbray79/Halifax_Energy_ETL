#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# init_database.sh
# Halifax Energy Forecasting — Database Initialization Script
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE:
#   1. Wait for SQL Server Docker container to be ready
#   2. Create the HalifaxEnergyProject database
#   3. Run create_seed_tables.sql to create all tables
#
# USAGE:
#   chmod +x init_database.sh
#   ./init_database.sh
#
# ══════════════════════════════════════════════════════════════════════════════

set -e

# Load environment variables
if [ -f .env ]; then
    # Source the .env file properly, ignoring comments and empty lines
    set -a
    source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
    set +a
else
    echo "❌ .env file not found! Copy .env.example to .env and configure it."
    exit 1
fi

echo "══════════════════════════════════════════════════════════════════════════"
echo "  Halifax Energy Forecasting — Database Initialization"
echo "══════════════════════════════════════════════════════════════════════════"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is running"
echo ""

# Start SQL Server container
echo "Starting SQL Server container..."
docker-compose up -d sqlserver

echo ""
echo "Waiting for SQL Server to be ready..."
echo "(This may take 30-60 seconds on first run)"
echo ""

# Wait for SQL Server to be healthy
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if docker-compose exec -T sqlserver /opt/mssql-tools/bin/sqlcmd \
        -S localhost -U sa -P "${SA_PASSWORD}" -Q "SELECT 1" -b > /dev/null 2>&1; then
        echo "✓ SQL Server is ready!"
        break
    fi
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo ""
    echo "❌ SQL Server failed to start within ${MAX_WAIT} seconds"
    echo "Check logs with: docker-compose logs sqlserver"
    exit 1
fi

echo ""
echo "Creating database: ${MSSQL_DATABASE}..."
echo ""

# Create the database
docker-compose exec -T sqlserver /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "${SA_PASSWORD}" \
    -Q "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'${MSSQL_DATABASE}') CREATE DATABASE ${MSSQL_DATABASE};"

echo "✓ Database created (or already exists)"
echo ""
echo "Running table creation script: sql/create_seed_tables.sql..."
echo ""

# Copy SQL file into container and run it
docker cp sql/create_seed_tables.sql halifaxenergy_sqlserver:/tmp/create_seed_tables.sql

docker-compose exec -T sqlserver /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "${SA_PASSWORD}" \
    -d "${MSSQL_DATABASE}" \
    -i /tmp/create_seed_tables.sql

echo ""
echo "══════════════════════════════════════════════════════════════════════════"
echo "  ✅ Database initialization complete!"
echo "══════════════════════════════════════════════════════════════════════════"
echo ""
echo "Database:      ${MSSQL_DATABASE}"
echo "Host:          localhost:1433"
echo "Username:      sa"
echo "Password:      ${SA_PASSWORD}"
echo ""
echo "Next steps:"
echo "  1. Verify tables: docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P '${SA_PASSWORD}' -d ${MSSQL_DATABASE} -Q \"SELECT name FROM sys.tables ORDER BY name\""
echo "  2. Seed historical data: python seed_historical_data.py"
echo "  3. Start FastAPI: cd api && uvicorn main:app --reload"
echo ""
echo "══════════════════════════════════════════════════════════════════════════"
