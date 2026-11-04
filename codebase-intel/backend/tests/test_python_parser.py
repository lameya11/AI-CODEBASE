"""Tests for the Python parser."""
import pytest
from app.core.parsers.python_parser import parse_python


SIMPLE_SOURCE = '''\
import os
import sys
from pathlib import Path
from app.users import find_user, create_user
from . import helper

def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}"

class UserService:
    """User service."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def create_user(self, username: str):
        return find_user(username)
'''

ROUTE_SOURCE = '''\
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    """List all users."""
    return []

@app.post("/login")
async def login(credentials: dict):
    return {"token": "x"}
'''

SYNTAX_ERROR_SOURCE = '''\
def broken(
    # missing closing paren
'''


def test_absolute_imports():
    result = parse_python(SIMPLE_SOURCE)
    modules = [i.module for i in result.imports]
    assert "os" in modules
    assert "sys" in modules
    assert "pathlib" in modules
    assert "app.users" in modules


def test_relative_imports():
    result = parse_python(SIMPLE_SOURCE)
    relative = [i for i in result.imports if i.level > 0]
    assert len(relative) == 1
    assert relative[0].level == 1


def test_imported_names():
    result = parse_python(SIMPLE_SOURCE)
    app_import = next(i for i in result.imports if i.module == "app.users")
    assert "find_user" in app_import.names
    assert "create_user" in app_import.names


def test_function_detection():
    result = parse_python(SIMPLE_SOURCE)
    func_names = [s.name for s in result.symbols if s.kind == "function"]
    assert "greet" in func_names


def test_class_detection():
    result = parse_python(SIMPLE_SOURCE)
    class_names = [s.name for s in result.symbols if s.kind == "class"]
    assert "UserService" in class_names


def test_method_detection():
    result = parse_python(SIMPLE_SOURCE)
    methods = [s for s in result.symbols if s.kind == "method"]
    method_names = [m.name for m in methods]
    assert "__init__" in method_names
    assert "create_user" in method_names


def test_method_parent():
    result = parse_python(SIMPLE_SOURCE)
    init = next(s for s in result.symbols if s.name == "__init__" and s.kind == "method")
    assert init.parent_name == "UserService"


def test_docstring_extraction():
    result = parse_python(SIMPLE_SOURCE)
    greet = next(s for s in result.symbols if s.name == "greet")
    assert greet.docstring == "Return a greeting."


def test_fastapi_route_detection():
    result = parse_python(ROUTE_SOURCE)
    routes = [s for s in result.symbols if s.kind == "route"]
    assert len(routes) == 2
    methods = {r.route_method for r in routes}
    paths = {r.route_path for r in routes}
    assert "GET" in methods
    assert "POST" in methods
    assert "/users" in paths
    assert "/login" in paths


def test_call_extraction():
    result = parse_python(SIMPLE_SOURCE)
    callee_names = [c.callee for c in result.calls]
    assert "find_user" in callee_names


def test_syntax_error_handling():
    result = parse_python(SYNTAX_ERROR_SOURCE)
    assert result.parse_error is not None
    assert len(result.symbols) == 0


def test_line_numbers():
    result = parse_python(SIMPLE_SOURCE)
    greet = next(s for s in result.symbols if s.name == "greet")
    assert greet.start_line > 0
    assert greet.end_line >= greet.start_line
