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
  stock_at_warehouse: number;
}

interface Customer {
  id: number;
  name: string;
}

interface LineForm {
  product_id: number | "";
  requested_qty: number;
  unit_price: number;
  tax_pct: number;
}

const EMPTY_LINE: LineForm = {
  product_id: "",
  requested_qty: 1,
  unit_price: 0,
  tax_pct: 0,
};

export default function NewOutboundPage() {
  const { authFetch, isWarehouse, effectiveCustomerId } = useAuth();
  const navigate = useNavigate();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<number | "">(
    effectiveCustomerId ?? "",
  );
  const [products, setProducts] = useState<ProductLite[]>([]);
  const [strategy, setStrategy] = useState<"" | "FIFO" | "FEFO" | "manual">("");
  const [soNumber, setSoNumber] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineForm[]>([{ ...EMPTY_LINE }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isWarehouse) return;
    authFetch(`${API}/customers`)
      .then((r) => (r.ok ? r.json() : { customers: [] }))
      .then((d) => setCustomers(d.customers || []));
  }, [authFetch, isWarehouse]);

  useEffect(() => {
    const params = new URLSearchParams({ per_page: "200" });
    if (customerId) params.set("customer_id", String(customerId));
    authFetch(`${API}/products?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { products: [] }))
      .then((d) => setProducts(d.products || []));
  }, [authFetch, customerId]);

  const updateLine = (i: number, patch: Partial<LineForm>) =>
    setLines((p) => p.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const addLine = () => setLines((p) => [...p, { ...EMPTY_LINE }]);
  const removeLine = (i: number) =>
    setLines((p) => (p.length > 1 ? p.filter((_, idx) => idx !== i) : p));

  const total = lines.reduce(
    (acc, l) => acc + Number(l.requested_qty || 0) * Number(l.unit_price || 0),
    0,
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (isWarehouse && !customerId) {
      setError("Select a customer for this outbound");
      return;
    }
    if (lines.some((l) => !l.product_id || l.requested_qty <= 0)) {
      setError("Each line needs a product and a positive quantity");
      return;
    }
    setSubmitting(true);
    const r = await authFetch(`${API}/outbounds`, {
      method: "POST",
      body: JSON.stringify({
        customer_id: customerId || undefined,
        so_number: soNumber,
        invoice_number: invoiceNumber,
        notes,
        pick_strategy: strategy || undefined,
        lines: lines.map((l) => ({
          product_id: Number(l.product_id),
          requested_qty: Number(l.requested_qty),
          unit_price: Number(l.unit_price),
          tax_pct: Number(l.tax_pct),
        })),
      }),
    });
    setSubmitting(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setError(e2.detail || "Failed to create outbound");
      return;
    }
    const data = await r.json();
    navigate(`/outbounds/${data.id}`);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => navigate("/outbounds")}>
          <ArrowLeft size={18} />
        </Button>
        <h1 className="text-2xl font-semibold">New outbound</h1>
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
            <div>
              <Label>SO Number</Label>
              <Input value={soNumber} onChange={(e) => setSoNumber(e.target.value)} />
            </div>
            <div>
              <Label>Invoice Number</Label>
              <Input
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
              />
            </div>
            <div>
              <Label>Pick strategy</Label>
              <Select
                value={strategy || "AUTO"}
                onValueChange={(v) =>
                  setStrategy(
                    v === "AUTO" ? "" : (v as "FIFO" | "FEFO" | "manual"),
                  )
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AUTO">
                    Auto (FEFO if perishable, else FIFO)
                  </SelectItem>
                  <SelectItem value="FIFO">FIFO</SelectItem>
                  <SelectItem value="FEFO">FEFO</SelectItem>
                </SelectContent>
              </Select>
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
            {lines.map((l, i) => {
              const prod = products.find((p) => p.id === l.product_id);
              return (
                <div
                  key={i}
                  className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end border rounded-md p-2"
                >
                  <div className="md:col-span-2">
                    <Label className="text-xs">Product</Label>
                    <Select
                      value={l.product_id === "" ? "" : String(l.product_id)}
                      onValueChange={(v) =>
                        updateLine(i, { product_id: Number(v) })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select product" />
                      </SelectTrigger>
                      <SelectContent>
                        {products.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>
                            {p.sku_code} — {p.name} (stock: {p.stock_at_warehouse})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">Requested qty</Label>
                    <Input
                      type="number"
                      min={1}
                      value={l.requested_qty}
                      onChange={(e) =>
                        updateLine(i, { requested_qty: Number(e.target.value) })
                      }
                    />
                    {prod && l.requested_qty > prod.stock_at_warehouse && (
                      <div className="text-[10px] text-destructive mt-1">
                        Only {prod.stock_at_warehouse} in stock
                      </div>
                    )}
                  </div>
                  <div>
                    <Label className="text-xs">Unit price (₹)</Label>
                    <Input
                      type="number"
                      min={0}
                      step={0.01}
                      value={l.unit_price}
                      onChange={(e) =>
                        updateLine(i, { unit_price: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Tax %</Label>
                    <Input
                      type="number"
                      min={0}
                      step={0.01}
                      value={l.tax_pct}
                      onChange={(e) =>
                        updateLine(i, { tax_pct: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeLine(i)}
                      disabled={lines.length === 1}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <div className="flex items-center justify-between border-t pt-4">
          <div className="text-sm text-muted-foreground">
            Total qty:{" "}
            <span className="text-foreground font-medium">
              {lines.reduce((a, l) => a + Number(l.requested_qty || 0), 0)}
            </span>{" "}
            · Total amount:{" "}
            <span className="text-foreground font-medium">
              ₹{total.toLocaleString("en-IN")}
            </span>
          </div>
          <div className="flex gap-2">
            {error && <span className="text-sm text-destructive">{error}</span>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create outbound"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
