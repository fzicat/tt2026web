import sqlite3
import pandas as pd

DB_NAME = "fbn.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create fbn table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fbn (
            id INTEGER PRIMARY KEY,
            date DATE,
            account TEXT,
            portfolio TEXT,
            investment REAL,
            deposit REAL,
            interest REAL,
            dividend REAL,
            distribution REAL,
            tax REAL,
            fee REAL,
            other REAL,
            cash REAL,
            asset REAL,
            currency TEXT,
            rate REAL
        )
    ''')

    conn.commit()
    conn.close()
    
    ensure_schema()

def fetch_fbn_data():
    """
    Retrieves all data from the fbn table.
    Returns a pandas DataFrame.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM fbn"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error fetching fbn data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
