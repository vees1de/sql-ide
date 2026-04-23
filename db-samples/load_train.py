#!/usr/bin/env python3
"""Load train.csv into PostgreSQL sqlide_analytics database."""

import csv
import io
import os
import sys
import psycopg

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://sqlide:sqlide@localhost:5433/sqlide_analytics",
)

CSV_PATH = os.path.join(os.path.dirname(__file__), "train.csv")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS train (
    city_id                       SMALLINT,
    order_id                      TEXT,
    tender_id                     TEXT,
    user_id                       TEXT,
    driver_id                     TEXT,
    offset_hours                  SMALLINT,
    status_order                  TEXT,
    status_tender                 TEXT,
    order_timestamp               TIMESTAMP,
    tender_timestamp              TIMESTAMP,
    driveraccept_timestamp        TIMESTAMP,
    driverarrived_timestamp       TIMESTAMP,
    driverstarttheride_timestamp  TIMESTAMP,
    driverdone_timestamp          TIMESTAMP,
    clientcancel_timestamp        TIMESTAMP,
    drivercancel_timestamp        TIMESTAMP,
    order_modified_local          TIMESTAMP,
    cancel_before_accept_local    TIMESTAMP,
    distance_in_meters            INTEGER,
    duration_in_seconds           INTEGER,
    price_order_local             NUMERIC(12, 2),
    price_tender_local            NUMERIC(12, 2),
    price_start_local             NUMERIC(12, 2)
);
"""

COLUMNS = (
    "city_id,order_id,tender_id,user_id,driver_id,offset_hours,"
    "status_order,status_tender,order_timestamp,tender_timestamp,"
    "driveraccept_timestamp,driverarrived_timestamp,"
    "driverstarttheride_timestamp,driverdone_timestamp,"
    "clientcancel_timestamp,drivercancel_timestamp,"
    "order_modified_local,cancel_before_accept_local,"
    "distance_in_meters,duration_in_seconds,"
    "price_order_local,price_tender_local,price_start_local"
)

EXPECTED_COLUMNS = len(COLUMNS.split(","))


def rows_to_tsv(path: str) -> io.BytesIO:
    """Convert CSV to TSV buffer compatible with PostgreSQL COPY."""
    buf = io.BytesIO()
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < EXPECTED_COLUMNS:
                row = row + [""] * (EXPECTED_COLUMNS - len(row))
            elif len(row) > EXPECTED_COLUMNS:
                row = row[:EXPECTED_COLUMNS]
            # Replace empty strings with \N (NULL in COPY format)
            tsv_row = "\t".join(v if v != "" else r"\N" for v in row)
            buf.write((tsv_row + "\n").encode())
    buf.seek(0)
    return buf


def main() -> None:
    print(f"Connecting to {DSN.split('@')[-1]} ...")
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            cur.execute("SELECT COUNT(*) FROM train")
            existing = cur.fetchone()[0]
            if existing > 0:
                print(f"Table already has {existing:,} rows — truncating.")
                cur.execute("TRUNCATE train")
            conn.commit()

        print(f"Reading {CSV_PATH} ...")
        buf = rows_to_tsv(CSV_PATH)

        print("Loading via COPY ...")
        with conn.cursor() as cur:
            with cur.copy(f"COPY train ({COLUMNS}) FROM STDIN") as copy:
                while True:
                    chunk = buf.read(65536)
                    if not chunk:
                        break
                    copy.write(chunk)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM train")
            total = cur.fetchone()[0]
        print(f"Done — {total:,} rows loaded.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
