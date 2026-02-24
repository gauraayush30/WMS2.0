import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Define SKUs with distinct demand profiles
SKUS = {
    "SKU-001": {"name": "Widget Alpha",   "base": 30, "weekend_factor": 0.6,  "trend": 0.005},
    "SKU-002": {"name": "Widget Beta",    "base": 50, "weekend_factor": 0.8,  "trend": -0.002},
    "SKU-003": {"name": "Gadget Pro",     "base": 20, "weekend_factor": 1.3,  "trend": 0.01},
    "SKU-004": {"name": "Gadget Lite",    "base": 40, "weekend_factor": 0.7,  "trend": 0.0},
    "SKU-005": {"name": "Accessory Plus", "base": 15, "weekend_factor": 0.9,  "trend": 0.008},
}

MONTH_SEASONALITY = {
    1: 0.80, 2: 0.75, 3: 0.85, 4: 0.90, 5: 0.95, 6: 1.00,
    7: 1.00, 8: 0.95, 9: 1.00, 10: 1.05, 11: 1.20, 12: 1.30,
}

start_date = datetime(2023, 1, 1)
num_days = 730  # ~2 years

rows = []

for sku_id, cfg in SKUS.items():
    stock = 500
    for i in range(num_days):
        d = start_date + timedelta(days=i)
        dow = d.weekday()       # 0=Mon … 6=Sun
        month = d.month

        demand = cfg["base"]

        # Weekend effect
        if dow >= 5:
            demand *= cfg["weekend_factor"]

        # Monthly seasonality
        demand *= MONTH_SEASONALITY[month]

        # Long-term trend (per-month growth/decline)
        demand *= 1 + cfg["trend"] * (i / 30)

        # Gaussian noise (σ = 15 % of demand)
        demand = max(1, int(round(demand + np.random.normal(0, demand * 0.15))))

        # Replenishment logic
        purchase_qty = 0
        if stock < 200:
            purchase_qty = int(np.random.randint(300, 600))

        stock = max(0, stock - demand + purchase_qty)

        rows.append({
            "sku_id": sku_id,
            "sku_name": cfg["name"],
            "sale_date": d.strftime("%Y-%m-%d"),
            "sales_qty": demand,
            "purchase_qty": purchase_qty,
            "stock_level": stock,
        })

df = pd.DataFrame(rows)
df.to_csv("../data/inventory_sales.csv", index=False)

print(f"Generated {len(df)} rows for {len(SKUS)} SKUs over {num_days} days")
print(df.groupby("sku_id")["sales_qty"].describe().round(1))
