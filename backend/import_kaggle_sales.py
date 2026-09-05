import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import DailyDemand, Product


# ============================================================
# CONFIG
# ============================================================

CSV_FILE = "train.csv"

DATABASE_URL = (
    os.getenv("DATABASE_URL", "postgresql://postgres:postgres@timescaledb:5432/food_waste_db")
)

# Import one real store to keep the dataset manageable.
STORE_NUMBER = 1

# Import the most recent 365 days available in the Kaggle data.
DAYS_TO_IMPORT = 365


# ============================================================
# KAGGLE CATEGORY -> EXISTING PRODUCT
# ============================================================

# Your existing products:
#
# Product 1 = Milk
# Product 2 = Fresh Berries
# Product 3 = Raw Poultry
#
# We only map categories where the mapping is defensible.
#
# DAIRY -> Milk
# POULTRY -> Raw Poultry

FAMILY_TO_PRODUCT = {
    "DAIRY": 1,
    "POULTRY": 3,
}


# ============================================================
# DATABASE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ============================================================
# LOAD KAGGLE DATA
# ============================================================

print()
print("=" * 60)
print("KAGGLE SALES IMPORT")
print("=" * 60)
print()

print("Reading train.csv...")

df = pd.read_csv(CSV_FILE)

print(f"Rows loaded: {len(df):,}")
print(f"Columns found: {list(df.columns)}")


# ============================================================
# CHECK COLUMNS
# ============================================================

required_columns = {
    "date",
    "store_nbr",
    "family",
    "sales",
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise ValueError(
        "The Kaggle CSV is missing these columns: "
        + ", ".join(sorted(missing_columns))
    )


# ============================================================
# CLEAN
# ============================================================

df["date"] = pd.to_datetime(
    df["date"],
    errors="coerce",
)

df["sales"] = pd.to_numeric(
    df["sales"],
    errors="coerce",
)

df = df.dropna(
    subset=["date", "sales"]
)


# ============================================================
# SELECT ONE STORE
# ============================================================

df = df[
    df["store_nbr"] == STORE_NUMBER
].copy()

print(
    f"Rows for store {STORE_NUMBER}: "
    f"{len(df):,}"
)


# ============================================================
# SELECT RELEVANT FOOD CATEGORIES
# ============================================================

df = df[
    df["family"].isin(
        FAMILY_TO_PRODUCT.keys()
    )
].copy()

if df.empty:
    raise ValueError(
        "No DAIRY or POULTRY records were found."
    )

print(
    "Categories selected: "
    + ", ".join(
        sorted(df["family"].unique())
    )
)


# ============================================================
# SELECT MOST RECENT 365 DAYS
# ============================================================

latest_date = df["date"].max()

start_date = (
    latest_date
    - pd.Timedelta(
        days=DAYS_TO_IMPORT - 1
    )
)

df = df[
    df["date"] >= start_date
].copy()

print(
    f"Date range: "
    f"{start_date.date()} "
    f"to "
    f"{latest_date.date()}"
)


# ============================================================
# MAP TO EXISTING PRODUCTS
# ============================================================

df["product_id"] = df["family"].map(
    FAMILY_TO_PRODUCT
)


# ============================================================
# AGGREGATE DAILY DEMAND
# ============================================================

daily = (
    df.groupby(
        ["product_id", "date"],
        as_index=False,
    )["sales"]
    .sum()
)

daily = daily.rename(
    columns={
        "sales": "units_sold"
    }
)

daily["date"] = (
    daily["date"]
    .dt.date
)


print(
    f"Daily records prepared: "
    f"{len(daily):,}"
)


# ============================================================
# DATABASE INSERT
# ============================================================

db = SessionLocal()

try:

    # Show existing products
    print()
    print("Existing products:")

    products = (
        db.query(Product)
        .order_by(Product.id)
        .all()
    )

    for product in products:
        print(
            f"  {product.id}: "
            f"{product.name}"
        )

    inserted = 0
    updated = 0

    for row in daily.itertuples(
        index=False
    ):

        existing = (
            db.query(DailyDemand)
            .filter(
                DailyDemand.product_id
                == int(row.product_id),

                DailyDemand.date
                == row.date,
            )
            .first()
        )

        if existing:

            existing.units_sold = float(
                row.units_sold
            )

            updated += 1

        else:

            demand = DailyDemand(
                product_id=int(
                    row.product_id
                ),

                date=row.date,

                units_sold=float(
                    row.units_sold
                ),
            )

            db.add(demand)

            inserted += 1

    db.commit()

    print()
    print("=" * 60)
    print("IMPORT SUCCESSFUL")
    print("=" * 60)
    print()
    print(
        f"Inserted: {inserted:,}"
    )
    print(
        f"Updated:  {updated:,}"
    )
    print(
        f"Processed: "
        f"{inserted + updated:,}"
    )

finally:

    db.close()
    engine.dispose()


print()
print("Real Kaggle demand history is now")
print("available to your existing forecasting engine.")
print()
