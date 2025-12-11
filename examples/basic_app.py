"""
Basic FastAPI app with metrics enabled.
Run with: uvicorn basic_app:app --reload
"""

import asyncio
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI(title="My API")

# Initialize metrics - that's it!
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",  # or "memory://" for testing
    retention_hours=24,
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hello World"}


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Simulate some work"""
    await asyncio.sleep(0.1)
    return {"user_id": user_id, "name": "John Doe"}


@app.post("/payment")
async def process_payment(amount: float, user_id: int):
    """Process a payment."""
    await metrics.track("revenue", amount, user_id=user_id)
    await metrics.track("payment_count", 1)

    return {"status": "success", "amount": amount}


@app.post("/signup")
async def signup(email: str, plan: str = "free"):
    """Track signups"""
    await metrics.track("signups", 1, plan=plan)

    return {"status": "created", "email": email}


# Metrics are automatically available at:
# GET /metrics - Current snapshot
# GET /metrics/query - Query time-series data
# GET /metrics/endpoints - Per-endpoint statistics
# POST /metrics/cleanup - Manual cleanup

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
