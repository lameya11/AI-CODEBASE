"""Authentication module."""
from app.users import find_user
from app.database import get_connection


def login(username: str, password: str):
    """Authenticate a user and return a session token.

    In a real app, passwords would be hashed and compared securely.
    This is a demo — never store plaintext passwords in production.
    """
    users = find_user(username)
    if not users:
        return None
    # Simplified: just return a fake token for demo
    return {"user": username, "token": f"fake-token-{username}"}


def logout(token: str):
    """Invalidate a session token."""
    # In a real app, remove token from session store
    return True
