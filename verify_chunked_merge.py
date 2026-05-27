#!/usr/bin/env python3
"""
Verification script for chunked merge implementation.
Runs a subset of critical tests to verify the change works.
"""
import sys
import subprocess
from pathlib import Path

# Change to repo root
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / "src"))

def run_tests():
    """Run the test suite."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_merge_chunked.py",
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
        ],
        cwd=repo_root,
    )
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
