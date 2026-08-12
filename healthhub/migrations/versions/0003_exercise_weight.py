"""add exercise and weight entries

Revision ID: 0003_exercise_weight
Revises: 0002_foods_diary
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_exercise_weight"
down_revision = "0002_foods_diary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercise_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("activity_name", sa.String(length=120), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("calories_burned", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exercise_entries_profile_id", "exercise_entries", ["profile_id"])
    op.create_index("ix_exercise_entries_activity_name", "exercise_entries", ["activity_name"])
    op.create_index("ix_exercise_entries_completed_at", "exercise_entries", ["completed_at"])
    op.create_index("ix_exercise_entries_source", "exercise_entries", ["source"])
    op.create_index("ix_exercise_profile_completed", "exercise_entries", ["profile_id", "completed_at"])

    op.create_table(
        "weight_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weight_entries_profile_id", "weight_entries", ["profile_id"])
    op.create_index("ix_weight_entries_measured_at", "weight_entries", ["measured_at"])
    op.create_index("ix_weight_entries_source", "weight_entries", ["source"])
    op.create_index("ix_weight_profile_measured", "weight_entries", ["profile_id", "measured_at"])


def downgrade() -> None:
    op.drop_index("ix_weight_profile_measured", table_name="weight_entries")
    op.drop_index("ix_weight_entries_source", table_name="weight_entries")
    op.drop_index("ix_weight_entries_measured_at", table_name="weight_entries")
    op.drop_index("ix_weight_entries_profile_id", table_name="weight_entries")
    op.drop_table("weight_entries")
    op.drop_index("ix_exercise_profile_completed", table_name="exercise_entries")
    op.drop_index("ix_exercise_entries_source", table_name="exercise_entries")
    op.drop_index("ix_exercise_entries_completed_at", table_name="exercise_entries")
    op.drop_index("ix_exercise_entries_activity_name", table_name="exercise_entries")
    op.drop_index("ix_exercise_entries_profile_id", table_name="exercise_entries")
    op.drop_table("exercise_entries")
