import sqlite3
import os

# Path to shared data folder
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def get_ibkr_connection():
    return sqlite3.connect(os.path.join(DB_PATH, "ibkr.db"), check_same_thread=False)

def get_fbn_connection():
    return sqlite3.connect(os.path.join(DB_PATH, "fbn.db"), check_same_thread=False)

def get_equity_connection():
    return sqlite3.connect(os.path.join(DB_PATH, "equity.db"), check_same_thread=False)

def dict_factory(cursor, row):
    """Convert sqlite3 rows to dictionaries"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
