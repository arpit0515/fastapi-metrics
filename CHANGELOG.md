# Changelog

## 0.4.0

### Added
- MCP server (`fastapi-metrics-mcp` console script, `pip install fastapi-metrics[mcp]`) so AI coding agents can discover and correctly use this library. Reference tools (`quickstart`, `config_reference`, `storage_backends`, `available_endpoints`) need no network access; live tools (`get_snapshot`, `query_metrics`, `endpoint_stats`, `check_health`) proxy a running app's existing JSON endpoints given a `base_url`.

### Fixed
- `tests/test_redis.py`'s connection-failure fixture could mask its own `pytest.skip()` with an unrelated `ConnectionError` raised during its `finally`-block cleanup (calling `flushdb()` on a client that never connected), making Redis tests report as errored instead of skipped when Redis isn't running. Cleanup failures are now swallowed since they're not meaningful when setup already failed or the test already ran.

## 0.3.14

### Fixed
- **Critical**: `Metrics(app, ...)` crashed with `AttributeError: 'FastAPI' object has no attribute 'add_event_handler'` on current FastAPI/Starlette, because startup/shutdown hooks were wired via an API that has since been removed. Now wired via `app.router.lifespan_context`, which works across FastAPI/Starlette versions and composes with any lifespan the host app already defines.
- `fastapi-metrics-setup` (`cli.py`) contained an f-string with nested same-quote-character f-strings, which is a `SyntaxError` on Python < 3.12 — the CLI could not even be imported on those versions. Simplified to avoid nested f-strings.

### Changed
- `aioboto3`, `asyncpg`, `rich`, and `uvicorn` are no longer installed by default. They're now optional extras: `pip install fastapi-metrics[redis|postgres|dynamodb|alerts|cli|all]`. Core install only requires `fastapi`, `pydantic`, `aiosqlite`, `psutil`.
- `redis` is now declared as an optional dependency (`fastapi-metrics[redis]`) — it was previously required by `storage/redis.py` at runtime but not declared anywhere.
- Replaced the internal project-spec `README.md` with real user-facing documentation (previously only visible in the un-rendered `README_mvp.md`); the old spec moved to `docs/ROADMAP.md`.
- Added a CI workflow (`.github/workflows/ci.yml`) running lint + tests across Python 3.8–3.13 and against both the minimum and latest supported FastAPI versions.

## Earlier versions

Not tracked in this file. See git history.
