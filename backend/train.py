import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

# ── Load data ────────────────────────────────────────────────
df = pd.read_csv("../data/inventory_sales.csv")
df["sale_date"] = pd.to_datetime(df["sale_date"])

# ── Feature engineering ──────────────────────────────────────
df["day_of_week"]  = df["sale_date"].dt.dayofweek
df["month"]        = df["sale_date"].dt.month
df["day_of_month"] = df["sale_date"].dt.day
df["day_of_year"]  = df["sale_date"].dt.dayofyear
df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)
df["week_of_year"] = df["sale_date"].dt.isocalendar().week.astype(int)

FEATURES = ["day_of_week", "month", "day_of_month",
            "day_of_year", "is_weekend", "week_of_year"]

# ── Train one RandomForest model per SKU ─────────────────────
models = {}
for sku_id in sorted(df["sku_id"].unique()):
    sku_df = df[df["sku_id"] == sku_id]
    X = sku_df[FEATURES]
    y = sku_df["sales_qty"]

    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=12,
        random_state=42,
    )
    model.fit(X, y)
    models[sku_id] = model

    print(f"  {sku_id}  R² = {model.score(X, y):.4f}  (n={len(sku_df)})")

# ── Save ─────────────────────────────────────────────────────
joblib.dump(models, "models.pkl")
print(f"\nSaved {len(models)} per-SKU models → models.pkl")
