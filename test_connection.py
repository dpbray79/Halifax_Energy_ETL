import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

print("Testing Supabase connection...")
print(f"URL: {DATABASE_URL[:50]}..." if DATABASE_URL else "ERROR: DATABASE_URL not found!")

try:
    # Create engine
    engine = create_engine(DATABASE_URL)

    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM etl_watermark"))
        count = result.scalar()
        print(f"✅ Connection successful!")
        print(f"✅ Found {count} rows in etl_watermark table")

        # Check all tables exist
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print(f"✅ Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table}")

except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your DATABASE_URL in .env")
    print("2. Verify password is correct")
    print("3. Check Supabase project is not paused")
