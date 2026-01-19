import sqlite3
import pandas as pd
import os
from shared.config import DB_PATH

DB_NAME = os.path.join(DB_PATH, "equity.db")

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

def save_equity_entries(entries_list):
    """
    Bulk insert multiple equity entries in a single transaction.
    entries_list: list of dicts, each containing column names and values
    """
    if not entries_list:
        return True
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Use first entry to get column names
    columns = ', '.join(entries_list[0].keys())
    placeholders = ', '.join(['?'] * len(entries_list[0]))
    sql = f"INSERT INTO equity ({columns}) VALUES ({placeholders})"
    
    try:
        for entry in entries_list:
            cursor.execute(sql, list(entry.values()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving equity entries: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_equity_entry(entry_id):
    """
    Delete a single equity entry by ID.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM equity WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting equity entry: {e}")
        return False
    finally:
        conn.close()
