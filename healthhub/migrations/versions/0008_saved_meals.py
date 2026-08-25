"""add reusable saved meals

Revision ID: 0008_saved_meals
Revises: 0007_food_capture_products
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_saved_meals"
down_revision = "0007_food_capture_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_meals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_meal_period", sa.String(length=20), nullable=False, server_default="lunch"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_meals_profile_id", "saved_meals", ["profile_id"])
    op.create_index("ix_saved_meals_name", "saved_meals", ["name"])
    op.create_index("ix_saved_meals_archived", "saved_meals", ["archived"])
    op.create_table(
        "saved_meal_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("saved_meal_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("servings", sa.Float(), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["saved_meal_id"], ["saved_meals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_meal_items_saved_meal_id", "saved_meal_items", ["saved_meal_id"])
    op.create_index("ix_saved_meal_items_food_id", "saved_meal_items", ["food_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_meal_items_food_id", table_name="saved_meal_items")
    op.drop_index("ix_saved_meal_items_saved_meal_id", table_name="saved_meal_items")
    op.drop_table("saved_meal_items")
    op.drop_index("ix_saved_meals_archived", table_name="saved_meals")
    op.drop_index("ix_saved_meals_name", table_name="saved_meals")
    op.drop_index("ix_saved_meals_profile_id", table_name="saved_meals")
    op.drop_table("saved_meals")
