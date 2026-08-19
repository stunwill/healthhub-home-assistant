"""extend food library, composites, preferences and spreadsheet imports"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0006_food_library_imports"
down_revision = "0005_hydration_nutrition_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("foods") as batch:
        batch.add_column(sa.Column("category", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("serving_unit", sa.String(length=40), nullable=True, server_default="serving"))
        for name in ("saturated_fat_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg"):
            batch.add_column(sa.Column(name, sa.Float(), nullable=True))
        batch.add_column(sa.Column("data_quality", sa.String(length=40), nullable=True, server_default="user_entered"))
    op.execute("UPDATE foods SET serving_unit = 'serving' WHERE serving_unit IS NULL")
    op.execute("UPDATE foods SET data_quality = CASE WHEN source = 'nutrition_label' THEN 'packaging_confirmed' ELSE 'user_entered' END WHERE data_quality IS NULL")
    with op.batch_alter_table("diary_entries") as batch:
        for name in ("saturated_fat_g", "fibre_g", "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "cholesterol_mg", "alcohol_g", "caffeine_mg"):
            batch.add_column(sa.Column(name, sa.Float(), nullable=True))
    op.create_index("ix_foods_category", "foods", ["category"])
    op.create_table(
        "food_components",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("composite_food_id", sa.String(length=36), nullable=False),
        sa.Column("component_food_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="serving"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["composite_food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["component_food_id"], ["foods.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_components_composite_food_id", "food_components", ["composite_food_id"])
    op.create_index("ix_food_components_component_food_id", "food_components", ["component_food_id"])
    op.create_table(
        "food_preferences",
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("favourite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_quantity", sa.Float(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", "food_id"),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="spreadsheet"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "import_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_items_batch_id", "import_items", ["batch_id"])

    foods = sa.table("foods", sa.column("id", sa.String), sa.column("name", sa.String), sa.column("category", sa.String), sa.column("serving_name", sa.String), sa.column("serving_unit", sa.String), sa.column("calories", sa.Float), sa.column("source", sa.String), sa.column("data_quality", sa.String), sa.column("kind", sa.String), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime))
    seed = [
        ("Nutri-Grain", "Breakfast cereal", "80 g", "g", 310, "estimated"), ("Almond milk", "Milk / Drink / Ingredient", "250 mL", "mL", 60, "estimated"),
        ("White bread / white toast", "Bread", "1 slice", "slice", 90, "estimated"), ("Butter", "Spread / Ingredient", "10 g", "g", 72, "estimated"),
        ("Honey", "Spread / Ingredient", "10 g", "g", 30, "estimated"), ("Raw sugar", "Sugar / Ingredient", "2 teaspoons / 8 g", "teaspoon", 32, "estimated"),
        ("Iced coffee with almond milk and raw sugar", "Drink", "1 drink", "drink", 90, "estimated"), ("Iced matcha with almond milk and raw sugar", "Drink", "1 drink", "drink", 100, "estimated"),
        ("Meat pie", "Meal / Savoury", "1 pie", "pie", 450, "estimated"), ("Lamington", "Snack / Dessert", "58 g", "g", 189, "packaging_confirmed"),
        ("Nestlé Roll-Up", "Snack", "1 Roll-Up / 15 g", "item", 55, "packaging_confirmed"), ("Cheezels mini multipack", "Snack", "1 small packet", "packet", 100, "estimated"),
        ("Tim Tam", "Snack / Biscuit", "1 biscuit", "biscuit", 95, "estimated"), ("Magnum ice cream", "Dessert / Snack", "1 ice cream", "item", 270, "estimated"),
        ("Red wine", "Alcohol", "1 glass", "glass", 213, "estimated"), ("Corona beer", "Alcohol", "1 bottle", "bottle", 140, "estimated"),
        ("Pesto pasta with peas, lactose-free cream and parmesan", "Meal / Dinner", "1 serving", "serving", 700, "estimated"),
    ]
    now = datetime.now(timezone.utc)
    op.bulk_insert(foods, [{"id": f"seed-{index:02d}", "name": name, "category": category, "serving_name": serving_name, "serving_unit": unit, "calories": calories, "source": "healthhub_seed", "data_quality": quality, "kind": "drink" if category in {"Drink", "Alcohol"} else "food", "created_at": now, "updated_at": now} for index, (name, category, serving_name, unit, calories, quality) in enumerate(seed, 1)])
    op.execute("UPDATE foods SET protein_g=2.6, carbohydrates_g=35.8, fat_g=3.2, saturated_fat_g=2.8, sugar_g=21.6, fibre_g=2.2, sodium_mg=140 WHERE id='seed-10'")
    op.execute("UPDATE foods SET protein_g=0.1, carbohydrates_g=11.5, fat_g=0.5, saturated_fat_g=0.2, sugar_g=4.2, fibre_g=0.9, sodium_mg=3 WHERE id='seed-11'")


def downgrade() -> None:
    op.drop_index("ix_import_items_batch_id", table_name="import_items")
    op.drop_table("import_items")
    op.drop_table("import_batches")
    op.drop_table("food_preferences")
    op.drop_index("ix_food_components_component_food_id", table_name="food_components")
    op.drop_index("ix_food_components_composite_food_id", table_name="food_components")
    op.drop_table("food_components")
    op.drop_index("ix_foods_category", table_name="foods")
    with op.batch_alter_table("diary_entries") as batch:
        for name in ("caffeine_mg", "alcohol_g", "cholesterol_mg", "potassium_mg", "iron_mg", "calcium_mg", "sodium_mg", "fibre_g", "saturated_fat_g"):
            batch.drop_column(name)
    with op.batch_alter_table("foods") as batch:
        batch.drop_column("data_quality")
        for name in ("caffeine_mg", "alcohol_g", "cholesterol_mg", "potassium_mg", "iron_mg", "calcium_mg", "sodium_mg", "fibre_g", "saturated_fat_g"):
            batch.drop_column(name)
        batch.drop_column("serving_unit")
        batch.drop_column("category")
