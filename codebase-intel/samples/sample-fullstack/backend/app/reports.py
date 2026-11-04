"""Reports module with intentional SQL injection warning for demo purposes."""
import os

# os is imported but unused — will trigger unused_import warning


def get_report(user_id: int):
    """Get a report for a user.

    ⚠️ INTENTIONAL WARNING: Uses an f-string in a SQL call.
    This will trigger the SQL injection check in Codebase Intelligence.
    In production, always use parameterized queries.
    """
    from app.database import run_query
    return run_query(f"SELECT * FROM reports WHERE user_id = {user_id}")


def get_summary_report(start_date: str, end_date: str):
    """Get a summary report for a date range.

    ⚠️ INTENTIONAL WARNING: Uses string concatenation in a SQL call.
    """
    from app.database import run_query
    return run_query(
        "SELECT * FROM reports WHERE date BETWEEN " + start_date + " AND " + end_date
    )
