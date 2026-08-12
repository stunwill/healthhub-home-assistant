"""add foods and diary entries

Revision ID: 0002_foods_diary
Revises: 0001_profiles
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_foods_diary"
down_revision = "0001_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="food"),
        sa.Column("serving_name", sa.String(length=100), nullable=False, server_default="1 serve"),
        sa.Column("serving_grams", sa.Float(), nullable=True),
        sa.Column("energy_kj", sa.Float(), nullable=True),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbohydrates_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("favourite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_foods_name", "foods", ["name"])
    op.create_index("ix_foods_brand", "foods", ["brand"])
    op.create_index("ix_foods_kind", "foods", ["kind"])
    op.create_index("ix_foods_source", "foods", ["source"])
    op.create_index("ix_foods_favourite", "foods", ["favourite"])
    op.create_index("ix_foods_archived", "foods", ["archived"])
    op.create_index("ix_foods_search", "foods", ["archived", "name", "brand"])

    op.create_table(
        "diary_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=True),
        sa.Column("meal_period", sa.String(length=20), nullable=False, server_default="snack"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("food_name", sa.String(length=180), nullable=False),
        sa.Column("serving_name", sa.String(length=100), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbohydrates_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="healthhub"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diary_entries_profile_id", "diary_entries", ["profile_id"])
    op.create_index("ix_diary_entries_food_id", "diary_entries", ["food_id"])
    op.create_index("ix_diary_entries_meal_period", "diary_entries", ["meal_period"])
    op.create_index("ix_diary_entries_consumed_at", "diary_entries", ["consumed_at"])
    op.create_index("ix_diary_profile_consumed", "diary_entries", ["profile_id", "consumed_at"])


def downgrade() -> None:
    op.drop_index("ix_diary_profile_consumed", table_name="diary_entries")
    op.drop_index("ix_diary_entries_consumed_at", table_name="diary_entries")
    op.drop_index("ix_diary_entries_meal_period", table_name="diary_entries")
    op.drop_index("ix_diary_entries_food_id", table_name="diary_entries")
    op.drop_index("ix_diary_entries_profile_id", table_name="diary_entries")
    op.drop_table("diary_entries")
    op.drop_index("ix_foods_search", table_name="foods")
    op.drop_index("ix_foods_archived", table_name="foods")
    op.drop_index("ix_foods_favourite", table_name="foods")
    op.drop_index("ix_foods_source", table_name="foods")
    op.drop_index("ix_foods_kind", table_name="foods")
    op.drop_index("ix_foods_brand", table_name="foods")
    op.drop_index("ix_foods_name", table_name="foods")
    op.drop_table("foods")
