"""add planned entries and recurrence rules

Revision ID: 0003_planning_recurrence
Revises: 0002_foods_diary
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_planning_recurrence"
down_revision = "0002_foods_diary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurrence_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("meal_period", sa.String(length=20), nullable=False, server_default="snack"),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("local_time", sa.String(length=5), nullable=False, server_default="12:00"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurrence_rules_profile_id", "recurrence_rules", ["profile_id"])
    op.create_index("ix_recurrence_rules_food_id", "recurrence_rules", ["food_id"])
    op.create_index("ix_recurrence_rules_frequency", "recurrence_rules", ["frequency"])
    op.create_index("ix_recurrence_rules_start_date", "recurrence_rules", ["start_date"])
    op.create_index("ix_recurrence_rules_active", "recurrence_rules", ["active"])

    op.create_table(
        "planned_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=True),
        sa.Column("recurrence_rule_id", sa.String(length=36), nullable=True),
        sa.Column("meal_period", sa.String(length=20), nullable=False, server_default="snack"),
        sa.Column("planned_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("food_name", sa.String(length=180), nullable=False),
        sa.Column("serving_name", sa.String(length=100), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbohydrates_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="healthhub"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("consumed_diary_entry_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["consumed_diary_entry_id"], ["diary_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recurrence_rule_id"], ["recurrence_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planned_entries_profile_id", "planned_entries", ["profile_id"])
    op.create_index("ix_planned_entries_food_id", "planned_entries", ["food_id"])
    op.create_index("ix_planned_entries_recurrence_rule_id", "planned_entries", ["recurrence_rule_id"])
    op.create_index("ix_planned_entries_meal_period", "planned_entries", ["meal_period"])
    op.create_index("ix_planned_entries_planned_for", "planned_entries", ["planned_for"])
    op.create_index("ix_planned_entries_status", "planned_entries", ["status"])
    op.create_index("ix_planned_profile_date", "planned_entries", ["profile_id", "planned_for"])
    op.create_index("ix_planned_profile_status", "planned_entries", ["profile_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_planned_profile_status", table_name="planned_entries")
    op.drop_index("ix_planned_profile_date", table_name="planned_entries")
    op.drop_index("ix_planned_entries_status", table_name="planned_entries")
    op.drop_index("ix_planned_entries_planned_for", table_name="planned_entries")
    op.drop_index("ix_planned_entries_meal_period", table_name="planned_entries")
    op.drop_index("ix_planned_entries_recurrence_rule_id", table_name="planned_entries")
    op.drop_index("ix_planned_entries_food_id", table_name="planned_entries")
    op.drop_index("ix_planned_entries_profile_id", table_name="planned_entries")
    op.drop_table("planned_entries")
    op.drop_index("ix_recurrence_rules_active", table_name="recurrence_rules")
    op.drop_index("ix_recurrence_rules_start_date", table_name="recurrence_rules")
    op.drop_index("ix_recurrence_rules_frequency", table_name="recurrence_rules")
    op.drop_index("ix_recurrence_rules_food_id", table_name="recurrence_rules")
    op.drop_index("ix_recurrence_rules_profile_id", table_name="recurrence_rules")
    op.drop_table("recurrence_rules")
