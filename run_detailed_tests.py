#!/usr/bin/env python3
"""Test runner that captures detailed failure info."""

import subprocess
import sys

# Run pytest with maximum verbosity
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=long",
        "-x",  # Stop on first failure
        "--capture=no",
    ],
    cwd="/workspaces/fastapi-metrics",
    capture_output=True,
    text=True,
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")

# Save to file for inspection
with open("/workspaces/fastapi-metrics/test_results.txt", "w") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nReturn code: {result.returncode}")

sys.exit(result.returncode)
