import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import { Package, Warehouse, AlertTriangle, TrendingDown, Eye, ClipboardList, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";

interface Summary {
  total_products: number;
  total_stock: number;
  out_of_stock: number;
  low_stock: number;
}

export default function InventoryPage() {
  const { authFetch } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    authFetch(`${API}/inventory/summary`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Inventory</h2>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Card><CardContent className="p-4 flex items-center gap-3"><div className="h-10 w-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center"><Package size={18} /></div><div><p className="text-xs text-muted-foreground">Total Products</p><p className="text-lg font-semibold">{summary?.total_products ?? "-"}</p></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><div className="h-10 w-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center"><Warehouse size={18} /></div><div><p className="text-xs text-muted-foreground">Total Stock</p><p className="text-lg font-semibold">{summary?.total_stock ?? "-"}</p></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><div className="h-10 w-10 rounded-lg bg-red-50 text-red-600 flex items-center justify-center"><AlertTriangle size={18} /></div><div><p className="text-xs text-muted-foreground">Out of Stock</p><p className="text-lg font-semibold">{summary?.out_of_stock ?? "-"}</p></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><div className="h-10 w-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center"><TrendingDown size={18} /></div><div><p className="text-xs text-muted-foreground">Low Stock</p><p className="text-lg font-semibold">{summary?.low_stock ?? "-"}</p></div></CardContent></Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Link to="/inventory/overview" className="block">
            <Card className="transition-all hover:shadow-md hover:border-primary/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Eye size={18} /> Inventory Overview</CardTitle>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                <span>View current stock levels for all products</span>
                <ChevronRight size={16} />
              </CardContent>
            </Card>
          </Link>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <Link to="/inventory/history" className="block">
            <Card className="transition-all hover:shadow-md hover:border-primary/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><ClipboardList size={18} /> Inventory History</CardTitle>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Browse batch transactions and detailed line items</span>
                <ChevronRight size={16} />
              </CardContent>
            </Card>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
