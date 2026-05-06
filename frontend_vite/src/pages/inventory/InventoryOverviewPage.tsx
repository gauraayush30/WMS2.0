import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft, Package, X, CalendarClock, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { motion, AnimatePresence } from "framer-motion";

interface ProductStock {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  updated_at: string;
  customer_id: number | null;
  customer_name: string | null;
  customer_code: string | null;
}

interface StockBatch {
  id: number;
  product_id: number;
  quantity: number;
  remaining_qty: number;
  purchased_at: string;
  expires_at: string | null;
  is_expired: boolean;
}

interface StockBatchDialogData {
  batches: StockBatch[];
  product: {
    id: number;
    name: string;
    sku_code: string;
    expiry_days: number;
  };
}

export default function InventoryOverviewPage() {
  const { authFetch, effectiveCustomerId, selectedWarehouseId, isWarehouse } = useAuth();
  const navigate = useNavigate();

  const [products, setProducts] = useState<ProductStock[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Stock Batches Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogData, setDialogData] = useState<StockBatchDialogData | null>(null);
  const [dialogLoading, setDialogLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const params = new URLSearchParams({
          page: String(page),
          per_page: "18",
          search: search,
        });
        if (effectiveCustomerId) params.set("customer_id", String(effectiveCustomerId));
        if (selectedWarehouseId) params.set("warehouse_id", String(selectedWarehouseId));
        const r = await authFetch(`${API}/inventory/overview?${params.toString()}`);
        const data = await r.json();
        if (!cancelled) {
          setProducts(data.products || []);
          setTotalPages(data.total_pages || 0);
        }
      } catch {
        if (!cancelled) {
          setProducts([]);
          setTotalPages(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    setLoading(true);
    load();
    return () => {
      cancelled = true;
    };
  }, [authFetch, page, search, effectiveCustomerId, selectedWarehouseId]);

  const stockVariant = (stock: number) => {
    if (stock === 0) return "destructive" as const;
    if (stock <= 10) return "warning" as const;
    return "success" as const;
  };

  const handleRowClick = async (productId: number) => {
    setDialogOpen(true);
    setDialogLoading(true);
    setDialogData(null);
    try {
      const r = await authFetch(`${API}/products/${productId}/stock-batches`);
      if (r.ok) {
        const data = await r.json();
        setDialogData(data);
      }
    } catch {
      // silently fail
    } finally {
      setDialogLoading(false);
    }
  };

  const getBatchStatus = (batch: StockBatch) => {
    if (batch.is_expired) return "expired";
    if (batch.remaining_qty === 0) return "consumed";
    if (!batch.expires_at) return "active";
    const now = new Date();
    const exp = new Date(batch.expires_at);
    const diffDays = Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return "expired";
    if (diffDays <= 7) return "expiring_soon";
    return "active";
  };

  const getBatchBadge = (status: string) => {
    switch (status) {
      case "expired":
        return <Badge variant="destructive" className="text-[10px]">Expired</Badge>;
      case "expiring_soon":
        return <Badge variant="warning" className="text-[10px]">Expiring Soon</Badge>;
      case "consumed":
        return <Badge variant="secondary" className="text-[10px]">Consumed</Badge>;
      default:
        return <Badge variant="success" className="text-[10px]">Active</Badge>;
    }
  };

  const getBatchRowClass = (status: string) => {
    switch (status) {
      case "expired":
        return "bg-red-50/60";
      case "expiring_soon":
        return "bg-amber-50/60";
      case "consumed":
        return "opacity-50";
      default:
        return "";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate("/inventory")}>
          <ArrowLeft size={14} /> Back
        </Button>
        <h2 className="text-xl font-bold">Inventory Overview</h2>
      </div>

      <Card>
        <CardContent className="p-4 flex items-center justify-between gap-3 flex-wrap">
          <h3 className="text-sm font-semibold">All Products</h3>
          <Input
            className="w-full sm:w-72"
            placeholder="Search products..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-10 rounded-lg" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <Package size={38} className="mx-auto mb-2 opacity-60" />
            <p>No products found.</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product Name</TableHead>
                <TableHead>SKU</TableHead>
                {isWarehouse && !effectiveCustomerId && <TableHead>Customer</TableHead>}
                <TableHead className="text-right">Stock</TableHead>
                <TableHead>UOM</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((p) => (
                <TableRow
                  key={p.id}
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => handleRowClick(p.id)}
                >
                  <TableCell className="font-medium text-sm">{p.name}</TableCell>
                  <TableCell><code className="text-xs">{p.sku_code}</code></TableCell>
                  {isWarehouse && !effectiveCustomerId && (
                    <TableCell className="text-xs text-muted-foreground">
                      {p.customer_name || "—"}
                      {p.customer_code && <span className="ml-1 opacity-60">({p.customer_code})</span>}
                    </TableCell>
                  )}
                  <TableCell className="text-right text-sm">{p.stock_at_warehouse}</TableCell>
                  <TableCell className="text-sm">{p.uom || "pcs"}</TableCell>
                  <TableCell className="text-right text-sm">₹{Number(p.price).toFixed(2)}</TableCell>
                  <TableCell>
                    <Badge variant={stockVariant(p.stock_at_warehouse)}>
                      {p.stock_at_warehouse === 0 ? "Out of Stock" : p.stock_at_warehouse <= 10 ? "Low Stock" : "In Stock"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      )}

      {/* ── Stock Batches Dialog ───────────────────── */}
      <AnimatePresence>
        {dialogOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDialogOpen(false)}
            />
            {/* Dialog */}
            <motion.div
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: "spring", duration: 0.3 }}
            >
              <div
                className="bg-background rounded-xl shadow-2xl border w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between gap-3 px-6 py-4 border-b bg-muted/30">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-50 text-rose-600 shrink-0">
                      <CalendarClock size={18} />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold truncate">
                        {dialogData?.product.name ?? "Loading..."}
                      </h3>
                      {dialogData?.product && (
                        <div className="flex items-center gap-2 mt-0.5">
                          <code className="text-[11px] text-muted-foreground">{dialogData.product.sku_code}</code>
                          {dialogData.product.expiry_days > 0 && (
                            <Badge variant="secondary" className="text-[10px]">
                              {dialogData.product.expiry_days}d shelf life
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() => setDialogOpen(false)}
                  >
                    <X size={16} />
                  </Button>
                </div>

                {/* Body */}
                <div className="overflow-auto flex-1 px-6 py-4">
                  {dialogLoading ? (
                    <div className="space-y-3 py-4">
                      {[...Array(4)].map((_, i) => (
                        <Skeleton key={i} className="h-10 rounded-lg" />
                      ))}
                    </div>
                  ) : !dialogData || dialogData.batches.length === 0 ? (
                    <div className="py-12 text-center text-muted-foreground">
                      <Package size={32} className="mx-auto mb-3 opacity-50" />
                      <p className="text-sm font-medium">No stock batches found</p>
                      <p className="text-xs mt-1">
                        Stock batches are created automatically when stock is added to products with expiry tracking enabled.
                      </p>
                    </div>
                  ) : (
                    <>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-14">Batch</TableHead>
                            <TableHead>Purchased</TableHead>
                            <TableHead>Expires</TableHead>
                            <TableHead className="text-right">Qty</TableHead>
                            <TableHead className="text-right">Remaining</TableHead>
                            <TableHead>Status</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {dialogData.batches.map((b) => {
                            const status = getBatchStatus(b);
                            return (
                              <TableRow key={b.id} className={getBatchRowClass(status)}>
                                <TableCell className="text-xs font-mono">#{b.id}</TableCell>
                                <TableCell className="text-xs">
                                  {new Date(b.purchased_at).toLocaleDateString()}
                                </TableCell>
                                <TableCell className="text-xs">
                                  {b.expires_at ? (
                                    <span className={status === "expiring_soon" ? "text-amber-600 font-semibold" : status === "expired" ? "text-red-600 font-semibold" : ""}>
                                      {new Date(b.expires_at).toLocaleDateString()}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">No expiry</span>
                                  )}
                                </TableCell>
                                <TableCell className="text-right text-xs">{b.quantity}</TableCell>
                                <TableCell className="text-right text-xs font-semibold">
                                  {b.remaining_qty}
                                </TableCell>
                                <TableCell>{getBatchBadge(status)}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>

                      {/* Summary */}
                      <div className="mt-4 flex items-center justify-between px-1 py-3 border-t">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <AlertTriangle size={13} />
                          {dialogData.batches.filter(b => getBatchStatus(b) === "expiring_soon").length > 0
                            ? `${dialogData.batches.filter(b => getBatchStatus(b) === "expiring_soon").length} batch(es) expiring within 7 days`
                            : "No batches expiring soon"
                          }
                        </div>
                        <div className="text-xs font-semibold">
                          Total remaining:{" "}
                          <span className="text-primary">
                            {dialogData.batches
                              .filter(b => !b.is_expired)
                              .reduce((sum, b) => sum + b.remaining_qty, 0)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
