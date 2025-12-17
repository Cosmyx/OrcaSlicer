#!/usr/bin/env python3
"""
Script to fix the compatible_printer field typo in common filament library files.

This script:
1. Scans all JSON files in the Common Filament library
2. Finds files using "compatible_printer" (singular - incorrect)
3. Replaces with "compatible_printers" (plural - correct)
4. Preserves JSON formatting and structure
5. Reports all changes made
"""

import json
import os
from pathlib import Path
from typing import List, Tuple

# Base directory for scanning
BASE_DIR = Path(__file__).parent
COMMON_FILAMENT_DIR = BASE_DIR / "Common Filament library"


def fix_compatible_printer_field(file_path: Path) -> Tuple[bool, str]:
    """
    Fix the compatible_printer field in a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Tuple of (was_modified, message)
    """
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if the file contains the typo
        if '"compatible_printer"' not in content:
            return False, "No typo found"

        # Parse JSON to verify structure
        data = json.loads(content)

        # Check if compatible_printer exists (shouldn't use json.load because we want to preserve formatting)
        if 'compatible_printer' not in data:
            return False, "No compatible_printer field in JSON"

        # Replace the field name in the raw content to preserve formatting
        new_content = content.replace('"compatible_printer"', '"compatible_printers"')

        # Verify the new content is valid JSON
        json.loads(new_content)

        # Write the fixed content back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True, "Fixed: compatible_printer → compatible_printers"

    except json.JSONDecodeError as e:
        return False, f"JSON parsing error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def scan_and_fix_files() -> List[Tuple[Path, bool, str]]:
    """
    Scan all JSON files in Common Filament library and fix them.

    Returns:
        List of (file_path, was_modified, message) tuples
    """
    results = []

    if not COMMON_FILAMENT_DIR.exists():
        print(f"Error: Directory not found: {COMMON_FILAMENT_DIR}")
        return results

    # Scan all JSON files in Common Filament library subdirectories
    for root, dirs, files in os.walk(COMMON_FILAMENT_DIR):
        for file in files:
            if file.endswith('.json'):
                file_path = Path(root) / file
                relative_path = file_path.relative_to(BASE_DIR)

                was_modified, message = fix_compatible_printer_field(file_path)
                results.append((relative_path, was_modified, message))

    return results


def main():
    print("=" * 80)
    print("Fixing compatible_printer field in Common Filament library")
    print("=" * 80)
    print()

    results = scan_and_fix_files()

    if not results:
        print("No files found to process.")
        return

    # Separate modified and unmodified files
    modified_files = [(path, msg) for path, modified, msg in results if modified]
    unmodified_files = [(path, msg) for path, modified, msg in results if not modified]

    # Print modified files
    if modified_files:
        print(f"FIXED FILES ({len(modified_files)}):")
        print("-" * 80)
        for path, message in modified_files:
            print(f"  [FIXED] {path}")
            print(f"    {message}")
        print()

    # Print summary of unmodified files
    if unmodified_files:
        print(f"UNMODIFIED FILES ({len(unmodified_files)}):")
        print("-" * 80)

        # Group by reason
        no_typo = [path for path, msg in unmodified_files if "No typo found" in msg]
        errors = [(path, msg) for path, msg in unmodified_files if "No typo found" not in msg]

        if no_typo:
            print(f"  Already correct: {len(no_typo)} files")

        if errors:
            print(f"  Errors: {len(errors)} files")
            for path, message in errors:
                print(f"    [ERROR] {path}")
                print(f"      {message}")
        print()

    # Print summary
    print("=" * 80)
    print("SUMMARY:")
    print(f"  Total files processed: {len(results)}")
    print(f"  Files modified: {len(modified_files)}")
    if unmodified_files:
        no_typo_count = len([path for path, msg in unmodified_files if "No typo found" in msg])
        error_count = len([path for path, msg in unmodified_files if "No typo found" not in msg])
        print(f"  Files already correct: {no_typo_count}")
        print(f"  Errors: {error_count}")
    print("=" * 80)

    if modified_files:
        print()
        print("[SUCCESS] Fix completed successfully!")
        print("  Next step: Run ztool_generate_cosmyx_json.py to regenerate cosmyx.json")


if __name__ == "__main__":
    main()
