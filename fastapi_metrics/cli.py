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


def generate_setup_code(storage_choice, retention, app_name):
    """Generate setup code based on user choices."""
    
    storage_map = {
        1: 'storage="sqlite://metrics.db"',
        2: 'storage="memory://"',
    }
    
    code = f'''# Add to your {app_name}.py file

from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI()

# Initialize metrics
metrics = Metrics(
    app,
    {storage_map[storage_choice]},
    retention_hours={retention},
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
    
    return code


def generate_query_examples():
    """Generate example API queries."""
    
    examples = '''
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
'''
    
    return examples


def main():
    """Main CLI flow."""
    print_header()
    
    print("This helper will generate setup code for FastAPI Metrics.\n")
    
    # Question 1: Storage
    storage_choice = ask_question(
        "Which storage backend do you want to use?",
        options=[
            "SQLite (recommended - persistent, single file)",
            "In-Memory (testing/dev only - data lost on restart)",
        ],
        default=1
    )
    
    # Question 2: Retention
    print()
    retention = ask_question(
        "How many hours of data should be kept?",
        default=24
    )
    try:
        retention = int(retention)
    except ValueError:
        retention = 24
    
    # Question 3: App name
    print()
    app_name = ask_question(
        "What's your main app file name?",
        default="main"
    )
    
    # Generate code
    print("\n" + "="*60)
    print("  Generated Setup Code")
    print("="*60)
    
    setup_code = generate_setup_code(storage_choice, retention, app_name)
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
    print(generate_query_examples())
    
    # Next steps
    print("\n" + "="*60)
    print("  Next Steps")
    print("="*60)
    print("""
1. Copy the generated code to your FastAPI app
2. Install the package: pip install fastapi-metrics
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
