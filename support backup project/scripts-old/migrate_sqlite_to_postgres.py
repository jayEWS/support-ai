#!/usr/bin/env python3
"""Migrate from a local SQLite DB file to a Postgres database (e.g., Supabase).

Usage:
  # set destination DATABASE_URL first (SQLAlchemy style, psycopg2)
  setx DATABASE_URL "postgresql+psycopg2://user:password@host:5432/dbname"
  # or in PowerShell for current session:
  $env:DATABASE_URL = 'postgresql+psycopg2://user:password@host:5432/dbname'

  # then run:
  python scripts/migrate_sqlite_to_postgres.py [source_file] [--batch-size N]

Notes:
- This is intended for small-to-medium datasets for demo/dev migration.
- It preserves column names as-is. Identity/autoincrement semantics may
  differ between SQLite and Postgres.
- Ensure `psycopg2-binary` is installed in your venv.

"""

import os
import sys
import argparse
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.orm import sessionmaker
from app.models.models import Base

parser = argparse.ArgumentParser()
parser.add_argument('source', nargs='?', default='data.db', help='SQLite file path')
parser.add_argument('--batch-size', type=int, default=500, help='Insert batch size')
args = parser.parse_args()

src_file = args.source
if not os.path.exists(src_file):
    print(f"ERROR: source SQLite file not found: {src_file}")
    sys.exit(1)

dest_url = os.environ.get('DATABASE_URL')
if not dest_url:
    print("ERROR: set DATABASE_URL env var to your Postgres (Supabase) connection first")
    sys.exit(1)

if 'sqlite' in dest_url.lower():
    print('ERROR: destination appears to be SQLite. Set DATABASE_URL to Postgres (Supabase).')
    sys.exit(1)

print(f"Migrating from sqlite:///{src_file} -> {dest_url}")

src_engine = create_engine(f"sqlite:///{src_file}")
dst_engine = create_engine(dest_url)

# ensure destination schema/tables exist
print("Creating destination schema/tables (if missing) via SQLAlchemy metadata...")
Base.metadata.create_all(dst_engine)

SrcSession = sessionmaker(bind=src_engine)
DstSession = sessionmaker(bind=dst_engine)

src = SrcSession()
dst = DstSession()

# Read source table metadata (SQLite, no schema prefix)
src_metadata = MetaData()
src_metadata.reflect(bind=src_engine)

try:
    for table in Base.metadata.sorted_tables:
        table_name = table.name
        print(f"Copying table: {table_name}")
        
        # Get the source table definition (no schema prefix for SQLite)
        if table_name not in src_metadata.tables:
            print(f"  WARNING: table {table_name} not found in SQLite source, skipping")
            continue
        
        src_table = src_metadata.tables[table_name]
        
        # read rows in batches from source
        offset = 0
        rows_copied = 0
        while True:
            rows = src.execute(src_table.select().limit(args.batch_size).offset(offset)).fetchall()
            if not rows:
                break
            # convert to dicts
            data = [dict(r) for r in rows]
            # insert into destination (using Base table which has schema prefix for Postgres)
            try:
                dst.execute(table.insert(), data)
                dst.commit()
            except Exception as e:
                dst.rollback()
                print(f"Warning: failed inserting batch at offset {offset} for table {table_name}: {e}")
                # attempt row-by-row fallback
                for row in data:
                    try:
                        dst.execute(table.insert(), row)
                        dst.commit()
                    except Exception as e2:
                        dst.rollback()
                        print(f"  row insert failed: {e2} -- continuing")
            rows_copied += len(data)
            offset += len(data)
        print(f"  finished table {table_name}: copied {rows_copied} rows")
    print("Migration complete.")
except Exception as e:
    print(f"Migration failed: {e}")
    raise
finally:
    src.close()
    dst.close()

print("After migration: set DATABASE_URL to the destination Postgres URL in your .env and restart the server.")
