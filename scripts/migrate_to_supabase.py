"""
Migrate data from SQLite databases to Supabase.

This script reads data from the local SQLite databases in ./data/
and imports them into Supabase tables.

Usage:
    python scripts/migrate_to_supabase.py

Make sure your .env file has the correct SUPABASE_URL and SUPABASE_KEY set.
"""
import sqlite3
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import DB_PATH
from shared.supabase_client import get_client


# Column mapping from SQLite camelCase to PostgreSQL snake_case (for IBKR trades)
TRADES_COLUMN_MAP = {
    'tradeID': 'trade_id',
    'accountId': 'account_id',
    'underlyingSymbol': 'underlying_symbol',
    'symbol': 'symbol',
    'description': 'description',
    'expiry': 'expiry',
    'putCall': 'put_call',
    'strike': 'strike',
    'dateTime': 'date_time',
    'quantity': 'quantity',
    'tradePrice': 'trade_price',
    'multiplier': 'multiplier',
    'ibCommission': 'ib_commission',
    'currency': 'currency',
    'notes': 'notes',
    'openCloseIndicator': 'open_close_indicator',
    'delta': 'delta',
    'und_price': 'und_price',
}

MARKET_PRICE_COLUMN_MAP = {
    'symbol': 'symbol',
    'price': 'price',
    'dateTime': 'date_time',
}


def convert_datetime(dt_str):
    """Convert compact datetime string (YYYYMMDDHHmmss) to ISO format."""
    if not dt_str:
        return None
    try:
        # Try parsing compact format: 20251229110122
        if len(dt_str) == 14 and dt_str.isdigit():
            dt = datetime.strptime(dt_str, '%Y%m%d%H%M%S')
            return dt.isoformat()
        # Already in a parseable format, try to parse and return ISO
        return dt_str
    except Exception:
        return dt_str


def migrate_ibkr():
    """Migrate IBKR trades and market prices."""
    db_path = os.path.join(DB_PATH, "ibkr.db")
    if not os.path.exists(db_path):
        print(f"IBKR database not found at {db_path}")
        return

    print("Migrating IBKR data...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    client = get_client()

    # Migrate trades
    print("  Migrating trades...")
    cursor.execute("SELECT * FROM trades")
    trades = cursor.fetchall()
    print(f"    Found {len(trades)} trades")

    if trades:
        batch_size = 100
        for i in range(0, len(trades), batch_size):
            batch = trades[i:i + batch_size]
            data = []
            for trade in batch:
                trade_dict = dict(trade)
                # Convert column names
                converted = {}
                for old_key, new_key in TRADES_COLUMN_MAP.items():
                    if old_key in trade_dict:
                        value = trade_dict[old_key]
                        # Convert datetime fields
                        if new_key == 'date_time':
                            value = convert_datetime(value)
                        converted[new_key] = value
                data.append(converted)

            try:
                client.table('trades').upsert(data, on_conflict='trade_id').execute()
                print(f"    Migrated trades {i + 1} to {min(i + batch_size, len(trades))}")
            except Exception as e:
                print(f"    Error migrating trades batch: {e}")

    # Migrate market prices
    print("  Migrating market prices...")
    cursor.execute("SELECT * FROM market_price")
    prices = cursor.fetchall()
    print(f"    Found {len(prices)} market prices")

    if prices:
        data = []
        for price in prices:
            price_dict = dict(price)
            converted = {}
            for old_key, new_key in MARKET_PRICE_COLUMN_MAP.items():
                if old_key in price_dict:
                    value = price_dict[old_key]
                    # Convert datetime fields
                    if new_key == 'date_time':
                        value = convert_datetime(value)
                    converted[new_key] = value
            data.append(converted)

        try:
            client.table('market_price').upsert(data, on_conflict='symbol').execute()
            print(f"    Migrated {len(data)} market prices")
        except Exception as e:
            print(f"    Error migrating market prices: {e}")

    conn.close()
    print("  IBKR migration complete!")


def migrate_fbn():
    """Migrate FBN data."""
    db_path = os.path.join(DB_PATH, "fbn.db")
    if not os.path.exists(db_path):
        print(f"FBN database not found at {db_path}")
        return

    print("Migrating FBN data...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    client = get_client()

    cursor.execute("SELECT * FROM fbn")
    entries = cursor.fetchall()
    print(f"  Found {len(entries)} FBN entries")

    if entries:
        batch_size = 100
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            data = []
            for entry in batch:
                entry_dict = dict(entry)
                # Remove 'id' as it will be auto-generated
                if 'id' in entry_dict:
                    del entry_dict['id']
                data.append(entry_dict)

            try:
                # Delete existing entries first (based on date + account)
                for item in data:
                    client.table('fbn').delete().eq('date', item['date']).eq('account', item['account']).execute()

                client.table('fbn').insert(data).execute()
                print(f"    Migrated FBN entries {i + 1} to {min(i + batch_size, len(entries))}")
            except Exception as e:
                print(f"    Error migrating FBN batch: {e}")

    conn.close()
    print("  FBN migration complete!")


def migrate_equity():
    """Migrate Equity data."""
    db_path = os.path.join(DB_PATH, "equity.db")
    if not os.path.exists(db_path):
        print(f"Equity database not found at {db_path}")
        return

    print("Migrating Equity data...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    client = get_client()

    cursor.execute("SELECT * FROM equity")
    entries = cursor.fetchall()
    print(f"  Found {len(entries)} equity entries")

    if entries:
        # First, clear existing data
        try:
            client.table('equity').delete().neq('id', 0).execute()
            print("  Cleared existing equity data")
        except Exception as e:
            print(f"  Warning: Could not clear existing data: {e}")

        batch_size = 100
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            data = []
            for entry in batch:
                entry_dict = dict(entry)
                # Remove 'id' as it will be auto-generated
                if 'id' in entry_dict:
                    del entry_dict['id']
                data.append(entry_dict)

            try:
                client.table('equity').insert(data).execute()
                print(f"    Migrated equity entries {i + 1} to {min(i + batch_size, len(entries))}")
            except Exception as e:
                print(f"    Error migrating equity batch: {e}")

    conn.close()
    print("  Equity migration complete!")


def main():
    print("=" * 50)
    print("SQLite to Supabase Migration")
    print("=" * 50)
    print()

    # Test Supabase connection
    try:
        client = get_client()
        print("Connected to Supabase successfully!")
        print()
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
        print("Make sure your .env file has SUPABASE_URL and SUPABASE_KEY set correctly.")
        sys.exit(1)

    migrate_ibkr()
    print()

    migrate_fbn()
    print()

    migrate_equity()
    print()

    print("=" * 50)
    print("Migration complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
