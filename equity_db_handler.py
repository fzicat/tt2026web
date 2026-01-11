import sqlite3
import pandas as pd

DB_NAME = "equity.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE,
            description TEXT,
            account TEXT,
            category TEXT,
            currency TEXT,
            rate REAL,
            balance REAL,
            tax REAL
        )
    ''')
    
    conn.commit()
    conn.close()

def save_equity_entry(entry_data):
    """
    Saves a single equity entry.
    entry_data: dict containing column names and values
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    columns = ', '.join(entry_data.keys())
    placeholders = ', '.join(['?'] * len(entry_data))
    sql = f"INSERT INTO equity ({columns}) VALUES ({placeholders})"
    
    try:
        cursor.execute(sql, list(entry_data.values()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving equity entry: {e}")
        return False
    finally:
        conn.close()

def fetch_equity_data():
    """
    Fetches all equity data, sorted by date descending.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM equity ORDER BY date DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error fetching equity data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def update_equity_entry(entry_id, entry_data):
    """
    Updates an existing equity entry by ID.
    entry_id: the ID of the entry to update
    entry_data: dict containing column names and values to update
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    set_clauses = ', '.join([f"{k} = ?" for k in entry_data.keys()])
    sql = f"UPDATE equity SET {set_clauses} WHERE id = ?"
    
    try:
        print(sql)
        print(list(entry_data.values()) + [entry_id])
        cursor.execute(sql, list(entry_data.values()) + [entry_id])
        print(cursor.rowcount)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating equity entry: {e}")
        return False
    finally:
        conn.close()
