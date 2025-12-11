#!/bin/bash
set -e

echo "Running fastapi-metrics test suite..."
echo "======================================="

# Run pytest with verbose output
python -m pytest tests/ -v --tb=short 2>&1

echo ""
echo "Test suite completed successfully!"
