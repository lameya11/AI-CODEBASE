"""Sample Python file for parser tests."""
import os
import sys
from pathlib import Path
from app.users import find_user
from . import helper  # relative import

API_KEY = "sk-test-1234567890abcdef"  # for secret detection tests


def greet(name: str) -> str:
    """Return a greeting string."""
    return f"Hello, {name}"


def unused_function():
    pass


class UserService:
    """Service for managing users."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def create_user(self, username: str, email: str):
        """Create a new user."""
        return find_user(username)

    def delete_user(self, user_id: int):
        if user_id < 0:
            raise ValueError("negative id")
        return True
