from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_profiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("colour", sa.String(length=20), nullable=True),
        sa.Column("avatar", sa.String(length=500), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("starting_weight_kg", sa.Float(), nullable=True),
        sa.Column("goal_weight_kg", sa.Float(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("daily_calorie_target", sa.Integer(), nullable=False),
        sa.Column("weekly_exercise_minutes_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hydration_target_ml", sa.Integer(), nullable=True),
        sa.Column("exercise_credit_mode", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("exercise_credit_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nutrition_display_mode", sa.String(length=20), nullable=False, server_default="simple"),
        sa.Column("timezone", sa.String(length=100), nullable=False, server_default="Australia/Melbourne"),
        sa.Column("measurement_units", sa.String(length=20), nullable=False, server_default="metric"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("daily_calorie_target > 0", name="ck_profiles_calorie_target_positive"),
        sa.CheckConstraint("exercise_credit_percentage >= 0 AND exercise_credit_percentage <= 100", name="ck_profiles_exercise_credit_percentage"),
    )
    op.create_index("ix_profiles_display_name", "profiles", ["display_name"])
    op.create_index("ix_profiles_archived", "profiles", ["archived"])


def downgrade() -> None:
    op.drop_index("ix_profiles_archived", table_name="profiles")
    op.drop_index("ix_profiles_display_name", table_name="profiles")
    op.drop_table("profiles")
