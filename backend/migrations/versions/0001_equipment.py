"""M3 assets, sampled telemetry and deduplicated device alarms."""
from alembic import op
import sqlalchemy as sa
revision = "0001_equipment"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("devices",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("device_code", sa.String(32), nullable=False, unique=True),
        sa.Column("device_name", sa.String(100), nullable=False),
        sa.Column("device_type", sa.String(32), nullable=False),
        sa.Column("building_id", sa.String(32), nullable=False),
        sa.Column("area_id", sa.String(64), nullable=False),
        *[sa.Column(name, sa.Float(), nullable=False) for name in ("position_x", "position_y", "position_z", "health_score", "runtime_hours", "rated_power", "rated_rpm", "rated_current", "rated_capacity")],
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("install_date", sa.Date(), nullable=False),
        sa.Column("last_maintenance", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_devices_device_type", "devices", ["device_type"])
    op.create_table("device_telemetry",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(32), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        *[sa.Column(name, sa.Float(), nullable=False) for name in ("temperature", "vibration", "current", "rpm", "efficiency", "health_score")],
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("session_id", "revision", "device_id", name="uq_telemetry_snapshot"))
    op.create_index("ix_telemetry_device_time", "device_telemetry", ["device_id", "timestamp"])
    op.create_table("device_alarms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(32), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("alarm_type", sa.String(32), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_active_device_alarm", "device_alarms", ["device_id", "alarm_type"], unique=True, postgresql_where=sa.text("status = 'active'"))

def downgrade():
    op.drop_table("device_alarms")
    op.drop_table("device_telemetry")
    op.drop_table("devices")
