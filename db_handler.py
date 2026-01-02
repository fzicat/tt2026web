import sqlite3
import pandas as pd

DB_NAME = "tradetools.db"

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
    
    conn.commit()
    conn.close()

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
