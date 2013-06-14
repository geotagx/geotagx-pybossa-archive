"""Rename app to project

Revision ID: 1dda7eb046c3
Revises: 3f113ca6c186
Create Date: 2013-06-14 11:25:17.716272

"""

# revision identifiers, used by Alembic.
revision = '1dda7eb046c3'
down_revision = '3f113ca6c186'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.rename_table('app', 'project')
    op.alter_column(table_name='featured', column_name='app_id', new_column_name='project_id')
    op.alter_column(table_name='task', column_name='app_id', new_column_name='project_id')
    op.alter_column(table_name='task_run', column_name='app_id', new_column_name='project_id')


def downgrade():
    op.rename_table('project', 'app')
    op.alter_column(table_name='featured', column_name='project_id', new_column_name='app_id')
    op.alter_column(table_name='task', column_name='project_id', new_column_name='app_id')
    op.alter_column(table_name='task_run', column_name='project_id', new_column_name='app_id')
