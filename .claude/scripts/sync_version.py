#!/usr/bin/env python3
"""
Sync VERSION from src/utils/config.py to README.md and other files.

This script is the SOURCE OF TRUTH sync mechanism for PDFusion versioning.
Run this after updating VERSION in src/utils/config.py to propagate changes to README.

Usage:
    python .claude/scripts/sync_version.py
"""

import re
from pathlib import Path
from datetime import datetime


def read_version():
    """Read VERSION from src/utils/config.py (source of truth)."""
    config_path = Path(__file__).parent.parent.parent / "src" / "utils" / "config.py"

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find VERSION in src/utils/config.py")

    return match.group(1)


def update_readme(version):
    """Update README.md with the new version."""
    readme_path = Path(__file__).parent.parent.parent / "README.md"

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update version badge
    content = re.sub(
        r'!\[Version\]\(https://img\.shields\.io/badge/version-[^-]+-blue\)',
        f'[![Version](https://img.shields.io/badge/version-{version}-blue)]()',
        content
    )

    # Update Pre-built Installers section
    content = re.sub(
        r'`PDFusion-[0-9.]+-windows-setup\.exe`',
        f'`PDFusion-{version}-windows-setup.exe`',
        content
    )
    content = re.sub(
        r'`PDFusion-[0-9.]+-macos\.dmg`',
        f'`PDFusion-{version}-macos.dmg`',
        content
    )
    content = re.sub(
        r'`PDFusion-[0-9.]+-linux\.AppImage`',
        f'`PDFusion-{version}-linux.AppImage`',
        content
    )

    # Update footer version and date
    content = re.sub(
        r'Version [0-9.a-z-]+ \| Last Updated: \d{4}-\d{2}-\d{2}',
        f'Version {version} | Last Updated: {datetime.now().strftime("%Y-%m-%d")}',
        content
    )

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return readme_path


def main():
    """Main entry point."""
    try:
        version = read_version()
        print(f"[INFO] Read VERSION from src/utils/config.py: {version}")

        readme_path = update_readme(version)
        print(f"[OK] Updated {readme_path.name} with version {version}")
        print(f"[OK] Updated footer with current date: {datetime.now().strftime('%Y-%m-%d')}")

        print("\n[SUCCESS] Version sync completed!")
        print(f"[NEXT] Commit the changes with:")
        print(f"       git add README.md")
        print(f"       git commit -m 'chore: Bump version to {version}'")

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}")
        exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}")
        exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
