import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, ArrowLeft } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ProductLite {
  id: number;
  name: string;
  sku_code: string;
  expiry_days: number;
}

interface Customer {
  id: number;
  name: string;
}

interface Seller {
  id: number;
  name: string;
  gstin: string;
}

interface SellerLocation {
  id: number;
  name: string;
  city: string;
  state: string;
}

interface LineForm {
  product_id: number | "";
  expected_qty: number;
  unit_cost: number;
  tax_pct: number;
  expires_at: string;
  batch_code: string;
}

const EMPTY_LINE: LineForm = {
  product_id: "",
  expected_qty: 1,
  unit_cost: 0,
  tax_pct: 0,
  expires_at: "",
  batch_code: "",
};

export default function NewInboundPage() {
  const { authFetch, isWarehouse, effectiveCustomerId } = useAuth();
  const navigate = useNavigate();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<number | "">(
    effectiveCustomerId ?? "",
  );
  const [products, setProducts] = useState<ProductLite[]>([]);

  /* Seller + location state */
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [sellerId, setSellerId] = useState<number | "">("");
  const [sellerLocations, setSellerLocations] = useState<SellerLocation[]>([]);
  const [sellerLocationId, setSellerLocationId] = useState<number | "">("");

  const [poNumber, setPoNumber] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineForm[]>([{ ...EMPTY_LINE }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  /* Fetch customers */
  useEffect(() => {
    if (!isWarehouse) return;
    authFetch(`${API}/customers`)
      .then((r) => (r.ok ? r.json() : { customers: [] }))
      .then((d) => setCustomers(d.customers || []));
  }, [authFetch, isWarehouse]);

  /* Fetch sellers when customer changes */
  useEffect(() => {
    if (!customerId) {
      setSellers([]);
      setSellerId("");
      return;
    }
    const params = new URLSearchParams({ customer_id: String(customerId) });
    authFetch(`${API}/sellers?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { sellers: [] }))
      .then((d) => setSellers(d.sellers || []));
    setSellerId("");
    setSellerLocations([]);
    setSellerLocationId("");
  }, [authFetch, customerId]);

  /* Fetch seller locations when seller changes */
  useEffect(() => {
    if (!sellerId) {
      setSellerLocations([]);
      setSellerLocationId("");
      return;
    }
    authFetch(`${API}/sellers/${sellerId}/locations`)
      .then((r) => (r.ok ? r.json() : { locations: [] }))
      .then((d) => setSellerLocations(d.locations || []));
    setSellerLocationId("");
  }, [authFetch, sellerId]);

  /* Fetch products when customer changes */
  useEffect(() => {
    const params = new URLSearchParams({ per_page: "50" });
    if (customerId) params.set("customer_id", String(customerId));
    authFetch(`${API}/products?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { products: [] }))
      .then((d) => setProducts(d.products || []));
  }, [authFetch, customerId]);

  const updateLine = (i: number, patch: Partial<LineForm>) => {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  };
  const addLine = () => setLines((p) => [...p, { ...EMPTY_LINE }]);
  const removeLine = (i: number) =>
    setLines((p) => (p.length > 1 ? p.filter((_, idx) => idx !== i) : p));

  const total = lines.reduce(
    (acc, l) => acc + Number(l.expected_qty || 0) * Number(l.unit_cost || 0),
    0,
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (isWarehouse && !customerId) {
      setError("Select a customer for this inbound");
      return;
    }
    if (!sellerId) {
      setError("Select a seller for this inbound");
      return;
    }
    if (lines.some((l) => !l.product_id || l.expected_qty <= 0)) {
      setError("Each line needs a product and a positive quantity");
      return;
    }
    setSubmitting(true);
    const r = await authFetch(`${API}/inbounds`, {
      method: "POST",
      body: JSON.stringify({
        customer_id: customerId || undefined,
        supplier_id: sellerId || undefined,
        po_number: poNumber,
        invoice_number: invoiceNumber,
        notes,
        lines: lines.map((l) => ({
          product_id: Number(l.product_id),
          expected_qty: Number(l.expected_qty),
          unit_cost: Number(l.unit_cost),
          tax_pct: Number(l.tax_pct),
          expires_at: l.expires_at || undefined,
          batch_code: l.batch_code,
        })),
      }),
    });
    setSubmitting(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setError(e2.detail || "Failed to create inbound");
      return;
    }
    const data = await r.json();
    navigate(`/inbounds/${data.id}`);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => navigate("/inbounds")}>
          <ArrowLeft size={18} />
        </Button>
        <h1 className="text-2xl font-semibold">New inbound</h1>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Header</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {isWarehouse && (
              <div>
                <Label>Customer</Label>
                <Select
                  value={customerId === "" ? "" : String(customerId)}
                  onValueChange={(v) => setCustomerId(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select customer" />
                  </SelectTrigger>
                  <SelectContent>
                    {customers.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Seller dropdown */}
            <div>
              <Label>Seller</Label>
              <Select
                value={sellerId === "" ? "" : String(sellerId)}
                onValueChange={(v) => setSellerId(Number(v))}
                disabled={sellers.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder={sellers.length === 0 ? "No sellers available" : "Select seller"} />
                </SelectTrigger>
                <SelectContent>
                  {sellers.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.name}{s.gstin ? ` (${s.gstin})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Seller location dropdown */}
            <div>
              <Label>Seller Location</Label>
              <Select
                value={sellerLocationId === "" ? "" : String(sellerLocationId)}
                onValueChange={(v) => setSellerLocationId(Number(v))}
                disabled={sellerLocations.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder={!sellerId ? "Select seller first" : sellerLocations.length === 0 ? "No locations" : "Select location"} />
                </SelectTrigger>
                <SelectContent>
                  {sellerLocations.map((loc) => (
                    <SelectItem key={loc.id} value={String(loc.id)}>
                      {loc.name}{loc.city ? `, ${loc.city}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>PO Number</Label>
              <Input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} />
            </div>
            <div>
              <Label>Invoice Number</Label>
              <Input
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
              />
            </div>
            <div className="md:col-span-3">
              <Label>Notes</Label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-sm">Line items</CardTitle>
            <Button type="button" variant="outline" onClick={addLine}>
              <Plus size={14} /> Add line
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {lines.map((l, i) => (
              <div
                key={i}
                className="grid grid-cols-1 md:grid-cols-7 gap-2 items-end border rounded-md p-2"
              >
                <div className="md:col-span-2">
                  <Label className="text-xs">Product</Label>
                  <Select
                    value={l.product_id === "" ? "" : String(l.product_id)}
                    onValueChange={(v) => updateLine(i, { product_id: Number(v) })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select product" />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>
                          {p.sku_code} — {p.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">Qty</Label>
                  <Input
                    type="number"
                    min={1}
                    value={l.expected_qty}
                    onChange={(e) =>
                      updateLine(i, { expected_qty: Number(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <Label className="text-xs">Unit cost (₹)</Label>
                  <Input
                    type="number"
                    min={0}
                    step={0.01}
                    value={l.unit_cost}
                    onChange={(e) => updateLine(i, { unit_cost: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <Label className="text-xs">Tax %</Label>
                  <Input
                    type="number"
                    min={0}
                    step={0.01}
                    value={l.tax_pct}
                    onChange={(e) => updateLine(i, { tax_pct: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <Label className="text-xs">Expires</Label>
                  <Input
                    type="date"
                    value={l.expires_at}
                    onChange={(e) => updateLine(i, { expires_at: e.target.value })}
                  />
                </div>
                <div className="flex gap-1">
                  <div className="flex-1">
                    <Label className="text-xs">Batch code</Label>
                    <Input
                      value={l.batch_code}
                      onChange={(e) => updateLine(i, { batch_code: e.target.value })}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="self-end"
                    onClick={() => removeLine(i)}
                    disabled={lines.length === 1}
                    title="Remove line"
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex items-center justify-between border-t pt-4">
          <div className="text-sm text-muted-foreground">
            Total qty:{" "}
            <span className="text-foreground font-medium">
              {lines.reduce((a, l) => a + Number(l.expected_qty || 0), 0)}
            </span>{" "}
            · Total amount:{" "}
            <span className="text-foreground font-medium">
              ₹{total.toLocaleString("en-IN")}
            </span>
          </div>
          <div className="flex gap-2">
            {error && <span className="text-sm text-destructive">{error}</span>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create inbound"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
