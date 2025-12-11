#!/usr/bin/env python3
"""Quick syntax check for test files."""

import py_compile
import sys

test_files = [
    '/workspaces/fastapi-metrics/tests/test_core.py',
    '/workspaces/fastapi-metrics/tests/test_phase3.py',
    '/workspaces/fastapi-metrics/tests/test_health.py',
    '/workspaces/fastapi-metrics/tests/test_redis.py',
    '/workspaces/fastapi-metrics/tests/test_storage.py',
]

errors = False
for filepath in test_files:
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✓ {filepath}")
    except py_compile.PyCompileError as e:
        print(f"✗ {filepath}")
        print(f"  Error: {e}")
        errors = True

if errors:
    sys.exit(1)
else:
    print("\nAll test files have valid syntax!")
    sys.exit(0)
