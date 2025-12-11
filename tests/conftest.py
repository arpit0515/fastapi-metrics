import pytest
import asyncio
import sys
import threading
import atexit
import os


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests with proper cleanup."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Properly close all pending tasks before closing loop
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        # Give tasks time to be cancelled
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    
    # Shutdown the default executor
    try:
        executor = loop._default_executor
        if executor:
            executor.shutdown(wait=False)
    except Exception:
        pass
    
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_all(request):
    """Comprehensive cleanup after all tests."""
    yield
    
    # Give threads a moment to shut down gracefully
    import time
    time.sleep(0.2)
    
    # Close any remaining event loops
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.close()
    except Exception:
        pass
    
    # Force exit to kill daemon threads (httpx, etc)
    # This is necessary because some libraries create daemon threads
    # that don't shut down cleanly and cause pytest to hang
    os._exit(0)

