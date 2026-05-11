What this means for the plan
The architecture needs one fundamental change. Everything else flows from it.

The wrong model: 1 model per (product × customer × warehouse)

That is what exists today AND what the expansion plan doubles down on with seller/buyer pairs. At your scale this is untenable — storage, training jobs, retraining, versioning, drift monitoring all become impossible to manage.

The right model: 1 global model per (customer × warehouse)

One model that sees ALL of a customer's products at once, with product_id, seller_id, buyer_id as categorical features. Training data is pooled across all products for that customer. The model learns "how this customer's business behaves" rather than "how this one SKU behaves."


Model count comparison:
  Current approach at scale:    400,000 models
  Global per-customer approach: 20 × 200 = 4,000 models

Add entity dimensions (seller, buyer):
  Current plan approach: 8,000,000+ models
  Global per-customer approach: STILL 4,000 models
  (seller_id and buyer_id become features, not model multipliers)
This also fixes the sparse data problem completely. A buyer who has ordered 15 times total has no viable individual model. But those 15 orders pooled with every other buyer's orders for that customer give the global model real signal about how that customer's buyers behave as a group.

The specific changes needed in DEMAND_FORECAST_EXPANSION.md
Section 5.1 — Delete seller_trainer.py

Replace with seller_analytics.py. Sellers are a replenishment and reliability problem, not a demand forecasting problem. Compute: fill rate, avg lead time, delivery regularity, concentration index. No ML.

Section 5.2 — Redesign buyer_trainer.py

There is no buyer_trainer.py. There is a global customer model that has buyer_id as a categorical feature. Buyer-level predictions are produced by running inference with buyer_id set, not by loading a separate model.

Section 3.7 — Delete ml_entity_model_metadata table

It becomes unnecessary. Entity predictions come from the same global model. No new metadata table needed.

Section 5 overall — Add the global model design:

The global customer model feature matrix looks like:


# One row per day per product (or per day per product per buyer for entity forecasts)
features = [
    "product_id",          # categorical — model learns product-level patterns
    "buyer_id",            # categorical — nullable; set for buyer-level prediction
    "seller_id",           # categorical — nullable; used for inbound
    "dow",                 # day of week
    "month",
    "week_of_year",
    "days_since_last_order_this_buyer",   # entity-level feature
    "rolling_outbound_7d_product",         # product aggregate
    "rolling_outbound_7d_buyer",           # buyer aggregate
    "rolling_outbound_30d_product",
    "buyer_share_30d",     # this buyer's % of product outbound last 30d
    "stock_level",         # cross-product demand signal
    "lag_1", "lag_7", "lag_14", "lag_30",
    "holiday",
    # ... existing 52 features remain, now product-scoped
]
Training data for customer C, warehouse W = every daily row for every product that customer owns. One fit() call. One .joblib file.

Section 2 — Add to architecture diagram:


Model hierarchy:
  business
    └── customer × warehouse        ← 1 global model here
          └── product                ← feature, not model boundary
                └── buyer/seller     ← feature, not model boundary
Section 4.2 — Promote materialized views from "optional" to required

At 200 customers × 100 products, running the seller-product series SQL live is too expensive. The views are not a performance optimization — they are the architecture.

Section 8 — Add quantile outputs to the model

At scale, the forecast cache stores P10/P50/P90 per (product, buyer, date). This is what the portfolio tab reads. Point forecasts alone don't support inventory decisions.

Section 10 — Revised phase order:

The implementation order should now be:

Phase	What changes
1	DB layer (same as planned) + materialized views (now required)
2	Redesign trainer.py — global per-customer model replacing per-product model
3	ml_forecast_cache table + nightly batch job that runs inference for all customers
4	Portfolio API (reads from cache, never runs live inference)
5	Portfolio frontend
6	Seller reliability analytics (no ML, pure stats)
7	Probabilistic outputs (P10/P50/P90)
8	Simulation engine
Phase 2 is the hard part — migrating the existing per-product trainer to a global per-customer trainer is a meaningful rewrite of trainer.py. But it's the right time to do it before the portfolio layer is built on top of the current architecture, because everything downstream of it (portfolio API, caching, entity forecasts) is shaped by whether the model is per-product or per-customer.

One more thing worth saying directly: the critique you received is the kind of feedback that comes from someone who has built large ML systems. The points about global models, hierarchical allocation, and avoiding model explosion are genuinely correct at your scale. The plan you have is excellent thinking for a 50-product single-tenant system. For a multi-tenant 3PL at real scale it needs this one architectural pivot at the ML layer, and then it becomes a serious system.