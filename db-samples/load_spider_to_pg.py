#!/usr/bin/env python3
"""
Load all Spider SQLite databases into PostgreSQL.
Each SQLite database becomes a separate PostgreSQL database.
"""

import sqlite3
import psycopg2
import psycopg2.extensions
import os
import re
import sys
from pathlib import Path

PG_HOST = "127.0.0.1"
PG_PORT = 5433
PG_USER = "sqlide"
PG_PASSWORD = "sqlide"
PG_ADMIN_DB = "postgres"

SPIDER_DB_DIR = Path(__file__).parent / "spider_data" / "database"

# SQLite → PostgreSQL type mapping
SQLITE_TO_PG_TYPES = {
    "integer": "INTEGER",
    "int": "INTEGER",
    "tinyint": "SMALLINT",
    "smallint": "SMALLINT",
    "mediumint": "INTEGER",
    "bigint": "BIGINT",
    "unsigned big int": "BIGINT",
    "int2": "SMALLINT",
    "int8": "BIGINT",
    "text": "TEXT",
    "clob": "TEXT",
    "character": "TEXT",
    "varchar": "TEXT",
    "varying character": "TEXT",
    "nchar": "TEXT",
    "native character": "TEXT",
    "nvarchar": "TEXT",
    "real": "DOUBLE PRECISION",
    "double": "DOUBLE PRECISION",
    "double precision": "DOUBLE PRECISION",
    "float": "REAL",
    "numeric": "NUMERIC",
    "decimal": "NUMERIC",
    "boolean": "BOOLEAN",
    "date": "TEXT",  # Spider dates are stored as text
    "datetime": "TEXT",
    "timestamp": "TEXT",
    "blob": "BYTEA",
    "": "TEXT",
    "none": "TEXT",
}


def map_type(sqlite_type: str) -> str:
    if not sqlite_type:
        return "TEXT"
    base = re.split(r"[\s(]", sqlite_type.strip().lower())[0]
    return SQLITE_TO_PG_TYPES.get(base, "TEXT")


def get_pg_conn(dbname=PG_ADMIN_DB):
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=dbname
    )


def db_exists(dbname: str) -> bool:
    conn = get_pg_conn()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists


def create_pg_db(dbname: str):
    conn = get_pg_conn()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f'CREATE DATABASE "{dbname}" OWNER {PG_USER}')
    cur.close()
    conn.close()


def quote_ident(name: str) -> str:
    return f'"{name}"'


def load_sqlite_to_pg(sqlite_path: Path, pg_dbname: str):
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = get_pg_conn(pg_dbname)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    try:
        # Get all tables (excluding sqlite internal tables)
        sqlite_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in sqlite_cur.fetchall()]

        # Disable FK checks during load
        pg_cur.execute("SET session_replication_role = replica;")

        for table in tables:
            # Get column info
            sqlite_cur.execute(f'PRAGMA table_info("{table}")')
            columns = sqlite_cur.fetchall()

            if not columns:
                continue

            col_defs = []
            pk_cols = [col[1] for col in columns if col[5] > 0]  # col[5] = pk flag

            for col in columns:
                col_name = col[1]
                col_type = map_type(col[2])
                not_null = "NOT NULL" if col[3] and col[5] == 0 else ""
                col_defs.append(f"  {quote_ident(col_name)} {col_type} {not_null}".rstrip())

            # Add PK constraint if exists
            if pk_cols:
                pk_list = ", ".join(quote_ident(c) for c in pk_cols)
                col_defs.append(f"  PRIMARY KEY ({pk_list})")

            create_sql = (
                f'CREATE TABLE IF NOT EXISTS {quote_ident(table)} (\n'
                + ",\n".join(col_defs)
                + "\n);"
            )

            try:
                pg_cur.execute(create_sql)
            except Exception as e:
                print(f"    [WARN] Failed to create table {table}: {e}")
                pg_conn.rollback()
                continue

            # Copy data
            col_names = [col[1] for col in columns]
            sqlite_cur.execute(f'SELECT * FROM "{table}"')
            rows = sqlite_cur.fetchall()

            if rows:
                cols_quoted = ", ".join(quote_ident(c) for c in col_names)
                placeholders = ", ".join(["%s"] * len(col_names))
                insert_sql = f'INSERT INTO {quote_ident(table)} ({cols_quoted}) VALUES ({placeholders})'

                batch = []
                for row in rows:
                    # Convert row values: handle bytes, bools, etc.
                    values = []
                    for v in row:
                        if isinstance(v, bytes):
                            v = psycopg2.Binary(v)
                        values.append(v)
                    batch.append(tuple(values))

                try:
                    pg_cur.executemany(insert_sql, batch)
                except Exception as e:
                    print(f"    [WARN] Failed to insert into {table}: {e}")
                    pg_conn.rollback()
                    # Recreate table without PK to avoid conflicts
                    pg_cur.execute(f'DROP TABLE IF EXISTS {quote_ident(table)}')
                    # Retry without PK
                    col_defs_no_pk = col_defs[:-1] if pk_cols else col_defs
                    create_sql2 = (
                        f'CREATE TABLE IF NOT EXISTS {quote_ident(table)} (\n'
                        + ",\n".join(col_defs_no_pk)
                        + "\n);"
                    )
                    pg_cur.execute(create_sql2)
                    try:
                        pg_cur.executemany(insert_sql, batch)
                    except Exception as e2:
                        print(f"    [ERROR] Still failed for {table}: {e2}")
                        pg_conn.rollback()
                        continue

        pg_conn.commit()

    finally:
        pg_cur.execute("SET session_replication_role = DEFAULT;")
        pg_conn.commit()
        pg_cur.close()
        pg_conn.close()
        sqlite_cur.close()
        sqlite_conn.close()


def main():
    db_dirs = sorted(SPIDER_DB_DIR.iterdir())
    total = len(db_dirs)
    skipped = 0
    loaded = 0
    errors = 0

    for i, db_dir in enumerate(db_dirs, 1):
        if not db_dir.is_dir():
            continue

        db_name = db_dir.name
        pg_dbname = f"spider_{db_name}"

        # Find sqlite file
        sqlite_files = list(db_dir.glob("*.sqlite")) + list(db_dir.glob("*.splite"))
        if not sqlite_files:
            print(f"[{i}/{total}] {db_name}: no sqlite file, skipping")
            skipped += 1
            continue

        sqlite_path = sqlite_files[0]

        if db_exists(pg_dbname):
            print(f"[{i}/{total}] {db_name}: already exists, skipping")
            skipped += 1
            continue

        print(f"[{i}/{total}] {db_name} → {pg_dbname} ...", end=" ", flush=True)
        try:
            create_pg_db(pg_dbname)
            load_sqlite_to_pg(sqlite_path, pg_dbname)
            print("OK")
            loaded += 1
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1

    print(f"\nDone: {loaded} loaded, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
