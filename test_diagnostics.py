#!/usr/bin/env python3
"""Comprehensive test diagnostics."""

import subprocess
import sys
import json

def run_tests():
    """Run tests and collect diagnostics."""
    print("=" * 70)
    print("FASTAPI-METRICS TEST DIAGNOSTICS")
    print("=" * 70)
    
    # Test 1: Check Python version
    print("\n[1/5] Python Version:")
    result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
    print(f"  {result.stdout.strip()}")
    
    # Test 2: Check imports
    print("\n[2/5] Checking imports...")
    try:
        from fastapi_metrics import Metrics, Alert
        from fastapi_metrics.storage.memory import MemoryStorage
        from fastapi_metrics.collectors.llm_costs import LLMCostTracker
        from fastapi_metrics.collectors.system import SystemMetricsCollector
        from fastapi_metrics.exporters.prometheus import PrometheusExporter
        from fastapi_metrics.alerting import AlertManager
        print("  ✓ All Phase 1-3 imports successful")
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False
    
    # Test 3: Check fixture setup
    print("\n[3/5] Checking fixture setup...")
    try:
        from fastapi import FastAPI
        from fastapi_metrics import Metrics
        
        app = FastAPI()
        metrics = Metrics(app, storage="memory://")
        print("  ✓ Basic fixture creation successful")
    except Exception as e:
        print(f"  ✗ Fixture setup failed: {e}")
        return False
    
    # Test 4: Run minimal pytest
    print("\n[4/5] Running pytest syntax check...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "tests/"],
        cwd="/workspaces/fastapi-metrics",
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # Count tests
    if "collected" in result.stdout:
        lines = result.stdout.split('\n')
        for line in lines:
            if "collected" in line:
                print(f"  {line.strip()}")
    else:
        print("  Warning: Could not determine test count")
    
    if result.returncode != 0:
        print(f"  ✗ Test collection failed")
        print(f"    Error: {result.stderr[:500]}")
    else:
        print("  ✓ Test collection successful")
    
    # Test 5: Run one simple test
    print("\n[5/5] Running sample test...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", 
         "tests/test_phase3.py::test_llm_cost_tracker_openai", 
         "-v", "--tb=short"],
        cwd="/workspaces/fastapi-metrics",
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if "PASSED" in result.stdout:
        print("  ✓ Sample test passed")
    elif "FAILED" in result.stdout:
        print("  ✗ Sample test failed")
        # Extract failure reason
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            if "FAILED" in line or "AssertionError" in line:
                print(f"    {line.strip()}")
    else:
        print("  ? Test status unclear")
        if result.stderr:
            print(f"    Error: {result.stderr[:300]}")
    
    print("\n" + "=" * 70)
    return True

if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
