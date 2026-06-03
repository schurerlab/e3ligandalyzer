#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from pathlib import Path


def quote_identifier(name: str) -> str:
    """Safely quote SQLite table/column identifiers."""
    return '"' + name.replace('"', '""') + '"'


def print_table_headers_and_preview(db_path, n_rows=5):
    db_path = str(db_path)

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print("No tables found in the database.")
        conn.close()
        return

    print(f"\nDatabase: {db_path}")
    print("=" * (len(db_path) + 10))

    for table_name in tables:
        print(f"\nTable: {table_name}")
        print("-" * (len(table_name) + 8))

        cursor.execute(f"PRAGMA table_info({quote_identifier(table_name)});")
        columns = cursor.fetchall()

        if not columns:
            print("  (No columns found)")
            continue

        col_names = [col[1] for col in columns]

        print("  Columns:")
        for col in columns:
            # col = (cid, name, type, notnull, dflt_value, pk)
            print(f"    - {col[1]} ({col[2]})")

        cursor.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)};")
        row_count = cursor.fetchone()[0]
        print(f"\n  Row count: {row_count}")

        print(f"\n  First {n_rows} rows:")
        cursor.execute(f"SELECT * FROM {quote_identifier(table_name)} LIMIT {int(n_rows)};")
        rows = cursor.fetchall()

        if not rows:
            print("    (No rows)")
            continue

        # Print compact table-style preview
        print("    " + " | ".join(col_names))
        print("    " + "-" * min(160, len(" | ".join(col_names))))

        for row in rows:
            formatted = []
            for value in row:
                text = "" if value is None else str(value)
                text = text.replace("\n", "\\n")
                if len(text) > 80:
                    text = text[:77] + "..."
                formatted.append(text)
            print("    " + " | ".join(formatted))

    conn.close()


if __name__ == "__main__":
    # db_file = "Ligases/eliah.db"
    db_file = "Ligases/Ligase_Recruiter.db"
    # db_file = "Ligases/Ligase_Recruiter_2.db"

    print_table_headers_and_preview(db_file, n_rows=5)