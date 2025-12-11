#!/usr/bin/env python3
"""Check syntax of all Python files."""

import py_compile
import sys
from pathlib import Path

def check_syntax():
    """Check syntax of all Python files."""
    errors = []
    root = Path("/workspaces/fastapi-metrics")
    
    # Check source files
    for py_file in root.glob("fastapi_metrics/**/*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"✓ {py_file.relative_to(root)}")
        except py_compile.PyCompileError as e:
            print(f"✗ {py_file.relative_to(root)}")
            print(f"  {e}")
            errors.append(str(py_file))
    
    # Check test files
    print("\nTest files:")
    for py_file in root.glob("tests/*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"✓ {py_file.relative_to(root)}")
        except py_compile.PyCompileError as e:
            print(f"✗ {py_file.relative_to(root)}")
            print(f"  {e}")
            errors.append(str(py_file))
    
    if errors:
        print(f"\nFound {len(errors)} files with syntax errors")
        return False
    else:
        print(f"\n✓ All files have valid syntax!")
        return True

if __name__ == "__main__":
    success = check_syntax()
    sys.exit(0 if success else 1)
