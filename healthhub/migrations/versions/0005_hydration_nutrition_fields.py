"""add hydration, sugar and flexible nutrition display fields

Revision ID: 0005_hydration_nutrition_fields
Revises: 0004_planning_recurrence
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_hydration_nutrition_fields"
down_revision = "0004_planning_recurrence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("nutrition_display_fields", sa.String(length=100), nullable=True))

    op.execute(
        """
        UPDATE profiles
        SET nutrition_display_fields = CASE nutrition_display_mode
            WHEN 'balanced' THEN 'calories,protein'
            WHEN 'detailed' THEN 'calories,protein,carbohydrates,fat'
            ELSE 'calories'
        END
        """
    )

    with op.batch_alter_table("profiles") as batch:
        batch.alter_column("nutrition_display_fields", nullable=False, server_default="calories")

    with op.batch_alter_table("foods") as batch:
        batch.add_column(sa.Column("sugar_g", sa.Float(), nullable=True))
    with op.batch_alter_table("diary_entries") as batch:
        batch.add_column(sa.Column("sugar_g", sa.Float(), nullable=True))
    with op.batch_alter_table("planned_entries") as batch:
        batch.add_column(sa.Column("sugar_g", sa.Float(), nullable=True))

    op.create_table(
        "water_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_water_entries_profile_id", "water_entries", ["profile_id"])
    op.create_index("ix_water_entries_consumed_at", "water_entries", ["consumed_at"])
    op.create_index("ix_water_entries_source", "water_entries", ["source"])
    op.create_index("ix_water_profile_consumed", "water_entries", ["profile_id", "consumed_at"])


def downgrade() -> None:
    op.drop_index("ix_water_profile_consumed", table_name="water_entries")
    op.drop_index("ix_water_entries_source", table_name="water_entries")
    op.drop_index("ix_water_entries_consumed_at", table_name="water_entries")
    op.drop_index("ix_water_entries_profile_id", table_name="water_entries")
    op.drop_table("water_entries")

    with op.batch_alter_table("planned_entries") as batch:
        batch.drop_column("sugar_g")
    with op.batch_alter_table("diary_entries") as batch:
        batch.drop_column("sugar_g")
    with op.batch_alter_table("foods") as batch:
        batch.drop_column("sugar_g")
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("nutrition_display_fields")
