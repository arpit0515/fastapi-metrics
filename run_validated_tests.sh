#!/bin/bash
# Quick test validation script
# Run this after applying all fixes to verify tests pass

echo "================================"
echo "FastAPI Metrics - Test Validation"
echo "================================"
echo ""

# Check if pytest is available
if ! python -m pytest --version > /dev/null 2>&1; then
    echo "❌ pytest not found. Install with: pip install pytest pytest-asyncio httpx"
    exit 1
fi

echo "✓ pytest is available"
echo ""

# Run validation script
echo "Running fix validation..."
python validate_fixes.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Fix validation failed. Check the issues above."
    exit 1
fi

echo ""
echo "================================"
echo "Running Test Suite"
echo "================================"
echo ""

# Run tests with clear output
python -m pytest tests/ -v --tb=short 2>&1 | tee test_run_output.txt

# Check results
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ ALL TESTS PASSED!"
    echo ""
    echo "Next steps:"
    echo "  • Review test_run_output.txt for details"
    echo "  • Run with coverage: python -m pytest tests/ --cov=fastapi_metrics"
    echo "  • Deploy with confidence!"
else
    echo ""
    echo "❌ Some tests failed. Review output above."
    exit 1
fi
