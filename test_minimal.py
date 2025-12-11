#!/usr/bin/env python3
"""Minimal test to identify fixture and initialization issues."""

import asyncio
import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_metrics import Metrics
from fastapi_metrics.storage.memory import MemoryStorage


def test_basic_fixture():
    """Test that basic fixture works."""
    app = FastAPI()
    metrics = Metrics(app, storage="memory://")
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    client = TestClient(app)
    response = client.get("/metrics")
    print(f"Status: {response.status_code}")
    print(f"Data: {response.json()}")
    assert response.status_code == 200


async def test_llm_tracker_async():
    """Test LLM tracker directly."""
    storage = MemoryStorage()
    await storage.initialize()
    
    app = FastAPI()
    metrics = Metrics(app, storage=storage)
    
    # Test direct cost calculation
    cost = metrics.llm_costs.calculate_openai_cost("gpt-4o", 1000, 2000)
    print(f"Cost: {cost}")
    assert cost > 0
    
    # Test tracking
    await metrics.llm_costs.track_openai_call(
        model="gpt-4o",
        input_tokens=100,
        output_tokens=200,
    )
    
    # Query metrics
    now = datetime.datetime.now(datetime.timezone.utc)
    costs = await storage.query_custom_metrics(
        from_time=now - datetime.timedelta(minutes=1),
        to_time=now + datetime.timedelta(minutes=1),
        name="llm_cost",
    )
    
    print(f"Tracked costs: {costs}")
    assert len(costs) >= 1


if __name__ == "__main__":
    print("Running basic fixture test...")
    test_basic_fixture()
    print("✓ Basic fixture test passed")
    
    print("\nRunning async LLM tracker test...")
    asyncio.run(test_llm_tracker_async())
    print("✓ Async LLM tracker test passed")
    
    print("\nAll tests passed!")
