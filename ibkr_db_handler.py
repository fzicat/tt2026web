import sqlite3
import pandas as pd
import os
from shared.config import DB_PATH

DB_NAME = os.path.join(DB_PATH, "ibkr.db")

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create trades table
    # Using text for most fields to be safe, real/integer for numbers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            tradeID TEXT PRIMARY KEY,
            accountId TEXT,
            underlyingSymbol TEXT,
            symbol TEXT,
            description TEXT,
            expiry TEXT,
            putCall TEXT,
            strike REAL,
            dateTime TEXT,
            quantity REAL,
            tradePrice REAL,
            multiplier REAL,
            ibCommission REAL,
            currency TEXT,
            notes TEXT,
            openCloseIndicator TEXT
        )
    ''')

    # Create market_price table
    # We drop and recreate to ensure checking for latest schema/primary key during dev
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_price (
            symbol TEXT PRIMARY KEY,
            price REAL,
            dateTime TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    ensure_schema()

def save_trade(trade_data):
    """
    Saves a trade dictionary to the database.
    Ignores if tradeID already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    columns = ', '.join(trade_data.keys())
    placeholders = ', '.join(['?'] * len(trade_data))
    sql = f"INSERT OR IGNORE INTO trades ({columns}) VALUES ({placeholders})"
    
    try:
        cursor.execute(sql, list(trade_data.values()))
        conn.commit()
        return cursor.rowcount > 0 # Returns True if inserted, False if ignored
    except Exception as e:
        print(f"Error saving trade {trade_data.get('tradeID')}: {e}")
        return False
    finally:
        conn.close()

def update_trade_fields(trade_id, updates):
    """
    Updates specific fields for a trade.
    updates: dict of column_name -> value
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values())
    values.append(trade_id)
    
    query = f"UPDATE trades SET {set_clause} WHERE tradeID = ?"
    
    try:
        cursor.execute(query, values)
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating trade {trade_id}: {e}")
        return False
    finally:
        conn.close()

def ensure_schema():
    """
    Ensures that the database schema is up to date.
    Adds new columns if they are missing.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if delta column exists
        cursor.execute("PRAGMA table_info(trades)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'delta' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN delta REAL")
            print("Added delta column to trades table.")
            
        if 'und_price' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN und_price REAL")
            print("Added und_price column to trades table.")
            
        conn.commit()
    except Exception as e:
        print(f"Error ensuring schema: {e}")
    finally:
        conn.close()

def fetch_all_trades_as_df():
    """
    Retrieves all trades from the database ordered by dateTime.
    Returns a pandas DataFrame.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM trades ORDER BY dateTime"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error fetching all trades: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def save_market_price(symbol, price, date_time):
    """
    Saves a market price to the database.
    Uses REPLACE to handle updates efficiently.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # REPLACE INTO works because symbol is PRIMARY KEY
        cursor.execute("INSERT OR REPLACE INTO market_price (symbol, price, dateTime) VALUES (?, ?, ?)", (symbol, price, date_time))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving market price for {symbol}: {e}")
        return False
    finally:
        conn.close()

def fetch_latest_market_prices():
    """
    Retrieves the latest market price for each symbol.
    Returns a dictionary {symbol: price}
    """
    conn = get_connection()
    try:
        # Since we only keep one row per symbol, simple select is enough
        query = "SELECT symbol, price FROM market_price"
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        print(f"Error fetching market prices: {e}")
        return {}
    finally:
        conn.close()
