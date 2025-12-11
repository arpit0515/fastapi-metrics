"""
FastAPI app with Redis storage and Kubernetes health checks.
Suitable for multi-instance deployments.
"""

import os
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI(title="My Scalable API")

# Get Redis URL from environment (set in K8s deployment)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize metrics with Redis and health checks
metrics = Metrics(
    app,
    storage=redis_url,
    retention_hours=72,
    enable_health_checks=True,  # Enables /health, /health/live, /health/ready
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Scalable API"}


@app.post("/api/payment")
async def payment(amount: float, user_id: int, plan: str):
    """Example endpoint to track payments."""
    await metrics.track("revenue", amount, user_id=user_id, plan=plan)
    await metrics.track("payment_count", 1, plan=plan)

    return {"status": "success"}


# Health endpoints automatically available:
# GET /health - Overall health
# GET /health/live - Liveness probe (for K8s)
# GET /health/ready - Readiness probe (for K8s)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
