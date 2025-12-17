#!/usr/bin/env python3
"""
FastAPI Metrics CLI - Query and manage metrics from command line
"""

import sys
import json
import argparse
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


async def get_storage(db_path: str):
    """Initialize storage backend from db path."""
    if db_path.startswith("redis://"):
        from fastapi_metrics.storage.redis import RedisStorage

        storage = RedisStorage(db_path)
    elif db_path.startswith("sqlite://") or db_path.endswith(".db"):
        from fastapi_metrics.storage.sqlite import SQLiteStorage

        path = db_path.replace("sqlite://", "")
        storage = SQLiteStorage(path)
    else:
        from fastapi_metrics.storage.sqlite import SQLiteStorage

        storage = SQLiteStorage(db_path)

    await storage.initialize()
    return storage


def format_number(num: float) -> str:
    """Format number with commas."""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return f"{num:,.0f}"


async def cmd_show(args):
    """Show current metrics snapshot."""
    storage = await get_storage(args.db)

    try:
        # Get last 24h of data
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=24)

        http_data = await storage.query_http_metrics(from_time=from_time, to_time=to_time)

        # Calculate stats
        total = len(http_data)
        errors = sum(1 for r in http_data if r.get("status_code", 0) >= 400)
        latencies = [r.get("latency_ms", 0) for r in http_data]

        def percentile(data, p):
            if not data:
                return 0
            s = sorted(data)
            idx = int(len(s) * p / 100)
            return s[min(idx, len(s) - 1)]

        if args.json:
            result = {
                "total_requests": total,
                "error_rate": round(errors / total, 3) if total > 0 else 0,
                "p95_latency_ms": round(percentile(latencies, 95), 2),
                "active_requests": 0,
            }
            print(json.dumps(result, indent=2))
        else:
            table = Table(title="FastAPI Metrics", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Requests", format_number(total))
            table.add_row("Error Rate", f"{(errors/total*100):.1f}%" if total > 0 else "0%")
            table.add_row("P50 Latency", f"{percentile(latencies, 50):.1f}ms")
            table.add_row("P95 Latency", f"{percentile(latencies, 95):.1f}ms")
            table.add_row("P99 Latency", f"{percentile(latencies, 99):.1f}ms")

            console.print(table)
    finally:
        await storage.close()


async def cmd_query(args):
    """Query specific metrics."""
    storage = await get_storage(args.db)

    try:
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=args.from_hours)

        if args.metric_type == "http":
            results = await storage.query_http_metrics(
                from_time=from_time,
                to_time=to_time,
                endpoint=args.endpoint,
                method=args.method,
            )
        else:
            results = await storage.query_custom_metrics(
                from_time=from_time,
                to_time=to_time,
                name=args.name,
            )

        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            if args.metric_type == "custom" and args.group_by:
                # Group by label
                grouped = {}
                for r in results:
                    key = r.get("labels", {}).get(args.group_by, "unknown")
                    if key not in grouped:
                        grouped[key] = {"count": 0, "sum": 0}
                    grouped[key]["count"] += 1
                    grouped[key]["sum"] += r.get("value", 0)

                table = Table(title=f"Metric: {args.name}", box=box.ROUNDED)
                table.add_column(args.group_by.capitalize(), style="cyan")
                table.add_column("Total", style="green", justify="right")
                table.add_column("Count", style="yellow", justify="right")

                for key, data in sorted(grouped.items(), key=lambda x: x[1]["sum"], reverse=True):
                    table.add_row(str(key), f"${data['sum']:,.2f}", str(data["count"]))

                console.print(table)
            else:
                console.print(f"[green]Found {len(results)} records[/green]")
                if results:
                    console.print_json(json.dumps(results[:10], indent=2, default=str))
    finally:
        await storage.close()


