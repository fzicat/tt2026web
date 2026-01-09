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
    
def ensure_schema():
    # Placeholder for future schema updates if needed
    pass

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

def save_account_entry(entry):
    """
    Saves a single account entry to the database.
    First deletes any existing entry for the same date and account.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Delete existing entry if any
        cursor.execute("DELETE FROM fbn WHERE date = ? AND account = ?", (entry['date'], entry['account']))
        
        # Insert new entry
        columns = ', '.join(entry.keys())
        placeholders = ', '.join(['?'] * len(entry))
        sql = f"INSERT INTO fbn ({columns}) VALUES ({placeholders})"
        
        cursor.execute(sql, list(entry.values()))
        conn.commit()
    except Exception as e:
        print(f"Error saving account entry: {e}")
        raise e
    finally:
        conn.close()
