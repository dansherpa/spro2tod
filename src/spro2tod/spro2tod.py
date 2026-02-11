#!/usr/bin/env python3
"""
spro2tod - Extract Time of Day (ToD) data from Vola SPRO files.

Reads a SPRO file (ZIP archive containing SQLite timing database) and
outputs all ToD values for all bibs across both Start and Finish channels.
"""

import csv
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import List, Optional, Tuple


def format_tod(microseconds: int) -> str:
    """
    Format microseconds since Unix epoch as ToD string.

    Args:
        microseconds: Time in microseconds since Unix epoch

    Returns:
        Formatted string like "10h17:07.3180"
    """
    seconds = microseconds / 1_000_000
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)

    # Extract sub-second portion (4 decimal places)
    fractional = microseconds % 1_000_000
    sub_seconds = f"{fractional:06d}"[:4]

    return f"{dt.hour}h{dt.minute:02d}:{dt.second:02d}.{sub_seconds}"


def get_runs(conn: sqlite3.Connection) -> List[int]:
    """
    Discover which runs exist in the database by checking for timing tables.

    Args:
        conn: SQLite database connection

    Returns:
        List of run numbers found
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'TTIMERECORDS_HEAT%'")
    tables = [row[0] for row in cursor.fetchall()]

    runs = set()
    for table in tables:
        # Extract run number from table name like TTIMERECORDS_HEAT1_START
        parts = table.split('_')
        if len(parts) >= 2:
            heat_part = parts[1]  # e.g., "HEAT1"
            if heat_part.startswith('HEAT'):
                try:
                    run_num = int(heat_part[4:])
                    runs.add(run_num)
                except ValueError:
                    pass

    return sorted(runs)


def extract_run_data(conn: sqlite3.Connection, run: int) -> List[Tuple[int, int, str, str]]:
    """
    Extract ToD data for all bibs from a specific run.

    Args:
        conn: SQLite database connection
        run: Run number

    Returns:
        List of (bib, run, channel, tod) tuples where tod is formatted time or "DNF"
    """
    cursor = conn.cursor()
    results = []
    start_bibs = set()
    finish_bibs = set()

    # Extract Start data (all statuses)
    start_table = f"TTIMERECORDS_HEAT{run}_START"
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (start_table,)
    )
    if cursor.fetchone():
        query = f'''
            SELECT "C_NUM" AS bib, "C_HOUR2" AS micros
            FROM "{start_table}"
            WHERE "C_NUM" > 0
            AND ("C_NUM" < 901 OR "C_NUM" > 909)
            ORDER BY "C_NUM"
        '''
        cursor.execute(query)
        for row in cursor.fetchall():
            bib, micros = row
            if micros is not None:
                results.append((int(bib), run, "Start", format_tod(int(micros))))
                start_bibs.add(int(bib))

    # Extract Finish data (all statuses, but mark non-zero status as DNF)
    finish_table = f"TTIMERECORDS_HEAT{run}_FINISH"
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (finish_table,)
    )
    if cursor.fetchone():
        query = f'''
            SELECT "C_NUM" AS bib, "C_HOUR2" AS micros, "C_STATUS" AS status
            FROM "{finish_table}"
            WHERE "C_NUM" > 0
            AND ("C_NUM" < 901 OR "C_NUM" > 909)
            ORDER BY "C_NUM"
        '''
        cursor.execute(query)
        for row in cursor.fetchall():
            bib, micros, status = row
            bib = int(bib)
            finish_bibs.add(bib)
            if status == 0 and micros is not None:
                results.append((bib, run, "Finish", format_tod(int(micros))))
            else:
                results.append((bib, run, "Finish", "DNF"))

    # Add DNF entries for bibs that started but have no finish record
    for bib in start_bibs - finish_bibs:
        results.append((bib, run, "Finish", "DNF"))

    return results


def process_spro(spro_path: str, output_path: str) -> None:
    """
    Process a SPRO file and output CSV of all ToD values.

    Args:
        spro_path: Path to the .spro file
        output_path: Path for output CSV
    """
    spro_full_path = os.path.abspath(spro_path)
    output_full_path = os.path.abspath(output_path)

    print(f"Reading {spro_full_path}")

    # Extract SPRO file to temp directory
    tempdir = tempfile.mkdtemp(prefix="spro2tod_")

    try:
        with zipfile.ZipFile(spro_path, 'r') as zip_obj:
            zip_obj.extractall(path=tempdir)

        db_path = os.path.join(tempdir, "File2")
        if not os.path.exists(db_path):
            print(f"Error: Database file 'File2' not found in {spro_full_path}", file=sys.stderr)
            sys.exit(1)

        conn = sqlite3.connect(db_path)

        print("Extracting ToD")

        # Collect all timing data
        all_data = []
        runs = get_runs(conn)
        bibs = set()

        for run in runs:
            run_data = extract_run_data(conn, run)
            all_data.extend(run_data)
            for bib, _, _, _ in run_data:
                bibs.add(bib)

        conn.close()

        print(f"Extracted times for {len(bibs)} bibs and {len(runs)} runs")

        # Sort by bib, then run, then channel (Start before Finish)
        all_data.sort(key=lambda x: (x[0], x[1], x[2] != "Start"))

        # Write CSV
        print(f"Writing to {output_full_path}")

        with open(output_path, 'w', newline='') as out_file:
            writer = csv.writer(out_file)
            writer.writerow(["Bib", "Run", "Channel", "ToD"])

            for bib, run, channel, tod in all_data:
                writer.writerow([bib, run, channel, tod])

    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(tempdir, ignore_errors=True)


def get_default_output_path(spro_path: str) -> str:
    """
    Generate default output path from input path.

    Args:
        spro_path: Path to the .spro file

    Returns:
        Path like "foobar-tod.csv" for input "foobar.spro"
    """
    base = os.path.basename(spro_path)
    root, _ = os.path.splitext(base)
    return f"{root}-tod.csv"


def confirm_overwrite(path: str) -> bool:
    """
    Ask user for permission to overwrite existing file.

    Args:
        path: Path to the file that would be overwritten

    Returns:
        True if user confirms, False otherwise
    """
    try:
        response = input(f"File {os.path.abspath(path)} already exists. Overwrite? [y/N]: ")
        return response.lower().strip() == 'y'
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def prompt_for_input(prompt: str, default: Optional[str] = None) -> str:
    """
    Prompt user for input with optional default value.

    Args:
        prompt: The prompt to display
        default: Default value if user presses Enter

    Returns:
        User input or default value
    """
    try:
        if default:
            response = input(f"{prompt} [{default}]: ").strip()
            return response if response else default
        else:
            response = input(f"{prompt}: ").strip()
            return response
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def main():
    """CLI entry point."""
    if len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} [file.spro] [output.csv]", file=sys.stderr)
        print("\nExtracts all Time of Day values from a SPRO file.", file=sys.stderr)
        print("If no arguments provided, prompts for input.", file=sys.stderr)
        sys.exit(1)

    # Get input file
    if len(sys.argv) >= 2:
        spro_path = sys.argv[1]
    else:
        spro_path = prompt_for_input("SPRO file")

    if not spro_path:
        print("Error: No input file specified.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(spro_path):
        print(f"Error: File not found: {spro_path}", file=sys.stderr)
        sys.exit(1)

    # Get output file
    default_output = get_default_output_path(spro_path)
    if len(sys.argv) == 3:
        output_path = sys.argv[2]
    elif len(sys.argv) == 2:
        output_path = default_output
    else:
        output_path = prompt_for_input("Output CSV file", default_output)

    if not output_path:
        output_path = default_output

    # Check if output file exists
    if os.path.exists(output_path):
        if not confirm_overwrite(output_path):
            print("Aborted.")
            sys.exit(0)

    process_spro(spro_path, output_path)


if __name__ == '__main__':
    main()
