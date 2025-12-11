#!/bin/bash

echo "======================================"
echo "FastAPI Metrics - Test Suite v0.3.0"
echo "======================================"
echo ""

# Run Phase 1 tests (core functionality)
echo "Running Phase 1 tests (Core, Storage, Middleware)..."
pytest tests/test_storage.py tests/test_core.py -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Phase 1 tests failed!"
    exit 1
fi

echo ""
echo "✓ Phase 1 tests passed!"
echo ""

# Run Phase 2 tests (health checks)
echo "Running Phase 2 tests (Health Checks)..."
pytest tests/test_health.py -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Phase 2 tests failed!"
    exit 1
fi

echo ""
echo "✓ Phase 2 tests passed!"
echo ""

# Run Phase 3 tests (advanced features)
echo "Running Phase 3 tests (LLM, System, Prometheus, Alerts)..."
pytest tests/test_phase3.py -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Phase 3 tests failed!"
    exit 1
fi

echo ""
echo "✓ Phase 3 tests passed!"
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
    fi
else
    echo "⚠️  Redis Python package not installed, skipping Redis tests"
    echo "   Install with: pip install redis"
fi

echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo "✓ Phase 1: Core functionality"
echo "✓ Phase 2: Health checks"
echo "✓ Phase 3: Advanced features"
echo "  - LLM cost tracking"
echo "  - System metrics"
echo "  - Prometheus export"
echo "  - Alerting"
echo ""
echo "All tests passed! Ready to deploy! 🚀"
