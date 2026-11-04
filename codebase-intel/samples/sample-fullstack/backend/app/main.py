"""Main FastAPI application."""
from fastapi import FastAPI, HTTPException
from app.auth import login
from app.users import find_user, list_users

app = FastAPI(title="Sample Demo API")


@app.post("/login")
def do_login(credentials: dict):
    """Authenticate a user."""
    username = credentials.get("username")
    password = credentials.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    result = login(username, password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result


@app.get("/users")
def get_users():
    """List all users."""
    return list_users()
