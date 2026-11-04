"""Tests for static code quality checks."""
import pytest
from app.core.checks import (
    check_secrets,
    check_sql_injection,
    check_unused_imports,
    check_complexity,
    run_all_checks,
)


# ---- Secret detection ----

def test_secret_api_key():
    source = 'api_key = "sk-live-1234567890abcdef"'
    issues = check_secrets(source)
    assert len(issues) == 1
    assert issues[0].type == "secret"
    assert issues[0].severity == "warning"


def test_secret_password():
    source = 'password = "super-secret-pass-123"'
    issues = check_secrets(source)
    assert len(issues) == 1


def test_secret_token():
    source = 'token: "ghp_abcdefghijklmnopqr"'
    issues = check_secrets(source)
    assert len(issues) == 1


def test_secret_aws_key():
    source = 'key = "AKIAIOSFODNN7EXAMPLE1234"'
    issues = check_secrets(source)
    # AWS key pattern should be detected  
    assert any(i.type == "secret" for i in issues)


def test_secret_private_key():
    source = '-----BEGIN RSA KEY-----'
    issues = check_secrets(source)
    assert len(issues) == 1
    assert issues[0].severity == "high"


def test_secret_placeholder_skipped():
    source = 'api_key = "your_api_key_here"'
    issues = check_secrets(source)
    assert len(issues) == 0


def test_secret_example_skipped():
    source = 'password = "example_password"'
    issues = check_secrets(source)
    assert len(issues) == 0


def test_secret_env_var_skipped():
    source = 'api_key = os.environ["KEY"]'
    issues = check_secrets(source)
    assert len(issues) == 0


# ---- SQL injection detection ----

def test_sql_fstring():
    source = '''\
import sqlite3
conn = sqlite3.connect(":memory:")
def bad_query(user_id):
    conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
'''
    issues = check_sql_injection(source)
    assert len(issues) >= 1
    assert issues[0].type == "sql_injection"


def test_sql_string_concat():
    source = '''\
def bad(name):
    db.execute("SELECT * FROM t WHERE name = " + name)
'''
    issues = check_sql_injection(source)
    assert len(issues) >= 1


def test_sql_format():
    source = '''\
def bad(name):
    db.query("SELECT * FROM t WHERE name = %s".format(name))
'''
    issues = check_sql_injection(source)
    assert len(issues) >= 1


def test_sql_safe_query():
    source = '''\
def good(name):
    db.execute("SELECT * FROM t WHERE name = ?", (name,))
'''
    issues = check_sql_injection(source)
    assert len(issues) == 0


# ---- Unused import detection ----

def test_unused_import():
    source = '''\
import os
import sys

def greet():
    print(sys.argv[0])
'''
    issues = check_unused_imports(source)
    unused_names = [i.message for i in issues]
    assert any("os" in m for m in unused_names)
    # sys IS used
    assert not any("sys" in m for m in unused_names)


def test_used_import_not_flagged():
    source = '''\
from pathlib import Path
p = Path("/tmp")
'''
    issues = check_unused_imports(source)
    assert len(issues) == 0


def test_init_py_skipped():
    source = 'import os\n'
    issues = check_unused_imports(source, file_path="app/__init__.py")
    assert len(issues) == 0


def test_future_import_skipped():
    source = 'from __future__ import annotations\n'
    issues = check_unused_imports(source)
    assert len(issues) == 0


# ---- Complexity ----

def test_complexity_simple():
    source = '''\
def simple():
    return 42
'''
    issues = check_complexity(source, threshold=10)
    assert len(issues) == 0


def test_complexity_over_threshold():
    # Build a function with complexity > 10
    body = "\n".join(f"    if x == {i}: pass" for i in range(12))
    source = f"def complex_func(x):\n{body}\n"
    issues = check_complexity(source, threshold=10)
    assert len(issues) >= 1
    assert issues[0].type == "complexity"


def test_complexity_high_severity():
    body = "\n".join(f"    if x == {i}: pass" for i in range(22))
    source = f"def very_complex(x):\n{body}\n"
    issues = check_complexity(source, threshold=10)
    assert any(i.severity == "high" for i in issues)


def test_run_all_checks():
    source = '''\
import os
api_key = "sk-test-1234567890abcdef"

def do_query(user_id):
    db.execute(f"SELECT * FROM t WHERE id = {user_id}")
'''
    issues = run_all_checks(source, file_path="test.py")
    types = {i.type for i in issues}
    assert "secret" in types
    assert "sql_injection" in types
    assert "unused_import" in types
