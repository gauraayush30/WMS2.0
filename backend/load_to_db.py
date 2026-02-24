import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL not found in environment variables")

engine = create_engine(DB_URL)


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS inventory_sales (
    id          SERIAL PRIMARY KEY,
    sku_id      VARCHAR(20)  NOT NULL,
    sku_name    VARCHAR(100) NOT NULL,
    sale_date   DATE         NOT NULL,
    sales_qty   INTEGER      NOT NULL,
    purchase_qty INTEGER     NOT NULL DEFAULT 0,
    stock_level INTEGER      NOT NULL DEFAULT 0
);
"""

with engine.begin() as conn:
    conn.execute(text(CREATE_TABLE))
    # Clear old rows so re-runs don't duplicate
    conn.execute(text("DELETE FROM inventory_sales"))

print("Table created / cleared.")

#  Load CSV into DB 
df = pd.read_csv("../data/inventory_sales.csv")

df.to_sql(
    "inventory_sales",
    engine,
    if_exists="append",
    index=False,
)

print(f"Inserted {len(df)} rows into inventory_sales table.")
