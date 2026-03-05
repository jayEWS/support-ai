#!/usr/bin/env python3
"""Migrate existing SQL Server database to a local SQLite file.

Usage:
    python scripts/migrate_to_sqlite.py [output_file]

This script reads the current DATABASE_URL from the environment (which should
point at an SQL Server instance with the full schema and data).  It creates a
new SQLite database file, copies the schema using SQLAlchemy metadata, and then
moves all rows table-by-table.  The resulting file can be used by setting
`DATABASE_URL=sqlite:///./data.db`.

The migration is intended for development/demo purposes only; large datasets may
be slow and identity columns may not be preserved exactly.
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base

# determine source and destination
source_url = os.environ.get("DATABASE_URL")
if not source_url:
    print("ERROR: set DATABASE_URL to your SQL Server connection first")
    sys.exit(1)

out_file = sys.argv[1] if len(sys.argv) > 1 else "data.db"
dest_url = f"sqlite:///{out_file}"

if "sqlite" in source_url.lower():
    print("Source is already SQLite; nothing to migrate.")
    sys.exit(1)

print(f"Migrating from {source_url} → {dest_url}")

# create engines
src_engine = create_engine(source_url)
dst_engine = create_engine(dest_url)

# create destination schema
Base.metadata.create_all(dst_engine)

SrcSession = sessionmaker(bind=src_engine)
DstSession = sessionmaker(bind=dst_engine)

src_sess = SrcSession()
dst_sess = DstSession()

try:
    for table in Base.metadata.sorted_tables:
        print(f"Copying table {table.name}...")
        rows = src_sess.execute(table.select()).fetchall()
        if not rows:
            continue
        # convert each row to dict, removing _sa_instance_state if present
        data = [dict(r) for r in rows]
        dst_sess.execute(table.insert(), data)
    dst_sess.commit()
    print(f"Migration complete; output file: {out_file}")
except Exception as e:
    print(f"Migration failed: {e}")
    dst_sess.rollback()
finally:
    src_sess.close()
    dst_sess.close()

print("To use the new database, set:\n    DATABASE_URL=sqlite:///./%s" % out_file)
