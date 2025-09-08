import os
import sys
import asyncio
import pytest

# Ensure repository root is on sys.path so `from app ...` works
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure tests use SQLite and disable background poller BEFORE importing app modules
os.environ["DISABLE_POLLER"] = os.environ.get("DISABLE_POLLER", "1")
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.db import create_all_for_testing, drop_all_for_testing, Base


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def setup_db_schema():
    # Create schema before tests
    asyncio.run(create_all_for_testing(Base.metadata))
    yield
    # Drop schema after tests
    asyncio.run(drop_all_for_testing(Base.metadata))
