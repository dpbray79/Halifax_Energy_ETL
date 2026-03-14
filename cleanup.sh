#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# cleanup.sh
# Halifax Energy Forecasting — Disk Space Cleanup Script
# ══════════════════════════════════════════════════════════════════════════════
#
# USAGE:
#   ./cleanup.sh [OPTIONS]
#
# OPTIONS:
#   --temp-only       Clean only temporary files (safe)
#   --csvs            Remove Electricity Maps CSV files (after seeding)
#   --logs            Remove old log files
#   --dev-deps        Remove node_modules and Python venv (can reinstall)
#   --all-safe        Run all safe cleanups (temp + csvs + logs)
#   --nuclear         Remove EVERYTHING including database (⚠️ DANGER!)
#
# ══════════════════════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track total space freed
SPACE_FREED=0

# Function to get directory size
get_dir_size() {
    if [ -d "$1" ]; then
        du -sh "$1" 2>/dev/null | cut -f1
    else
        echo "0K"
    fi
}

# Function to calculate space freed
calc_space() {
    local dir=$1
    if [ -d "$dir" ]; then
        du -sk "$dir" 2>/dev/null | cut -f1 || echo 0
    else
        echo 0
    fi
}

echo "══════════════════════════════════════════════════════════════════════════"
echo "  Halifax Energy Forecasting — Disk Space Cleanup"
echo "══════════════════════════════════════════════════════════════════════════"
echo ""

# Parse arguments
TEMP_ONLY=false
CSVS=false
LOGS=false
DEV_DEPS=false
ALL_SAFE=false
NUCLEAR=false

if [ $# -eq 0 ]; then
    echo "No options specified. Use --help to see available options."
    echo ""
    echo "Quick options:"
    echo "  ./cleanup.sh --all-safe    # Clean temp files, CSVs, and logs"
    echo "  ./cleanup.sh --temp-only   # Clean only temporary files"
    echo "  ./cleanup.sh --help        # Show all options"
    exit 0
fi

for arg in "$@"; do
    case $arg in
        --temp-only) TEMP_ONLY=true ;;
        --csvs) CSVS=true ;;
        --logs) LOGS=true ;;
        --dev-deps) DEV_DEPS=true ;;
        --all-safe) ALL_SAFE=true ;;
        --nuclear) NUCLEAR=true ;;
        --help)
            echo "Cleanup options:"
            echo "  --temp-only    Clean temporary files only (Python __pycache__, etc.)"
            echo "  --csvs         Remove Electricity Maps CSV files (safe after seeding)"
            echo "  --logs         Remove old log files (keeps last 7 days)"
            echo "  --dev-deps     Remove node_modules and venv (can reinstall)"
            echo "  --all-safe     Clean temp + CSVs + logs (recommended)"
            echo "  --nuclear      Remove EVERYTHING including database (⚠️ DANGEROUS)"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help to see available options"
            exit 1
            ;;
    esac
done

# If --all-safe, enable safe cleanups
if [ "$ALL_SAFE" = true ]; then
    TEMP_ONLY=true
    CSVS=true
    LOGS=true
fi

# ══════════════════════════════════════════════════════════════════════════════
# 1. TEMPORARY FILES (ALWAYS SAFE)
# ══════════════════════════════════════════════════════════════════════════════

if [ "$TEMP_ONLY" = true ] || [ "$ALL_SAFE" = true ] || [ "$NUCLEAR" = true ]; then
    echo "🧹 Cleaning temporary files..."

    # Python cache
    BEFORE=$(calc_space ".")
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    AFTER=$(calc_space ".")
    FREED=$((BEFORE - AFTER))
    SPACE_FREED=$((SPACE_FREED + FREED))

    echo "  ✓ Removed Python cache files"

    # Temporary seed files
    if [ -f "__tmp_load" ]; then rm -f "__tmp_load"; fi
    if [ -f "__tmp_wx" ]; then rm -f "__tmp_wx"; fi
    if [ -f "__tmp_predictions" ]; then rm -f "__tmp_predictions"; fi

    echo "  ✓ Removed temporary database files"
fi

# ══════════════════════════════════════════════════════════════════════════════
# 2. ELECTRICITY MAPS CSV FILES (SAFE AFTER SEEDING)
# ══════════════════════════════════════════════════════════════════════════════

if [ "$CSVS" = true ] || [ "$ALL_SAFE" = true ] || [ "$NUCLEAR" = true ]; then
    echo ""
    echo "📁 Cleaning Electricity Maps CSV files..."

    if [ -d "data/electricitymaps" ]; then
        BEFORE=$(calc_space "data/electricitymaps")
        CSV_COUNT=$(find data/electricitymaps -type f -name "*.csv" | wc -l | tr -d ' ')

        if [ "$CSV_COUNT" -gt 0 ]; then
            echo -e "${YELLOW}  Found $CSV_COUNT CSV files${NC}"
            echo -e "${YELLOW}  Current size: $(get_dir_size data/electricitymaps)${NC}"
            echo ""
            read -p "  Remove CSV files? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                find data/electricitymaps -type f -name "*.csv" -delete
                AFTER=$(calc_space "data/electricitymaps")
                FREED=$((BEFORE - AFTER))
                SPACE_FREED=$((SPACE_FREED + FREED))
                echo -e "${GREEN}  ✓ Removed $CSV_COUNT CSV files${NC}"
            else
                echo "  Skipped CSV cleanup"
            fi
        else
            echo "  No CSV files found"
        fi
    else
        echo "  No electricitymaps directory found"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 3. LOG FILES (KEEP RECENT, PURGE OLD)