async def cmd_costs(args):
    """Show LLM costs breakdown."""
    storage = await get_storage(args.db)

    try:
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=args.from_hours)

        costs = await storage.query_custom_metrics(
            from_time=from_time,
            to_time=to_time,
            name="llm_cost",
        )

        # Aggregate by provider
        by_provider = {}
        for cost in costs:
            provider = cost.get("labels", {}).get("provider", "unknown")
            if provider not in by_provider:
                by_provider[provider] = 0
            by_provider[provider] += cost.get("value", 0)

        total_cost = sum(by_provider.values())
        monthly_estimate = total_cost * (720 / args.from_hours)

        if args.json:
            result = {
                "total_cost": round(total_cost, 2),
                "by_provider": {k: round(v, 2) for k, v in by_provider.items()},
                "monthly_estimate": round(monthly_estimate, 2),
            }
            print(json.dumps(result, indent=2))
        else:
            table = Table(title="LLM Costs", box=box.ROUNDED)
            table.add_column("Provider", style="cyan")
            table.add_column("Cost", style="green", justify="right")
            table.add_column("Monthly Est.", style="yellow", justify="right")

            for provider, cost in sorted(by_provider.items(), key=lambda x: x[1], reverse=True):
                est = cost * (720 / args.from_hours)
                table.add_row(provider.capitalize(), f"${cost:.2f}", f"${est:.2f}")

            table.add_row(
                "[bold]Total[/bold]",
                f"[bold]${total_cost:.2f}[/bold]",
                f"[bold]${monthly_estimate:.2f}[/bold]",
            )

            console.print(table)
    finally:
        await storage.close()


async def cmd_export(args):
    """Export metrics to file."""
    storage = await get_storage(args.db)

    try:
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=args.from_hours)

        http_data = await storage.query_http_metrics(from_time=from_time, to_time=to_time)

        if args.format == "csv":
            import csv

            with open(args.output, "w", newline="") as f:
                if http_data:
                    writer = csv.DictWriter(f, fieldnames=http_data[0].keys())
                    writer.writeheader()
                    writer.writerows(http_data)
            console.print(f"[green]✓ Exported {len(http_data)} records to {args.output}[/green]")

        elif args.format == "json":
            with open(args.output, "w") as f:
                json.dump(http_data, f, indent=2, default=str)
            console.print(f"[green]✓ Exported {len(http_data)} records to {args.output}[/green]")
    finally:
        await storage.close()


async def cmd_endpoints(args):
    """Show endpoint statistics."""
    storage = await get_storage(args.db)

    try:
        stats = await storage.get_endpoint_stats()

        # Flatten and sort
        rows = []
        for endpoint, methods in stats.items():
            for method, data in methods.items():
                rows.append(
                    {
                        "endpoint": endpoint,
                        "method": method,
                        "count": data.get("count", 0),
                        "p99": data.get("p99_latency_ms", 0),
                    }
                )

        rows.sort(key=lambda x: x[args.sort_by], reverse=True)

        if args.json:
            print(json.dumps(rows[: args.top], indent=2))
        else:
            table = Table(title=f"Top {args.top} Endpoints", box=box.ROUNDED)
            table.add_column("Endpoint", style="cyan")
            table.add_column("Method", style="blue")
            table.add_column("Count", style="green", justify="right")
            table.add_column("P99 (ms)", style="yellow", justify="right")

            for row in rows[: args.top]:
                table.add_row(
                    row["endpoint"],
                    row["method"],
                    format_number(row["count"]),
                    f"{row['p99']:.1f}",
                )

            console.print(table)
    finally:
        await storage.close()

