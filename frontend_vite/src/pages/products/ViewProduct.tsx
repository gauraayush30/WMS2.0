import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowLeft, Pencil, Trash2, Package, DollarSign, Barcode,
  Warehouse, Clock, History, Ruler, AlertTriangle, ArrowDownToLine,
  ShieldCheck, Truck, TrendingUp, MapPin, Brain,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import DemandForecastTab from "../../components/DemandForecastTab";
import { motion } from "framer-motion";

interface Product {
  id: number; name: string; sku_code: string; price: number;
  stock_at_warehouse: number; uom: string; par_level: number;
  reorder_point: number; safety_stock: number; lead_time_days: number;
  max_stock_level: number; location_zone: string; location_aisle: string;
  location_rack: string; location_shelf: string; location_level: string;
  location_bin: string; created_at: string; updated_at: string;
}

interface AuditEntry {
  id: number; product_id: number; field_name: string; old_value: string;
  new_value: string; updated_by_name: string; created_at: string;
}

export default function ViewProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("details");

  useEffect(() => {
    setLoading(true);
    authFetch(`${API}/products/${id}`)
      .then((r) => { if (!r.ok) throw new Error("Product not found"); return r.json(); })
      .then((data) => setProduct(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [authFetch, id]);

  useEffect(() => {
    if (!id) return;
    setAuditLoading(true);
    authFetch(`${API}/products/${id}/audit-log`)
      .then((r) => { if (!r.ok) return { entries: [] }; return r.json(); })
      .then((data) => setAuditLog(data.entries || []))
      .catch(() => setAuditLog([]))
      .finally(() => setAuditLoading(false));
  }, [authFetch, id]);

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this product? All related inventory transactions will also be deleted.")) return;
    setDeleting(true);
    try {
      const res = await authFetch(`${API}/products/${id}`, { method: "DELETE" });
      if (!res.ok) { const err = await res.json().catch(() => ({})); alert(err.detail || "Failed to delete"); setDeleting(false); return; }
      navigate("/products");
    } catch { alert("Error deleting product"); setDeleting(false); }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">{error || "Product not found"}</Alert>
        <Button variant="outline" size="sm" onClick={() => navigate("/products")}>
          <ArrowLeft size={14} /> Back to Products
        </Button>
      </div>
    );
  }

  const stockVariant = product.stock_at_warehouse === 0 ? "destructive" : product.stock_at_warehouse <= 10 ? "warning" : "success";

  const detailCards = [
    { label: "Product Name", value: product.name, icon: Package, color: "bg-blue-50 text-blue-600" },
    { label: "SKU Code", value: product.sku_code, icon: Barcode, color: "bg-purple-50 text-purple-600", mono: true },
    { label: "Price", value: `₹${Number(product.price).toFixed(2)}`, icon: DollarSign, color: "bg-emerald-50 text-emerald-600" },
    { label: "Stock", value: product.stock_at_warehouse, icon: Warehouse, color: "bg-amber-50 text-amber-600", badge: stockVariant },
    { label: "UOM", value: product.uom || "pcs", icon: Ruler, color: "bg-purple-50 text-purple-600" },
    { label: "Created", value: new Date(product.created_at).toLocaleString(), icon: Clock, color: "bg-gray-50 text-gray-500" },
  ];

  const inventoryCards = [
    { label: "PAR Level", value: product.par_level ?? 0, icon: TrendingUp, color: "bg-blue-50 text-blue-600" },
    { label: "Reorder Point", value: product.reorder_point ?? 0, icon: ArrowDownToLine, color: "bg-amber-50 text-amber-600" },
    { label: "Safety Stock", value: product.safety_stock ?? 0, icon: ShieldCheck, color: "bg-emerald-50 text-emerald-600" },
    { label: "Lead Time", value: `${product.lead_time_days ?? 0} days`, icon: Truck, color: "bg-purple-50 text-purple-600" },
    { label: "Max Stock", value: product.max_stock_level ?? 0, icon: AlertTriangle, color: "bg-amber-50 text-amber-600" },
  ];

  const locationFields = [
    { label: "Zone", value: product.location_zone },
    { label: "Aisle", value: product.location_aisle },
    { label: "Rack", value: product.location_rack },
    { label: "Shelf", value: product.location_shelf },
    { label: "Level", value: product.location_level },
    { label: "Bin / Pallet", value: product.location_bin },
  ];
  const hasLocation = locationFields.some((f) => f.value);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => navigate("/products")}>
          <ArrowLeft size={14} /> Back
        </Button>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <h2 className="text-xl font-bold truncate">{product.name}</h2>
          <code className="text-xs bg-muted px-2 py-0.5 rounded shrink-0">{product.sku_code}</code>
        </div>
        <div className="flex gap-2 ml-auto">
          <Button size="sm" onClick={() => navigate(`/products/${product.id}/edit`)}>
            <Pencil size={14} /> Edit
          </Button>
          <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
            <Trash2 size={14} /> {deleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="details"><Package size={14} className="mr-1.5" /> Details</TabsTrigger>
          <TabsTrigger value="forecast"><Brain size={14} className="mr-1.5" /> Demand Forecast</TabsTrigger>
          <TabsTrigger value="history"><History size={14} className="mr-1.5" /> Edit History</TabsTrigger>
        </TabsList>

        {/* ── Details Tab ──────────────────────── */}
        <TabsContent value="details">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 mt-2">
            {/* Product Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {detailCards.map((c) => (
                <Card key={c.label}>
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${c.color}`}>
                      <c.icon size={18} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{c.label}</p>
                      {c.badge ? (
                        <Badge variant={c.badge as "success" | "warning" | "destructive"}>{String(c.value)}</Badge>
                      ) : c.mono ? (
                        <code className="text-sm font-semibold">{c.value}</code>
                      ) : (
                        <p className="text-sm font-semibold truncate">{c.value}</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Inventory Management */}
            <div>
              <h3 className="text-sm font-semibold text-muted-foreground mb-3">Inventory Management</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {inventoryCards.map((c) => (
                  <Card key={c.label}>
                    <CardContent className="flex items-center gap-4 p-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${c.color}`}>
                        <c.icon size={18} />
                      </div>
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{c.label}</p>
                        <p className="text-sm font-semibold">{c.value}</p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Warehouse Location */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={14} className="text-muted-foreground" />
                <h3 className="text-sm font-semibold text-muted-foreground">Warehouse Location</h3>
                {!hasLocation && <Badge variant="destructive" className="text-[10px]">Not Set</Badge>}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {locationFields.map((f) => (
                  <Card key={f.label}>
                    <CardContent className="p-3">
                      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-0.5">{f.label}</p>
                      <p className="text-sm font-semibold">{f.value || <span className="text-muted-foreground">—</span>}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </motion.div>
        </TabsContent>

        {/* ── Demand Forecast Tab ──────────────── */}
        <TabsContent value="forecast">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2">
            <DemandForecastTab productId={id!} />
          </motion.div>
        </TabsContent>

        {/* ── Edit History Tab ─────────────────── */}
        <TabsContent value="history">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2">
            {auditLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}
              </div>
            ) : auditLog.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No edits have been made to this product yet.
              </p>
            ) : (
              <Card className="overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Field</TableHead>
                      <TableHead>Old Value</TableHead>
                      <TableHead>New Value</TableHead>
                      <TableHead>Updated By</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLog.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs capitalize">{entry.field_name}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-red-500 line-through">{entry.old_value}</TableCell>
                        <TableCell className="text-xs text-emerald-600 font-medium">{entry.new_value}</TableCell>
                        <TableCell className="text-xs">{entry.updated_by_name}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
