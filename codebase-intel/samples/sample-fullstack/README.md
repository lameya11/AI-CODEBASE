# Sample Fullstack Project

This is a minimal sample project demonstrating the capabilities of Codebase Intelligence.

## Purpose

This sample is used to demonstrate the following analysis features:

- **Dependency Graph**: `main.py` → `auth.py` → `users.py` → `database.py`
- **Secret Detection**: `config.py` contains an intentional hardcoded API key (`api_key = "sk-live-..."`)
- **SQL Injection Warning**: `reports.py` uses an f-string inside a `run_query()` call
- **Complexity Warning**: `config.py` has a `complex_function()` with cyclomatic complexity > 10
- **Unused Import**: `reports.py` imports `os` but never uses it

## ⚠️ Intentional Warnings

The following code patterns are **intentionally wrong** for demo purposes:

| File | Issue | Type |
|------|-------|------|
| `backend/app/config.py` | `api_key = "sk-live-..."` | Secret |
| `backend/app/reports.py` | `run_query(f"SELECT ... {user_id}")` | SQL Injection |
| `backend/app/config.py` | `complex_function()` has 12+ branches | Complexity |
| `backend/app/reports.py` | `import os` never used | Unused Import |

**Never** use these patterns in production code.

## Structure

```
backend/
  app/
    main.py      - FastAPI app with /login and /users routes
    auth.py      - Login logic (imports from users + database)
    users.py     - User management (imports from database)
    database.py  - Database connection and query helpers
    config.py    - Config with intentional secret + complex function
    reports.py   - Reports with intentional SQL injection + unused import
frontend/
  src/
    App.jsx          - Main app component
    Login.jsx        - Login form (imports api + auth-utils)
    api.js           - API client for /login and /users
    auth-utils.js    - Auth helper functions
```