async def cmd_errors(args):
    """Show error logs."""
    storage = await get_storage(args.db)

    try:
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=args.from_hours)

        errors = await storage.query_errors(
            from_time=from_time,
            to_time=to_time,
            endpoint=args.endpoint
        )

        if args.json:
            print(json.dumps(errors, indent=2, default=str))
        else:
            table = Table(title=f"Errors (Last {args.from_hours}h)", box=box.ROUNDED)
            table.add_column("Time", style="cyan")
            table.add_column("Endpoint", style="blue")
            table.add_column("Error", style="red")
            table.add_column("Count", style="yellow", justify="right")

            for error in errors[:args.limit]:
                timestamp = error.get("last_seen", error.get("timestamp", ""))
                endpoint = error.get("endpoint", "")
                error_type = error.get("error_type", "")
                error_msg = error.get("error_message", "")
                count = error.get("count", 1)
                
                # Truncate long messages
                display_error = f"{error_type}: {error_msg[:50]}..." if len(error_msg) > 50 else f"{error_type}: {error_msg}"
                
                table.add_row(
                    str(timestamp)[:19],
                    endpoint,
                    display_error,
                    str(count)
                )

            console.print(table)
            
            if errors and args.detail:
                console.print("\n[bold]Detailed view of most recent error:[/bold]")
                latest = errors[0]
                console.print(f"[cyan]Endpoint:[/cyan] {latest.get('method')} {latest.get('endpoint')}")
                console.print(f"[cyan]Error:[/cyan] {latest.get('error_type')}")
                console.print(f"[cyan]Message:[/cyan] {latest.get('error_message')}")
                console.print(f"[cyan]Count:[/cyan] {latest.get('count')}")
                if latest.get('stack_trace'):
                    console.print(f"\n[cyan]Stack Trace:[/cyan]\n{latest.get('stack_trace')}")
    finally:
        await storage.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fastapi-metrics",
        description="FastAPI Metrics CLI - Query and manage metrics",
    )

    parser.add_argument("-v", "--version", action="version", version="0.3.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show current metrics snapshot")
    show_parser.add_argument("--db", default="metrics.db", help="Database path")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query specific metrics")
    query_parser.add_argument("--db", default="metrics.db", help="Database path")
    query_parser.add_argument("--metric-type", default="http", choices=["http", "custom"])
    query_parser.add_argument("--name", help="Custom metric name")
    query_parser.add_argument("--endpoint", help="Filter by endpoint")
    query_parser.add_argument("--method", help="Filter by method")
    query_parser.add_argument("--from-hours", type=int, default=24)
    query_parser.add_argument("--group-by", help="Group by label")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Costs command
    costs_parser = subparsers.add_parser("costs", help="Show LLM costs")
    costs_parser.add_argument("--db", default="metrics.db", help="Database path")
    costs_parser.add_argument("--from-hours", type=int, default=24)
    costs_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export metrics to file")
    export_parser.add_argument("--db", default="metrics.db", help="Database path")
    export_parser.add_argument("--format", default="csv", choices=["csv", "json"])
    export_parser.add_argument("--output", default="metrics.csv", help="Output file")
    export_parser.add_argument("--from-hours", type=int, default=24)

    # Endpoints command
    endpoints_parser = subparsers.add_parser("endpoints", help="Show endpoint stats")
    endpoints_parser.add_argument("--db", default="metrics.db", help="Database path")
    endpoints_parser.add_argument("--sort-by", default="p99", choices=["count", "p99"])
    endpoints_parser.add_argument("--top", type=int, default=10)
    endpoints_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Errors command
    errors_parser = subparsers.add_parser("errors", help="Show error logs")
    errors_parser.add_argument("--db", default="metrics.db", help="Database path")
    errors_parser.add_argument("--from-hours", type=int, default=24)
    errors_parser.add_argument("--endpoint", help="Filter by endpoint")
    errors_parser.add_argument("--limit", type=int, default=20, help="Max errors to show")
    errors_parser.add_argument("--detail", action="store_true", help="Show full stack trace")
    errors_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Setup wizard (your existing code)
    setup_parser = subparsers.add_parser("setup", help="Run interactive setup wizard")

    args = parser.parse_args()

    if not args.command or args.command == "setup":
        # Run your existing setup wizard
        from fastapi_metrics.cli import main as setup_main

        setup_main()
    else:
        # Run async commands
        commands = {
            "show": cmd_show,
            "query": cmd_query,
            "costs": cmd_costs,
            "export": cmd_export,
            "endpoints": cmd_endpoints,
            "errors": cmd_errors,
        }

        try:
            asyncio.run(commands[args.command](args))
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)


if __name__ == "__main__":
    main()
