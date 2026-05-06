"""
Smoke test for multi-tenant isolation.

Run against a live backend_api on http://127.0.0.1:8000 with a fresh DB.
This is a happy-path smoke test, not a thorough RBAC matrix — Phase 6 should
expand it into a full pytest suite that runs in CI.

Usage:
    BASE_URL=http://127.0.0.1:8000 python tests/test_tenancy_smoke.py
"""

from __future__ import annotations

import os
import sys
import time
import json
from urllib.parse import urljoin

import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TS = int(time.time())


def _post(path: str, body: dict, token: str | None = None) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(urljoin(BASE, path), data=json.dumps(body), headers=headers)


def _get(path: str, token: str) -> requests.Response:
    return requests.get(
        urljoin(BASE, path), headers={"Authorization": f"Bearer {token}"}
    )


def main() -> int:
    print(f"Smoke-testing {BASE}")

    # 1. Register a warehouse_admin
    r = _post("/auth/register", {
        "username": f"wadmin_{TS}",
        "name": "Warehouse Admin",
        "email": f"wadmin_{TS}@test.local",
        "password": "testtest",
        "business_name": f"3PL {TS}",
        "business_location": "Bangalore",
    })
    assert r.status_code == 201, r.text
    wadmin = r.json()
    wadmin_token = wadmin["access_token"]
    assert wadmin["user"]["role"] == "warehouse_admin", wadmin["user"]
    print("  ✓ warehouse_admin registered")

    # 2. Create two customers
    r = _post("/customers", {"name": "Acme", "code": "ACME"}, wadmin_token)
    assert r.status_code == 201, r.text
    acme = r.json()
    r = _post("/customers", {"name": "Globex", "code": "GLBX"}, wadmin_token)
    assert r.status_code == 201, r.text
    globex = r.json()
    print(f"  ✓ created customers: ACME #{acme['id']} / GLBX #{globex['id']}")

    # 3. Add customer_admin for Acme
    r = _post(
        f"/customers/{acme['id']}/users",
        {
            "username": f"acme_admin_{TS}",
            "name": "Acme Admin",
            "email": f"acme_admin_{TS}@test.local",
            "password": "testtest",
            "role": "customer_admin",
        },
        wadmin_token,
    )
    assert r.status_code == 201, r.text
    print("  ✓ acme_admin created")

    # 4. Login as acme_admin
    r = _post("/auth/login", {
        "email": f"acme_admin_{TS}@test.local",
        "password": "testtest",
    })
    assert r.status_code == 200, r.text
    acme_token = r.json()["access_token"]

    # 5. Acme creates a product
    r = _post("/products", {
        "name": "Widget",
        "sku_code": f"WGT-{TS}",
        "price": 100,
        "stock_at_warehouse": 0,
    }, acme_token)
    assert r.status_code == 201, r.text
    print("  ✓ acme_admin created a product")

    # 6. Acme cannot see Globex's customer record
    r = _get(f"/customers/{globex['id']}", acme_token)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
    print("  ✓ acme_admin forbidden from globex customer record")

    # 7. List products as acme — should see only Acme's
    r = _get("/products", acme_token)
    assert r.status_code == 200, r.text
    items = r.json()["products"]
    cust_ids = {p.get("customer_id") for p in items}
    assert cust_ids == {acme["id"]}, f"acme leaked other customer products: {cust_ids}"
    print(f"  ✓ acme_admin sees only acme products ({len(items)} item(s))")

    # 8. Warehouse view — list all + filter by customer
    r = _get(f"/products?customer_id={globex['id']}", wadmin_token)
    assert r.status_code == 200, r.text
    items = r.json()["products"]
    assert all(p.get("customer_id") == globex["id"] for p in items)
    print("  ✓ warehouse_admin can filter products by customer_id")

    print("All smoke checks passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
