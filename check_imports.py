#!/usr/bin/env python3
"""Quick check that all imports work."""
import sys
from pathlib import Path

repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / "src"))

try:
    # Check that we can import the modules
    print("Checking imports...")

    from core.merge import merge, _merge_simple, _merge_chunked, CHUNK_SIZE, CHUNKED_MERGE_THRESHOLD
    print("✓ core.merge imported successfully")

    from utils.exceptions import PDFusionError
    print("✓ utils.exceptions imported successfully")

    from core.protect import protect, ProtectConfig
    print("✓ core.protect imported successfully")

    import pikepdf
    print("✓ pikepdf imported successfully")

    print("\nAll imports successful!")
    print(f"CHUNKED_MERGE_THRESHOLD = {CHUNKED_MERGE_THRESHOLD}")
    print(f"CHUNK_SIZE = {CHUNK_SIZE}")

except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
