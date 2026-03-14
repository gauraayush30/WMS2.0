import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  par_level: number;
  reorder_point: number;
  safety_stock: number;
  lead_time_days: number;
  max_stock_level: number;
  location_zone: string;
  location_aisle: string;
  location_rack: string;
  location_shelf: string;
  location_level: string;
  location_bin: string;
}

export default function EditProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    name: "",
    sku_code: "",
    price: "0",
    uom: "pcs",
    par_level: "0",
    reorder_point: "0",
    safety_stock: "0",
    lead_time_days: "0",
    max_stock_level: "0",
    location_zone: "",
    location_aisle: "",
    location_rack: "",
    location_shelf: "",
    location_level: "",
    location_bin: "",
  });
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    authFetch(`${API}/products/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Product not found");
        return r.json();
      })
      .then((p: Product) => {
        setForm({
          name: p.name,
          sku_code: p.sku_code,
          price: String(p.price),
          uom: p.uom || "pcs",
          par_level: String(p.par_level ?? 0),
          reorder_point: String(p.reorder_point ?? 0),
          safety_stock: String(p.safety_stock ?? 0),
          lead_time_days: String(p.lead_time_days ?? 0),
          max_stock_level: String(p.max_stock_level ?? 0),
          location_zone: p.location_zone ?? "",
          location_aisle: p.location_aisle ?? "",
          location_rack: p.location_rack ?? "",
          location_shelf: p.location_shelf ?? "",
          location_level: p.location_level ?? "",
          location_bin: p.location_bin ?? "",
        });
      })
      .catch((e) => setFormError(e.message))
      .finally(() => setLoading(false));
  }, [authFetch, id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.name.trim() || !form.sku_code.trim()) {
      setFormError("Name and SKU Code are required");
      return;
    }
    setSaving(true);
    try {
      const res = await authFetch(`${API}/products/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.name.trim(),
          sku_code: form.sku_code.trim(),
          price: parseFloat(form.price) || 0,
          uom: form.uom.trim() || "pcs",
          par_level: parseInt(form.par_level) || 0,
          reorder_point: parseInt(form.reorder_point) || 0,
          safety_stock: parseInt(form.safety_stock) || 0,
          lead_time_days: parseInt(form.lead_time_days) || 0,
          max_stock_level: parseInt(form.max_stock_level) || 0,
          location_zone: form.location_zone.trim(),
          location_aisle: form.location_aisle.trim(),
          location_rack: form.location_rack.trim(),
          location_shelf: form.location_shelf.trim(),
          location_level: form.location_level.trim(),
          location_bin: form.location_bin.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update product");
      }
      setFormSuccess("Product updated successfully!");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string, val: string) => setForm((p) => ({ ...p, [key]: val }));

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate(`/products/${id}`)}>
          <ArrowLeft size={14} /> Back to Product
        </Button>
        <h2 className="text-xl font-bold">Edit Product</h2>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Product Details</CardTitle>
        </CardHeader>
        <CardContent>
          {formError && <Alert variant="destructive" className="mb-4">{formError}</Alert>}
          {formSuccess && <Alert variant="success" className="mb-4">{formSuccess}</Alert>}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Product Name *</Label>
                <Input value={form.name} onChange={(e) => set("name", e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label>SKU Code *</Label>
                <Input value={form.sku_code} onChange={(e) => set("sku_code", e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label>Price</Label>
                <Input type="number" step="0.01" min="0" value={form.price} onChange={(e) => set("price", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Unit of Measurement</Label>
                <Input value={form.uom} onChange={(e) => set("uom", e.target.value)} />
              </div>
            </div>

            <Separator />

            <div>
              <h4 className="text-sm font-semibold text-muted-foreground mb-3">Inventory Management</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="space-y-1.5"><Label>PAR Level</Label><Input type="number" min="0" value={form.par_level} onChange={(e) => set("par_level", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Reorder Point</Label><Input type="number" min="0" value={form.reorder_point} onChange={(e) => set("reorder_point", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Safety Stock</Label><Input type="number" min="0" value={form.safety_stock} onChange={(e) => set("safety_stock", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Lead Time (days)</Label><Input type="number" min="0" value={form.lead_time_days} onChange={(e) => set("lead_time_days", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Max Stock Level</Label><Input type="number" min="0" value={form.max_stock_level} onChange={(e) => set("max_stock_level", e.target.value)} /></div>
              </div>
            </div>

            <Separator />

            <div>
              <h4 className="text-sm font-semibold text-muted-foreground mb-3">Warehouse Location</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5"><Label>Zone</Label><Input value={form.location_zone} onChange={(e) => set("location_zone", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Aisle</Label><Input value={form.location_aisle} onChange={(e) => set("location_aisle", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Rack</Label><Input value={form.location_rack} onChange={(e) => set("location_rack", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Shelf</Label><Input value={form.location_shelf} onChange={(e) => set("location_shelf", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Level</Label><Input value={form.location_level} onChange={(e) => set("location_level", e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Bin / Pallet</Label><Input value={form.location_bin} onChange={(e) => set("location_bin", e.target.value)} /></div>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={saving}>
                <Save size={14} /> {saving ? "Saving..." : "Update Product"}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate(`/products/${id}`)}>
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