# ══════════════════════════════════════════════════════════════════════════════

if [ "$LOGS" = true ] || [ "$ALL_SAFE" = true ] || [ "$NUCLEAR" = true ]; then
    echo ""
    echo "📋 Cleaning old log files..."

    if [ -d "logs" ]; then
        BEFORE=$(calc_space "logs")

        # Remove logs older than 7 days
        find logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true

        # Truncate large current logs (keep last 1000 lines)
        for log in logs/*.log; do
            if [ -f "$log" ]; then
                LINES=$(wc -l < "$log" 2>/dev/null || echo 0)
                if [ "$LINES" -gt 1000 ]; then
                    tail -n 1000 "$log" > "$log.tmp" && mv "$log.tmp" "$log"
                fi
            fi
        done

        AFTER=$(calc_space "logs")
        FREED=$((BEFORE - AFTER))
        SPACE_FREED=$((SPACE_FREED + FREED))

        echo "  ✓ Cleaned old log files (kept last 7 days)"
        echo "  Current logs size: $(get_dir_size logs)"
    fi

    # Clean seed_run.log if it exists
    if [ -f "seed_run.log" ]; then
        rm -f seed_run.log
        echo "  ✓ Removed seed_run.log"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 4. DEVELOPMENT DEPENDENCIES (CAN REINSTALL)
# ══════════════════════════════════════════════════════════════════════════════

if [ "$DEV_DEPS" = true ] || [ "$NUCLEAR" = true ]; then
    echo ""
    echo "📦 Cleaning development dependencies..."

    # Node modules
    if [ -d "dashboard/node_modules" ]; then
        BEFORE=$(calc_space "dashboard/node_modules")
        echo -e "${YELLOW}  node_modules size: $(get_dir_size dashboard/node_modules)${NC}"
        read -p "  Remove node_modules? (can reinstall with 'npm install') (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf dashboard/node_modules
            SPACE_FREED=$((SPACE_FREED + BEFORE))
            echo -e "${GREEN}  ✓ Removed node_modules${NC}"
        fi
    fi

    # Python venv
    if [ -d "venv" ]; then
        BEFORE=$(calc_space "venv")
        echo -e "${YELLOW}  venv size: $(get_dir_size venv)${NC}"
        read -p "  Remove Python venv? (can recreate with 'python -m venv venv') (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
            SPACE_FREED=$((SPACE_FREED + BEFORE))
            echo -e "${GREEN}  ✓ Removed venv${NC}"
        fi
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# 5. NUCLEAR OPTION (REMOVE EVERYTHING)
# ══════════════════════════════════════════════════════════════════════════════

if [ "$NUCLEAR" = true ]; then
    echo ""
    echo -e "${RED}⚠️  NUCLEAR CLEANUP REQUESTED ⚠️${NC}"
    echo -e "${RED}This will remove:${NC}"
    echo -e "${RED}  • All data in the database${NC}"
    echo -e "${RED}  • Docker volumes${NC}"
    echo -e "${RED}  • Model artifacts${NC}"
    echo -e "${RED}  • All logs${NC}"
    echo ""
    echo -e "${YELLOW}You will need to re-seed all data and retrain models!${NC}"
    echo ""
    read -p "Are you ABSOLUTELY SURE? Type 'DELETE EVERYTHING' to confirm: " CONFIRM

    if [ "$CONFIRM" = "DELETE EVERYTHING" ]; then
        echo ""
        echo "💥 Executing nuclear cleanup..."

        # Stop and remove containers
        docker-compose down -v 2>/dev/null || true
        echo "  ✓ Removed Docker containers and volumes"

        # Remove model artifacts
        if [ -d "model/model_artifacts" ]; then
            rm -rf model/model_artifacts/*
            echo "  ✓ Removed model artifacts"
        fi

        # Remove all logs
        if [ -d "logs" ]; then
            rm -rf logs/*
            echo "  ✓ Removed all logs"
        fi

        echo ""
        echo -e "${GREEN}✓ Nuclear cleanup complete${NC}"
        echo ""
        echo "To restore your system:"
        echo "  1. ./init_database.sh"
        echo "  2. python scripts/seed_historical_data.py --start 2023-01-01"
        echo "  3. Rscript model/HalifaxEnergy_Model.R"
    else
        echo "Nuclear cleanup cancelled (confirmation did not match)"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo "══════════════════════════════════════════════════════════════════════════"
echo "  Cleanup Summary"
echo "══════════════════════════════════════════════════════════════════════════"

# Convert KB to human readable
SPACE_MB=$((SPACE_FREED / 1024))
if [ $SPACE_MB -gt 1024 ]; then
    SPACE_GB=$((SPACE_MB / 1024))
    echo -e "${GREEN}  Space freed: ~${SPACE_GB} GB${NC}"
else
    echo -e "${GREEN}  Space freed: ~${SPACE_MB} MB${NC}"
fi

echo ""
echo "Current disk usage:"
echo "  Database:        $(docker system df -v 2>/dev/null | grep halifaxenergy_sqlserver_data | awk '{print $3}' || echo 'N/A')"
echo "  Logs:            $(get_dir_size logs 2>/dev/null || echo '0')"
echo "  Model artifacts: $(get_dir_size model/model_artifacts 2>/dev/null || echo '0')"
echo "  CSV files:       $(get_dir_size data/electricitymaps 2>/dev/null || echo '0')"
echo ""
