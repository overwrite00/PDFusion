#!/usr/bin/env python3
"""
Sync VERSION from src/utils/config.py to all version-bearing files.

This script is the SOURCE OF TRUTH sync mechanism for PDFusion versioning.
Run this after updating VERSION in src/utils/config.py to propagate changes to:
  1. README.md (badge)
  2. pyproject.toml (version field)
  3. PDFusion.spec (macOS bundle version)
  4. installer/windows/installer.nsi (Windows VERSION define)
  5. assets/hero.png (optional: regenerate with version text)

Usage:
    python .claude/scripts/sync_version.py
"""

import re
import sys
from pathlib import Path
from datetime import datetime

# Try to import PIL for hero.png regeneration
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_project_root():
    """Get absolute path to PDFusion project root."""
    return Path(__file__).parent.parent.parent.resolve()


def read_version():
    """Read VERSION from src/utils/config.py (source of truth)."""
    config_path = get_project_root() / "src" / "utils" / "config.py"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Could not find {config_path}: {e}")

    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"Could not find VERSION in {config_path}")

    return match.group(1)


def update_readme(version):
    """Update README.md with the new version."""
    readme_path = get_project_root() / "README.md"

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update version badge — regex now includes leading [
    content = re.sub(
        r'\[\[!?\[Version\]\(https://img\.shields\.io/badge/version-[^\]]+\)\]',
        f'[![Version](https://img.shields.io/badge/version-{version}-blue)]',
        content
    )
    # Alternative pattern if the above doesn't match (simpler pattern)
    if '[![Version]' not in content and '![[[![Version]' in content:
        content = re.sub(
            r'\[\[!\[Version\]\(https://img\.shields\.io/badge/version-[^\)]+\)\]\]\(\)\]\(\)',
            f'[![Version](https://img.shields.io/badge/version-{version}-blue)]()',
            content
        )

    # Update Pre-built Installers section (if present)
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


def update_pyproject_toml(version):
    """Update pyproject.toml with the new version."""
    pyproject_path = get_project_root() / "pyproject.toml"

    with open(pyproject_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace version field on line 7 (or wherever it appears)
    content = re.sub(
        r'version\s*=\s*["\'][0-9.]+["\']',
        f'version = "{version}"',
        content
    )

    with open(pyproject_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return pyproject_path


def update_pdfusion_spec(version):
    """Update PDFusion.spec with the new version (macOS bundle)."""
    spec_path = get_project_root() / "PDFusion.spec"

    with open(spec_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update CFBundleVersion (line 119)
    content = re.sub(
        r'"CFBundleVersion":\s*["\'][0-9.]+["\']',
        f'"CFBundleVersion": "{version}"',
        content
    )

    # Update CFBundleShortVersionString (line 120)
    content = re.sub(
        r'"CFBundleShortVersionString":\s*["\'][0-9.]+["\']',
        f'"CFBundleShortVersionString": "{version}"',
        content
    )

    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return spec_path


def update_nsis_installer(version):
    """Update installer/windows/installer.nsi with the new version."""
    nsis_path = get_project_root() / "installer" / "windows" / "installer.nsi"

    with open(nsis_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update VERSION define on line 5
    content = re.sub(
        r'!define VERSION\s+"[0-9.]+"',
        f'!define VERSION "{version}"',
        content
    )

    with open(nsis_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return nsis_path


def regenerate_hero_png(version):
    """Regenerate assets/hero.png with version text (optional, requires PIL)."""
    if not HAS_PIL:
        print(f"[SKIP] PIL/Pillow not available — skipping hero.png regeneration")
        return None

    hero_path = get_project_root() / "assets" / "hero.png"

    # If hero.png doesn't exist, skip
    if not hero_path.exists():
        print(f"[SKIP] hero.png not found at {hero_path}")
        return None

    try:
        # Open existing image
        img = Image.open(hero_path)
        draw = ImageDraw.Draw(img)

        # Try to use a reasonable font, fallback to default
        try:
            font_size = int(img.width * 0.05)  # 5% of image width
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            # Fallback to default font
            font = ImageFont.load_default()

        # Draw version text in bottom-right corner
        text = f"v{version}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = img.width - text_width - 20
        y = img.height - text_height - 20

        # Draw with semi-transparent background
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))

        # Save
        img.save(hero_path)
        return hero_path
    except Exception as e:
        print(f"[WARN] Failed to regenerate hero.png: {e}")
        return None


def main():
    """Main entry point — sync version to all files."""
    try:
        # Read version from source of truth
        version = read_version()
        print(f"[INFO] Read VERSION from src/utils/config.py: {version}\n")

        # Update each file
        print("[SYNC] Updating files...")

        readme_path = update_readme(version)
        print(f"[OK] Updated {readme_path.name}")

        pyproject_path = update_pyproject_toml(version)
        print(f"[OK] Updated {pyproject_path.name}")

        spec_path = update_pdfusion_spec(version)
        print(f"[OK] Updated {spec_path.name}")

        nsis_path = update_nsis_installer(version)
        print(f"[OK] Updated {nsis_path.name}")

        hero_path = regenerate_hero_png(version)
        if hero_path:
            print(f"[OK] Regenerated {hero_path.name}")

        print(f"\n[SUCCESS] Version sync completed!")
        print(f"[NEXT] Commit the changes with:")
        print(f"       git add README.md pyproject.toml PDFusion.spec installer/windows/installer.nsi")
        print(f"       git commit -m 'chore: Bump version to {version}'")

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
