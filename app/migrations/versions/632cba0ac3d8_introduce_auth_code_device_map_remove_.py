"""introduce auth_code_device_map; remove devices.auth_code_id; add relationships

Revision ID: 632cba0ac3d8
Revises: f0d1b164ea3a
Create Date: 2025-09-23 13:49:53.512264

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '632cba0ac3d8'
down_revision = 'f0d1b164ea3a'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 创建中间表（若不存在）
    if not insp.has_table('auth_code_device_map'):
        op.create_table(
            'auth_code_device_map',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('auth_code_id', sa.Integer(), nullable=False),
            sa.Column('device_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['auth_code_id'], ['auth_codes.id']),
            sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('auth_code_id', 'device_id', name='uq_auth_code_device'),
        )
        op.create_index('ix_auth_code_device_map_auth_code_id', 'auth_code_device_map', ['auth_code_id'], unique=False)
        op.create_index('ix_auth_code_device_map_device_id', 'auth_code_device_map', ['device_id'], unique=True)

    # 从 devices 表移除旧的 auth_code_id 列（若存在）
    device_cols = [c['name'] if isinstance(c, dict) else c.name for c in insp.get_columns('devices')]
    if 'auth_code_id' in device_cols:
        with op.batch_alter_table('devices') as batch_op:
            batch_op.drop_column('auth_code_id')


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 回滚 devices.auth_code_id（若缺失）
    device_cols = [c['name'] if isinstance(c, dict) else c.name for c in insp.get_columns('devices')]
    if 'auth_code_id' not in device_cols:
        with op.batch_alter_table('devices') as batch_op:
            batch_op.add_column(sa.Column('auth_code_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(None, 'auth_codes', ['auth_code_id'], ['id'])

    # 删除中间表（若存在）
    if insp.has_table('auth_code_device_map'):
        try:
            op.drop_index('ix_auth_code_device_map_device_id', table_name='auth_code_device_map')
        except Exception:
            pass
        try:
            op.drop_index('ix_auth_code_device_map_auth_code_id', table_name='auth_code_device_map')
        except Exception:
            pass
        op.drop_table('auth_code_device_map')