"""
Advanced features demo - LLM costs, system metrics, alerts, Prometheus export
"""

import os
from fastapi import FastAPI
from fastapi_metrics import Metrics
from fastapi_metrics.alerting import Alert

app = FastAPI(title="Advanced Metrics Demo")

# Initialize with all Phase 3 features
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",
    retention_hours=72,
    enable_health_checks=True,
    enable_system_metrics=True,  # CPU, Memory, Disk tracking
    alert_webhook_url="https://hooks.slack.com/your-webhook",  # Optional
)

# Configure alerts
if metrics.alert_manager:
    # Alert if error rate > 5%
    metrics.alert_manager.add_alert(
        Alert(
            name="high_error_rate",
            metric_name="error_rate",
            threshold=0.05,
            comparison=">",
            window_minutes=5,
        )
    )

    # Alert if LLM costs > $10 in 1 hour
    metrics.alert_manager.add_alert(
        Alert(
            name="high_llm_costs",
            metric_name="llm_cost",
            threshold=10.0,
            comparison=">",
            window_minutes=60,
        )
    )


@app.get("/")
async def root():
    return {"message": "Advanced Metrics Demo"}


@app.post("/api/chat")
async def chat(prompt: str):
    """Example: Track LLM API usage."""

    # Your OpenAI call here...
    # response = openai.chat.completions.create(...)

    # Track costs
    await metrics.llm_costs.track_openai_call(
        model="gpt-4o",
        input_tokens=100,
        output_tokens=200,
        user_id=123,
        endpoint="/api/chat",
    )

    return {"response": "AI response here"}


@app.post("/api/claude")
async def claude_chat(prompt: str):
    """Example: Track Anthropic API usage."""

    # Your Anthropic call here...
    # response = anthropic.messages.create(...)

    # Track costs
    await metrics.llm_costs.track_anthropic_call(
        model="claude-3-5-sonnet-20241022",
        input_tokens=150,
        output_tokens=300,
        user_id=456,
        endpoint="/api/claude",
    )

    return {"response": "Claude response here"}


@app.get("/api/collect-system-metrics")
async def collect_system():
    """Manually trigger system metrics collection."""
    if metrics.system_metrics:
        await metrics.system_metrics.collect_and_track()
        return {"status": "collected"}
    return {"error": "System metrics not enabled"}


# Available Phase 3 endpoints:
# GET /metrics/costs?hours=24 - LLM cost breakdown
# GET /metrics/export/prometheus?hours=1 - Prometheus format
# GET /metrics/system - Current system resources
# GET /health, /health/live, /health/ready - Health checks

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
