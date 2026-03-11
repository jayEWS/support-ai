"""
Extract complete database schema from local SQL Server [JAY] database.
Generates Knowledge Base documents for AI to answer agent SQL questions.
"""
import pyodbc
import os
import json
from datetime import datetime

CONN_STR = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=JAY;UID=sa;PWD=1;TrustServerCertificate=yes;Encrypt=no'
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'knowledge')

def connect():
    return pyodbc.connect(CONN_STR)

def extract_tables(cursor):
    """Extract all tables with their columns, keys, and indexes."""
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE='BASE TABLE' 
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    tables = cursor.fetchall()
    
    doc_parts = []
    doc_parts.append("# JAY Database — Complete Table Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Tables: {len(tables)}")
    doc_parts.append(f"# Database: JAY (SQL Server 2019, Edgeworks POS)")
    doc_parts.append("")
    
    table_list = []
    for t in tables:
        schema, name = t.TABLE_SCHEMA, t.TABLE_NAME
        table_list.append(f"[{schema}].[{name}]")
    
    doc_parts.append("## Table Index")
    doc_parts.append(", ".join(table_list))
    doc_parts.append("")
    
    for t in tables:
        schema, name = t.TABLE_SCHEMA, t.TABLE_NAME
        doc_parts.append(f"\n{'='*70}")
        doc_parts.append(f"## Table: [{schema}].[{name}]")
        doc_parts.append(f"{'='*70}")
        
        # Columns
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, 
                   NUMERIC_PRECISION, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA='{schema}' AND TABLE_NAME='{name}' 
            ORDER BY ORDINAL_POSITION
        """)
        cols = cursor.fetchall()
        doc_parts.append(f"\nColumns ({len(cols)}):")
        for c in cols:
            size = ""
            if c.CHARACTER_MAXIMUM_LENGTH:
                size = f"({c.CHARACTER_MAXIMUM_LENGTH})" if c.CHARACTER_MAXIMUM_LENGTH != -1 else "(MAX)"
            elif c.NUMERIC_PRECISION:
                size = f"({c.NUMERIC_PRECISION})"
            null = "NULL" if c.IS_NULLABLE == "YES" else "NOT NULL"
            default = f" DEFAULT {c.COLUMN_DEFAULT}" if c.COLUMN_DEFAULT else ""
            doc_parts.append(f"  - {c.COLUMN_NAME:<40} {c.DATA_TYPE}{size:<15} {null}{default}")
        
        # Primary Keys
        try:
            cursor.execute(f"""
                SELECT COL_NAME(ic.object_id, ic.column_id) as col_name
                FROM sys.indexes i
                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                WHERE i.is_primary_key = 1 
                AND i.object_id = OBJECT_ID('[{schema}].[{name}]')
                ORDER BY ic.key_ordinal
            """)
            pks = [r.col_name for r in cursor.fetchall()]
            if pks:
                doc_parts.append(f"  Primary Key: {', '.join(pks)}")
        except:
            pass
        
        # Foreign Keys
        try:
            cursor.execute(f"""
                SELECT 
                    fk.name AS fk_name,
                    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS col,
                    OBJECT_SCHEMA_NAME(fkc.referenced_object_id) + '.' + OBJECT_NAME(fkc.referenced_object_id) AS ref_table,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ref_col
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                WHERE fk.parent_object_id = OBJECT_ID('[{schema}].[{name}]')
            """)
            fks = cursor.fetchall()
            if fks:
                doc_parts.append(f"  Foreign Keys:")
                for fk in fks:
                    doc_parts.append(f"    - {fk.col} -> {fk.ref_table}.{fk.ref_col} ({fk.fk_name})")
        except:
            pass
        
        # Row count estimate
        try:
            cursor.execute(f"""
                SELECT SUM(p.rows) as row_count
                FROM sys.partitions p
                WHERE p.object_id = OBJECT_ID('[{schema}].[{name}]') AND p.index_id IN (0,1)
            """)
            rc = cursor.fetchone()
            if rc and rc.row_count:
                doc_parts.append(f"  Approximate Rows: {int(rc.row_count):,}")
        except:
            pass
    
    return "\n".join(doc_parts), len(tables)


def extract_stored_procedures(cursor):
    """Extract all stored procedures with their source code."""
    cursor.execute("""
        SELECT 
            SCHEMA_NAME(p.schema_id) as [schema],
            p.name,
            p.create_date,
            p.modify_date,
            m.definition
        FROM sys.procedures p
        JOIN sys.sql_modules m ON p.object_id = m.object_id
        WHERE p.is_ms_shipped = 0
        ORDER BY p.name
    """)
    procs = cursor.fetchall()
    
    doc_parts = []
    doc_parts.append("# JAY Database — Stored Procedures Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Stored Procedures: {len(procs)}")
    doc_parts.append(f"# Database: JAY (SQL Server 2019, Edgeworks POS)")
    doc_parts.append("")
    
    doc_parts.append("## Stored Procedure Index")
    for p in procs:
        doc_parts.append(f"  - [{p[0]}].[{p.name}] (Modified: {p.modify_date})")
    doc_parts.append("")
    
    for p in procs:
        doc_parts.append(f"\n{'='*70}")
        doc_parts.append(f"## Stored Procedure: [{p[0]}].[{p.name}]")
        doc_parts.append(f"   Created: {p.create_date} | Modified: {p.modify_date}")
        doc_parts.append(f"{'='*70}")
        
        # Parameters
        try:
            cursor.execute(f"""
                SELECT 
                    pr.name, TYPE_NAME(pr.user_type_id) as type_name,
                    pr.max_length, pr.is_output
                FROM sys.parameters pr
                WHERE pr.object_id = OBJECT_ID('[{p[0]}].[{p.name}]')
                ORDER BY pr.parameter_id
            """)
            params = cursor.fetchall()
            if params:
                doc_parts.append("Parameters:")
                for param in params:
                    direction = "OUTPUT" if param.is_output else "INPUT"
                    doc_parts.append(f"  - {param.name} {param.type_name}({param.max_length}) [{direction}]")
        except:
            pass
        
        doc_parts.append("\nSource Code:")
        doc_parts.append("```sql")
        if p.definition:
            doc_parts.append(p.definition)
        else:
            doc_parts.append("-- (encrypted or unavailable)")
        doc_parts.append("```")
    
    return "\n".join(doc_parts), len(procs)


def extract_functions(cursor):
    """Extract all user-defined functions with their source code."""
    cursor.execute("""
        SELECT 
            SCHEMA_NAME(o.schema_id) as [schema],
            o.name,
            o.type_desc,
            o.create_date,
            o.modify_date,
            m.definition
        FROM sys.objects o
        JOIN sys.sql_modules m ON o.object_id = m.object_id
        WHERE o.type IN ('FN','IF','TF')
        AND o.is_ms_shipped = 0
        ORDER BY o.name
    """)
    funcs = cursor.fetchall()
    
    doc_parts = []
    doc_parts.append("# JAY Database — Functions Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Functions: {len(funcs)}")
    doc_parts.append(f"# Database: JAY (SQL Server 2019, Edgeworks POS)")
    doc_parts.append("")
    
    doc_parts.append("## Function Index")
    for f in funcs:
        doc_parts.append(f"  - [{f[0]}].[{f.name}] ({f.type_desc}) Modified: {f.modify_date}")
    doc_parts.append("")
    
    for f in funcs:
        doc_parts.append(f"\n{'='*70}")
        doc_parts.append(f"## Function: [{f[0]}].[{f.name}]")
        doc_parts.append(f"   Type: {f.type_desc} | Created: {f.create_date} | Modified: {f.modify_date}")
        doc_parts.append(f"{'='*70}")
        doc_parts.append("\nSource Code:")
        doc_parts.append("```sql")
        if f.definition:
            doc_parts.append(f.definition)
        else:
            doc_parts.append("-- (encrypted or unavailable)")
        doc_parts.append("```")
    
    return "\n".join(doc_parts), len(funcs)


def extract_views(cursor):
    """Extract all views with their source code."""
    cursor.execute("""
        SELECT 
            SCHEMA_NAME(o.schema_id) as [schema],
            o.name,
            o.create_date,
            o.modify_date,
            m.definition
        FROM sys.views o
        JOIN sys.sql_modules m ON o.object_id = m.object_id
        WHERE o.is_ms_shipped = 0
        ORDER BY o.name
    """)
    views = cursor.fetchall()
    
    doc_parts = []
    doc_parts.append("# JAY Database — Views Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Views: {len(views)}")
    doc_parts.append(f"# Database: JAY (SQL Server 2019, Edgeworks POS)")
    doc_parts.append("")
    
    for v in views:
        doc_parts.append(f"\n{'='*70}")
        doc_parts.append(f"## View: [{v[0]}].[{v.name}]")
        doc_parts.append(f"   Created: {v.create_date} | Modified: {v.modify_date}")
        doc_parts.append(f"{'='*70}")
        doc_parts.append("```sql")
        if v.definition:
            doc_parts.append(v.definition)
        else:
            doc_parts.append("-- (encrypted or unavailable)")
        doc_parts.append("```")
    
    return "\n".join(doc_parts), len(views)


def extract_triggers(cursor):
    """Extract all triggers with their source code."""
    cursor.execute("""
        SELECT 
            OBJECT_SCHEMA_NAME(t.parent_id) as [schema],
            t.name as trigger_name,
            OBJECT_NAME(t.parent_id) as table_name,
            t.create_date,
            m.definition
        FROM sys.triggers t
        JOIN sys.sql_modules m ON t.object_id = m.object_id
        WHERE t.is_ms_shipped = 0 AND t.parent_id > 0
        ORDER BY t.name
    """)
    triggers = cursor.fetchall()
    
    if not triggers:
        return "", 0
    
    doc_parts = []
    doc_parts.append("# JAY Database — Triggers Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Triggers: {len(triggers)}")
    doc_parts.append("")
    
    for tr in triggers:
        doc_parts.append(f"\n{'='*70}")
        doc_parts.append(f"## Trigger: [{tr[0]}].[{tr.trigger_name}] ON [{tr.table_name}]")
        doc_parts.append(f"{'='*70}")
        doc_parts.append("```sql")
        doc_parts.append(tr.definition if tr.definition else "-- (encrypted)")
        doc_parts.append("```")
    
    return "\n".join(doc_parts), len(triggers)


def extract_indexes(cursor):
    """Extract index information for performance analysis."""
    cursor.execute("""
        SELECT 
            OBJECT_SCHEMA_NAME(i.object_id) as [schema],
            OBJECT_NAME(i.object_id) as table_name,
            i.name as index_name,
            i.type_desc,
            i.is_unique,
            i.is_primary_key,
            STUFF((
                SELECT ', ' + COL_NAME(ic2.object_id, ic2.column_id)
                FROM sys.index_columns ic2
                WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id
                ORDER BY ic2.key_ordinal
                FOR XML PATH('')
            ), 1, 2, '') as columns
        FROM sys.indexes i
        WHERE i.object_id > 100 
        AND OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
        AND i.name IS NOT NULL
        ORDER BY OBJECT_NAME(i.object_id), i.index_id
    """)
    indexes = cursor.fetchall()
    
    doc_parts = []
    doc_parts.append("# JAY Database — Indexes Reference")
    doc_parts.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc_parts.append(f"# Total Indexes: {len(indexes)}")
    doc_parts.append("")
    
    current_table = ""
    for ix in indexes:
        if ix.table_name != current_table:
            current_table = ix.table_name
            doc_parts.append(f"\n## Table: [{ix[0]}].[{ix.table_name}]")
        
        pk = " [PRIMARY KEY]" if ix.is_primary_key else ""
        uniq = " [UNIQUE]" if ix.is_unique and not ix.is_primary_key else ""
        doc_parts.append(f"  - {ix.index_name} ({ix.type_desc}){pk}{uniq}: {ix.columns}")
    
    return "\n".join(doc_parts), len(indexes)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = connect()
    cursor = conn.cursor()
    
    print(f"Connected to JAY database on localhost")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*50}")
    
    extractors = [
        ("JAY_DB_Tables_Schema", "Tables & Columns", extract_tables),
        ("JAY_DB_Stored_Procedures", "Stored Procedures", extract_stored_procedures),
        ("JAY_DB_Functions", "Functions", extract_functions),
        ("JAY_DB_Views", "Views", extract_views),
        ("JAY_DB_Triggers", "Triggers", extract_triggers),
        ("JAY_DB_Indexes", "Indexes", extract_indexes),
    ]
    
    total_files = 0
    summary = []
    
    for filename, label, extractor in extractors:
        try:
            content, count = extractor(cursor)
            if count == 0:
                print(f"  {label}: 0 found, skipping")
                summary.append(f"  - {label}: 0")
                continue
            
            filepath = os.path.join(OUTPUT_DIR, f"{filename}.txt")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            size_kb = os.path.getsize(filepath) / 1024
            print(f"  ✅ {label}: {count} items -> {filename}.txt ({size_kb:.1f} KB)")
            summary.append(f"  - {label}: {count} items ({size_kb:.1f} KB)")
            total_files += 1
        except Exception as e:
            print(f"  ❌ {label}: ERROR - {e}")
            summary.append(f"  - {label}: ERROR - {e}")
    
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"✅ Done! {total_files} KB documents saved to {OUTPUT_DIR}")
    print(f"\nSummary:")
    for s in summary:
        print(s)
    print(f"\nNext step: Upload these to the Knowledge Base and run 'Train AI' to index them.")

if __name__ == "__main__":
    main()
