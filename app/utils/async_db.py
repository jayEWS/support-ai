"""
Async Database Utilities
=========================
Provides async wrappers for the synchronous DatabaseManager methods.

Since the DatabaseManager uses synchronous pyodbc/SQLAlchemy, calling its
methods directly from async FastAPI routes blocks the event loop. This module
provides `run_sync` to safely execute synchronous DB operations in a thread pool.

Usage:
    from app.utils.async_db import run_sync
    result = await run_sync(db_manager.get_agent, user_id)
"""

import asyncio
from functools import partial
from typing import TypeVar, Callable, Any

T = TypeVar("T")


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Run a synchronous function in the default thread pool executor.

    This prevents blocking the asyncio event loop when calling synchronous
    database operations from async FastAPI routes.

    Args:
        func: The synchronous function to execute.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The return value of the synchronous function.

    Example:
        agent = await run_sync(db_manager.get_agent, "john_doe")
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
