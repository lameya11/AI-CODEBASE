"""Application configuration.

WARNING: This file contains intentional security warnings for demo purposes.
Never hardcode credentials in production code!
"""

# ⚠️ INTENTIONAL WARNING: Hardcoded API key for demo/testing only
# This will trigger the secret detection check in Codebase Intelligence.
api_key = "sk-live-1234567890abcdef"

# Database configuration
DATABASE_URL = "sqlite:///./app.db"


def complex_function(x, y, z, mode="default"):
    """A deliberately complex function to demonstrate complexity warnings.

    This function has cyclomatic complexity > 10.
    """
    result = 0
    if mode == "add":
        result = x + y
    elif mode == "subtract":
        result = x - y
    elif mode == "multiply":
        result = x * y
    elif mode == "divide":
        if y != 0:
            result = x / y
        else:
            result = 0
    elif mode == "power":
        result = x ** y
    else:
        for i in range(z):
            if i % 2 == 0:
                result += i
            elif i % 3 == 0:
                result -= i
            elif i % 5 == 0:
                result *= i

    if result < 0:
        result = abs(result)
    elif result > 1000:
        result = result % 1000

    return result
