#!/usr/bin/env python3
"""
FastAPI Metrics Setup Helper CLI
"""

import sys


def print_header():
    print("\n" + "="*60)
    print("  FastAPI Metrics - Setup Helper")
    print("="*60 + "\n")


def ask_question(question, options=None, default=None):
    """Ask a question and return the answer."""
    if options:
        print(f"{question}")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        if default:
            prompt = f"Choice (default: {default}): "
        else:
            prompt = "Choice: "
        
        while True:
            answer = input(prompt).strip()
            if not answer and default:
                return default
            try:
                choice = int(answer)
                if 1 <= choice <= len(options):
                    return choice
            except ValueError:
                pass
            print("Invalid choice. Try again.")
    else:
        if default:
            prompt = f"{question} (default: {default}): "
        else:
            prompt = f"{question}: "
        answer = input(prompt).strip()
        return answer if answer else default


def generate_setup_code(storage_choice, retention, app_name, enable_health):
    """Generate setup code based on user choices."""
    
    storage_map = {
        1: 'storage="sqlite://metrics.db"',
        2: 'storage="memory://"',
        3: 'storage=os.getenv("REDIS_URL", "redis://localhost:6379/0")',
    }
    
    imports = "from fastapi import FastAPI\nfrom fastapi_metrics import Metrics"
    if storage_choice == 3:
        imports += "\nimport os"
    
    health_param = f",\n    enable_health_checks={str(enable_health)}" if enable_health else ""
    
    code = f'''# Add to your {app_name}.py file

{imports}

app = FastAPI()

# Initialize metrics
metrics = Metrics(
    app,
    {storage_map[storage_choice]},
    retention_hours={retention}{health_param},
)

# Track custom metrics in your endpoints
@app.post("/payment")
async def payment(amount: float, user_id: int):
    # Your payment logic...
    
    # Track metrics
    await metrics.track("revenue", amount, user_id=user_id)
    await metrics.track("payment_count", 1)
    
    return {{"status": "success"}}
'''
    
    if enable_health:
        code += '''
# Health check endpoints (Kubernetes):
# GET /health - Overall health status
# GET /health/live - Liveness probe
# GET /health/ready - Readiness probe (checks disk, memory, database)
'''
    
    return code


def generate_query_examples(storage_choice, enable_health):
    """Generate example API queries."""
    
    install_note = ""
    if storage_choice == 3:
        install_note = '''
# Install with Redis support:
   pip install fastapi-metrics[redis]
'''
    
    health_examples = ""
    if enable_health:
        health_examples = '''
   # Health checks (Kubernetes)
   curl http://localhost:8000/health
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
'''
    
    examples = f'''{install_note}
# Testing Your Metrics

1. Start your app:
   uvicorn your_app:app --reload

2. Make some test requests:
   curl http://localhost:8000/your-endpoint

3. View metrics:
   
   # Current snapshot
   curl http://localhost:8000/metrics
   
   # HTTP metrics (last 24 hours)
   curl "http://localhost:8000/metrics/query?metric_type=http&from_hours=24"
   
   # Custom metrics (e.g., revenue)
   curl "http://localhost:8000/metrics/query?metric_type=custom&name=revenue&from_hours=24"
   
   # Per-endpoint statistics
   curl http://localhost:8000/metrics/endpoints
   
   # Grouped by hour
   curl "http://localhost:8000/metrics/query?metric_type=http&group_by=hour&from_hours=12"
{health_examples}'''
    
    return examples


def main():
    """Main CLI flow."""
    print_header()
    
    print("This helper will generate setup code for FastAPI Metrics.\n")
    
    # Question 1: Deployment type
    deployment_type = ask_question(
        "What type of deployment?",
        options=[
            "Single server (VPS, EC2) - Use SQLite",
            "Development/Testing - Use in-memory storage",
            "Kubernetes/Multi-instance - Use Redis",
        ],
        default=1
    )
    
    # Question 2: Health checks
    print()
    if deployment_type == 3:
        enable_health = True
        print("✓ Kubernetes health checks will be enabled automatically\n")
    else:
        health_input = ask_question(
            "Enable Kubernetes health checks? (y/n)",
            default="n"
        )
        enable_health = health_input.lower() in ['y', 'yes']
    
    # Question 3: Retention
    print()
    retention = ask_question(
        "How many hours of data should be kept?",
        default=24
    )
    try:
        retention = int(retention)
    except ValueError:
        retention = 24
    
    # Question 4: App name
    print()
    app_name = ask_question(
        "What's your main app file name?",
        default="main"
    )
    
    # Generate code
    print("\n" + "="*60)
    print("  Generated Setup Code")
    print("="*60)
    
    setup_code = generate_setup_code(deployment_type, retention, app_name, enable_health)
    print(setup_code)
    
    # Save to file option
    print("\n" + "="*60)
    save = ask_question("Save this to a file? (y/n)", default="n")
    
    if save.lower() in ['y', 'yes']:
        filename = ask_question("Filename", default="metrics_setup.py")
        with open(filename, 'w') as f:
            f.write(setup_code)
        print(f"\n✓ Saved to {filename}")
    
    # Show usage examples
    print("\n" + "="*60)
    print("  Usage Examples")
    print("="*60)
    print(generate_query_examples(deployment_type, enable_health))
    
    # Kubernetes-specific notes
    if deployment_type == 3:
        print("\n" + "="*60)
        print("  Kubernetes Deployment")
        print("="*60)
        print("""
1. Ensure Redis is deployed in your cluster
2. Set REDIS_URL environment variable in your deployment
3. Configure liveness probe: /health/live
4. Configure readiness probe: /health/ready

Example deployment available in:
examples/kubernetes/deployment.yaml
""")
    
    # Next steps
    print("\n" + "="*60)
    print("  Next Steps")
    print("="*60)
    
    install_cmd = "pip install fastapi-metrics"
    if deployment_type == 3:
        install_cmd += "[redis]"
    
    print(f"""
1. Copy the generated code to your FastAPI app
2. Install the package: {install_cmd}
3. Start your app and test the endpoints
4. Check out USAGE_GUIDE.md for more examples
5. View metrics at: http://localhost:8000/metrics

For detailed documentation, visit:
https://github.com/arpit0515/fastapi-metrics
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
