"""User management module."""
from app.database import get_connection, run_query


def find_user(username: str):
    """Find a user by username."""
    return run_query("SELECT * FROM users WHERE username = ?", (username,))


def create_user(username: str, email: str):
    """Create a new user."""
    return run_query(
        "INSERT INTO users (username, email) VALUES (?, ?)",
        (username, email),
    )


def list_users():
    """List all users."""
    return run_query("SELECT id, username, email FROM users")
