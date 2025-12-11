#!/usr/bin/env python3
"""Final validation before running full test suite."""

import sys
from pathlib import Path

def validate():
    """Run validation checks."""
    print("=" * 70)
    print("FINAL VALIDATION CHECK")
    print("=" * 70)
    
    issues = []
    
    # Check 1: core.py has no utcnow()
    print("\n[1] Checking for deprecated utcnow() calls...")
    core_py = Path("/workspaces/fastapi-metrics/fastapi_metrics/core.py").read_text()
    if "utcnow()" in core_py:
        print("  ✗ Found utcnow() in core.py")
        issues.append("Deprecated utcnow() still in core.py")
    else:
        print("  ✓ No deprecated utcnow() found")
    
    # Check 2: middleware.py doesn't double-decrement
    print("\n[2] Checking middleware for double-decrement bug...")
    middleware_py = Path("/workspaces/fastapi-metrics/fastapi_metrics/middleware.py").read_text()
    lines = middleware_py.split('\n')
    active_requests_decrements = 0
    in_try_block = False
    in_except_block = False
    for i, line in enumerate(lines):
        if "try:" in line:
            in_try_block = True
        if "except" in line:
            in_except_block = True
        if "_active_requests -= 1" in line:
            active_requests_decrements += 1
            print(f"  Found decrement at line {i+1}")
    
    if active_requests_decrements > 1:
        # Count decrements in finally
        finally_section = middleware_py[middleware_py.find("finally:"):]
        decrements_in_finally = finally_section.count("_active_requests -= 1")
        if decrements_in_finally == 1:
            print("  ✓ Only 1 decrement in finally block (correct)")
        else:
            print(f"  ✗ Found {decrements_in_finally} decrements in finally")
            issues.append("Middleware has multiple active_requests decrements")
    else:
        print("  ✓ Only 1 decrement of active_requests")
    
    # Check 3: test_core.py fixture parameters
    print("\n[3] Checking test_core.py fixture parameters...")
    test_core = Path("/workspaces/fastapi-metrics/tests/test_core.py").read_text()
    
    bad_params = []
    for line_no, line in enumerate(test_core.split('\n'), 1):
        if "def test_" in line:
            if "in_client" in line or "in_health_client" in line:
                bad_params.append((line_no, line.strip()))
    
    if bad_params:
        print(f"  ✗ Found {len(bad_params)} functions with old parameter names:")
        for line_no, content in bad_params:
            print(f"    Line {line_no}: {content}")
        issues.append("test_core.py has old fixture parameter names")
    else:
        print("  ✓ All test_core.py parameters are correct")
    
    # Check 4: test_phase3.py fixture parameters
    print("\n[4] Checking test_phase3.py fixture parameters...")
    test_phase3 = Path("/workspaces/fastapi-metrics/tests/test_phase3.py").read_text()
    
    bad_params = []
    for line_no, line in enumerate(test_phase3.split('\n'), 1):
        if "def test_" in line:
            if "in_client_phase3" in line or "in_app_with_phase3" in line:
                bad_params.append((line_no, line.strip()))
        if "in_app_with_phase3" in line and "@pytest.fixture" not in line:
            if "in_app_with_phase3" not in ["def client_phase3(app_with_phase3)"]:
                if line.strip() and not line.strip().startswith("#"):
                    bad_params.append((line_no, line.strip()))
    
    if bad_params:
        print(f"  ✗ Found {len(bad_params)} issues with old parameter names")
        for line_no, content in bad_params:
            print(f"    Line {line_no}: {content}")
        issues.append("test_phase3.py has old fixture parameter names")
    else:
        print("  ✓ All test_phase3.py parameters are correct")
    
    # Check 5: Verify key endpoints exist
    print("\n[5] Checking registered endpoints...")
    endpoints_in_code = [
        "'/metrics'",
        "'/metrics/query'",
        "'/metrics/endpoints'",
        "'/metrics/cleanup'",
        "'/health'",
        "'/health/live'",
        "'/health/ready'",
        "'/metrics/system'",
        "'/metrics/costs'",
        "'/metrics/export/prometheus'",
    ]
    
    missing_endpoints = []
    for endpoint in endpoints_in_code:
        if endpoint not in core_py:
            missing_endpoints.append(endpoint)
    
    if missing_endpoints:
        print(f"  ✗ Missing endpoints: {missing_endpoints}")
        issues.append(f"Missing {len(missing_endpoints)} endpoints")
    else:
        print(f"  ✓ All 10 endpoints are registered")
    
    # Summary
    print("\n" + "=" * 70)
    if issues:
        print(f"VALIDATION FAILED - {len(issues)} issue(s) found:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("✅ VALIDATION PASSED - Ready to run tests!")
        print("\nRun tests with:")
        print("  python -m pytest tests/ -v --tb=short")
        return True

if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
