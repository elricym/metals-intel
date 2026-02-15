"""Data ingestion modules for metals-intel."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'metals.db')

def get_db():
    return sqlite3.connect(DB_PATH)
