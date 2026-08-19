"""add product identity, canonical nutrition provenance and FoodHub mappings"""

from alembic import op
import sqlalchemy as sa

revision = "0007_food_capture_products"
down_revision = "0006_food_library_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("foods") as batch:
        batch.add_column(sa.Column("serving_quantity", sa.Float(), nullable=True))
        batch.add_column(sa.Column("nutrition_basis", sa.String(length=20), nullable=True, server_default="per_serving"))
        batch.add_column(sa.Column("canonical_quantity", sa.Float(), nullable=True))
        batch.add_column(sa.Column("canonical_unit", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("package_size", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("source_provider", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("source_identifier", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("source_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("verification_status", sa.String(length=30), nullable=True, server_default="unverified"))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("ocr_confidence", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("image_url", sa.String(length=500), nullable=True))
    op.execute("UPDATE foods SET serving_quantity=serving_grams WHERE serving_grams IS NOT NULL")
    op.execute("UPDATE foods SET nutrition_basis='per_serving' WHERE nutrition_basis IS NULL")
    op.execute("UPDATE foods SET verification_status=CASE WHEN data_quality='packaging_confirmed' THEN 'verified' ELSE 'unverified' END WHERE verification_status IS NULL")

    op.create_table(
        "food_identifiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("identifier_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier_type", "value", name="uq_food_identifier_type_value"),
    )
    op.create_index("ix_food_identifiers_food_id", "food_identifiers", ["food_id"])
    op.create_index("ix_food_identifiers_value", "food_identifiers", ["value"])

    op.create_table(
        "foodhub_recipe_links",
        sa.Column("foodhub_recipe_id", sa.String(length=120), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("recipe_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nutrition_status", sa.String(length=30), nullable=False, server_default="unavailable"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("foodhub_recipe_id"),
        sa.UniqueConstraint("food_id", name="uq_foodhub_recipe_links_food_id"),
    )

    op.create_table(
        "foodhub_ingredient_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_key", sa.String(length=200), nullable=False),
        sa.Column("ingredient_name", sa.String(length=200), nullable=False),
        sa.Column("food_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingredient_key", name="uq_foodhub_ingredient_mappings_key"),
    )

    with op.batch_alter_table("import_batches") as batch:
        batch.add_column(sa.Column("source_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("import_batches") as batch:
        batch.drop_column("source_name")
    op.drop_table("foodhub_ingredient_mappings")
    op.drop_table("foodhub_recipe_links")
    op.drop_index("ix_food_identifiers_value", table_name="food_identifiers")
    op.drop_index("ix_food_identifiers_food_id", table_name="food_identifiers")
    op.drop_table("food_identifiers")
    with op.batch_alter_table("foods") as batch:
        for column in ("image_url", "ocr_confidence", "verified_at", "verification_status", "source_url", "source_identifier", "source_provider", "package_size", "canonical_unit", "canonical_quantity", "nutrition_basis", "serving_quantity"):
            batch.drop_column(column)
