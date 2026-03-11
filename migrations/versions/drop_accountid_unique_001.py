"""drop_accountid_unique_constraint

Drop the UNIQUE constraint on Users.AccountID to allow multiple NULL values.
SQL Server treats NULLs as equal in unique constraints, causing failures
when multiple portal users are created without an AccountID.

Revision ID: drop_accountid_uq001
Revises: f8257191df5c
Create Date: 2025-07-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'drop_accountid_uq001'
down_revision: Union[str, Sequence[str], None] = 'f8257191df5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the UNIQUE constraint on Users.AccountID."""
    # The constraint name on SQL Server is auto-generated: UQ__Users__349DA587A0CD4E4A
    # Use raw SQL since constraint name is server-generated
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'mssql':
        # SQL Server: find and drop the constraint by column name
        conn.execute(sa.text("""
            DECLARE @constraint_name NVARCHAR(256)
            SELECT @constraint_name = tc.CONSTRAINT_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON tc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE tc.TABLE_SCHEMA = 'app'
              AND tc.TABLE_NAME = 'Users'
              AND tc.CONSTRAINT_TYPE = 'UNIQUE'
              AND ccu.COLUMN_NAME = 'AccountID'
            
            IF @constraint_name IS NOT NULL
            BEGIN
                EXEC('ALTER TABLE app.Users DROP CONSTRAINT ' + @constraint_name)
            END
        """))
        # Add a non-unique index for performance
        conn.execute(sa.text(
            "CREATE INDEX ix_users_accountid ON app.Users (AccountID) WHERE AccountID IS NOT NULL"
        ))
    elif dialect == 'postgresql':
        # PostgreSQL: drop unique constraint (NULLs are already distinct in PG, but align the schema)
        op.drop_constraint('Users_AccountID_key', 'Users', type_='unique')
        op.create_index('ix_users_accountid', 'Users', ['AccountID'], unique=False)
    else:
        # SQLite: no constraint alteration needed (NULLs are distinct)
        pass


def downgrade() -> None:
    """Restore the UNIQUE constraint on Users.AccountID."""
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'mssql':
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_accountid ON app.Users"))
        conn.execute(sa.text("ALTER TABLE app.Users ADD CONSTRAINT UQ_Users_AccountID UNIQUE (AccountID)"))
    elif dialect == 'postgresql':
        op.drop_index('ix_users_accountid', table_name='Users')
        op.create_unique_constraint('Users_AccountID_key', 'Users', ['AccountID'])
