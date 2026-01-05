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
