import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from alembic import autogenerate
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from app.models import Base

engine = create_engine("sqlite:///:memory:")
ctx = MigrationContext.configure(engine.connect())
m_ops = autogenerate.produce_migrations(ctx, Base.metadata)

upgrade_code = autogenerate.render_python_code(m_ops.upgrade_ops)
downgrade_code = autogenerate.render_python_code(m_ops.downgrade_ops)

migration_content = f'''"""Initial full production schema setup

Revision ID: bd1e5a3970b2
Revises:
Create Date: 2026-11-09 22:57:23.601675

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd1e5a3970b2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
{upgrade_code}


def downgrade() -> None:
{downgrade_code}
'''

target_file = BACKEND_DIR / "alembic" / "versions" / "bd1e5a3970b2_initial_schema_setup.py"
with open(target_file, "w", encoding="utf-8") as f:
    f.write(migration_content)

print(f"Successfully generated initial full production migration at {target_file}")
