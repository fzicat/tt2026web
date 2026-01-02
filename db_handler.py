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

def get_trades_by_symbol(symbol):
    """
    Retrieves trades for a specific symbol.
    Returns a pandas DataFrame with selected columns.
    """
    conn = get_connection()
    try:
        query = '''
            SELECT dateTime, description, quantity, tradePrice, ibCommission, openCloseIndicator 
            FROM trades 
            WHERE symbol = ? OR underlyingSymbol = ?
            ORDER BY dateTime DESC
        '''
        df = pd.read_sql_query(query, conn, params=(symbol, symbol))
        return df
    except Exception as e:
        print(f"Error retrieving trades for {symbol}: {e}")
        return pd.DataFrame()
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
