import sqlite3
import pandas as pd

DB_NAME = "fbn.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

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
