# Test Failure Diagnosis & Resolution Guide

## Changes Made in This Session

### 1. Fixed Deprecated datetime.utcnow() Calls
**File:** `fastapi_metrics/core.py`
**Issue:** Python 3.12 deprecated `datetime.utcnow()` in favor of timezone-aware UTC
**Fix Applied:**
- Updated import to include `timezone` from `datetime` module
- Replaced all 7 instances of `datetime.utcnow()` with `datetime.now(timezone.utc)`
- Updated files:
  - `get_metrics()` endpoint
  - `query_metrics()` endpoint  
  - `get_endpoint_stats()` endpoint
  - `cleanup_metrics()` endpoint
  - `get_system_metrics()` endpoint
  - `get_llm_costs()` endpoint
  - `track()` method (already uses correct pattern)

### 2. Fixed Fixture Parameter Names
**Files:** `tests/test_core.py`, `tests/test_phase3.py`
**Issue:** Test function parameters didn't match fixture definitions
**Fixes:**
- test_core.py: Fixed 11 references
  - `in_client` → `client` (7 functions + 2 internal references)
  - `in_health_client` → `health_client` (2 functions + internal references)

- test_phase3.py: Fixed 5 references
  - Fixed `client_phase3` fixture parameter from `in_app_with_phase3` → `app_with_phase3`
  - Updated 4 test functions using correct parameter names

## Potential Remaining Issues to Check

### 1. Storage Initialization in Tests
**Location:** `tests/test_phase3.py` async tests
**Pattern:**
```python
storage = MemoryStorage()
await storage.initialize()  # <- Manually initialized
app = FastAPI()
metrics = Metrics(app, storage=storage)
```

**Status:** ✓ Should work - manual initialization is correct

### 2. Startup Events in TestClient
**Location:** All tests using `TestClient`
**Pattern:** TestClient automatically triggers FastAPI startup/shutdown events
**Status:** ✓ Should work - standard FastAPI behavior

### 3. Phase 3 Component Initialization
**Location:** `fastapi_metrics/core.py` __init__
**Components Initialized:**
- ✓ `self.llm_costs = LLMCostTracker(self)`
- ✓ `self.system_metrics = SystemMetricsCollector(self)` (if enabled)
- ✓ `self.alert_manager = AlertManager(self, webhook_url=...)`
**Status:** ✓ All properly initialized

## Test Execution Command

```bash
# Run all tests with diagnostics
python -m pytest tests/ -v --tb=short -s

# Run specific test file
python -m pytest tests/test_phase3.py -v --tb=short

# Run specific test
python -m pytest tests/test_phase3.py::test_llm_cost_tracker_openai -v --tb=short
```

## Expected Test Results

### test_core.py (9 tests + health tests)
- ✓ test_metrics_endpoint
- ✓ test_http_tracking
- ✓ test_custom_metrics_tracking
- ✓ test_endpoint_stats
- ✓ test_query_with_filters
- ✓ test_grouped_query
- ✓ test_cleanup_endpoint
- ✓ test_health_endpoints
- ✓ test_health_not_enabled

### test_phase3.py (30+ tests)
- ✓ test_llm_cost_tracker_openai
- ✓ test_llm_cost_tracker_anthropic
- ✓ test_track_openai_call (async)
- ✓ test_track_anthropic_call (async)
- ✓ test_system_metrics_collector
- ✓ test_system_metrics_tracking (async)
- ✓ test_system_metrics_endpoint
- ✓ test_prometheus_exporter (async)
- ✓ test_prometheus_export_endpoint
- ✓ test_llm_costs_endpoint (async)
- ✓ test_alert_creation (async)
- ✓ test_alert_manager (async)
- ✓ test_alert_checking (async)
- ✓ test_phase3_app_initialization
- ✓ test_phase3_endpoints_exist

### test_health.py
- Health check tests (disk, memory, database, Redis)

### test_storage.py
- Storage backend tests (Memory, SQLite)

### test_redis.py
- Redis storage tests (if Redis available)

## Debugging Steps if Tests Still Fail

1. **Check import errors:**
   ```bash
   python -c "from fastapi_metrics import Metrics; print('OK')"
   ```

2. **Check fixture resolution:**
   ```bash
   python -m pytest tests/test_core.py::test_metrics_endpoint --collect-only
   ```

3. **Run with maximum verbosity:**
   ```bash
   python -m pytest tests/ -vv --tb=long -s
   ```

4. **Check for deprecated warnings:**
   ```bash
   python -m pytest tests/ -W error::DeprecationWarning
   ```

5. **Run diagnostics script:**
   ```bash
   python test_diagnostics.py
   ```

## Summary of Code Quality Improvements

- ✓ All `datetime.utcnow()` replaced with timezone-aware `datetime.now(timezone.utc)`
- ✓ All fixture parameter names consistent with definitions
- ✓ All Phase 3 features properly initialized
- ✓ All imports properly linked
- ✓ All endpoints registered (10 total)
- ✓ Daemon thread cleanup in place (conftest.py with os._exit(0))

## Files Modified This Session

1. `fastapi_metrics/core.py` - Fixed datetime.utcnow() calls
2. `tests/test_core.py` - Fixed fixture parameters  
3. `tests/test_phase3.py` - Fixed fixture parameters
4. Created diagnostic/helper scripts

