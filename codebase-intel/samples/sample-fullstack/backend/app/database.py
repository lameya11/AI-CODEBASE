"""Sample FastAPI backend for demo/testing purposes."""
import sqlite3

def get_connection():
    """Get a database connection."""
    return sqlite3.connect(":memory:")

def run_query(sql, params=()):
    """Execute a SQL query and return results."""
    conn = get_connection()
    return conn.execute(sql, params).fetchall()
