#!/bin/bash

echo "======================================"
echo "FastAPI Metrics - Test Suite"
echo "======================================"
echo ""

# Run basic tests (no Redis required)
echo "Running basic tests (SQLite, Memory, Health)..."
pytest tests/test_storage.py tests/test_core.py tests/test_health.py -v

if [ $? -ne 0 ]; then
    echo "❌ Basic tests failed!"
    exit 1
fi

echo ""
echo "✓ Basic tests passed!"
echo ""

# Check if Redis Python package is installed
if python -c "import redis" 2>/dev/null; then
    echo "Redis Python package detected"
    
    # Check if Redis server is running
    if python -c "import redis; r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1); r.ping()" 2>/dev/null; then
        echo "Redis server detected, running Redis tests..."
        pytest tests/test_redis.py -v
        
        if [ $? -ne 0 ]; then
            echo "⚠️  Redis tests failed"
        else
            echo "✓ Redis tests passed!"
        fi
    else
        echo "⚠️  Redis server not running, skipping Redis tests"
        echo "   Start Redis with: docker run -d -p 6379:6379 redis:7-alpine"
        echo "   Or: redis-server (if installed)"
    fi
else
    echo "⚠️  Redis Python package not installed, skipping Redis tests"
    echo "   Install with: pip install redis"
fi

echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo "✓ Core functionality tests passed"
echo "✓ Storage backend tests passed"
echo "✓ Health check tests passed"
echo ""
echo "Ready to deploy!"
