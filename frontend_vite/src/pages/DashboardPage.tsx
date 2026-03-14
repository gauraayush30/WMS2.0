import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import { Package, MapPin, AlertTriangle, XCircle, RefreshCw, Pencil } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";

interface DashboardStats {
  total_products: number;
  products_without_location: number;
  low_stock_products: number;
  out_of_stock_products: number;
}

interface UnlocatedProduct {
  id: number;
  name: string;
  sku_code: string;
  stock_at_warehouse: number;
}

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.05, duration: 0.35 } }),
};

export default function DashboardPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [unlocated, setUnlocated] = useState<UnlocatedProduct[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(() => {
    setLoading(true);
    Promise.all([
      authFetch(`${API}/dashboard/stats`).then((r) => r.json()),
      authFetch(`${API}/dashboard/products-without-location`).then((r) => r.json()),
    ])
      .then(([statsData, unlocatedData]) => {
        setStats(statsData);
        setUnlocated(unlocatedData.products || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-8 w-24" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const statCards = [
    { label: "Total Products", value: stats?.total_products ?? 0, icon: Package, color: "bg-blue-50 text-blue-600" },
    { label: "Without Location", value: stats?.products_without_location ?? 0, icon: MapPin, color: "bg-orange-50 text-orange-600", warn: (stats?.products_without_location ?? 0) > 0 },
    { label: "Low Stock", value: stats?.low_stock_products ?? 0, icon: AlertTriangle, color: "bg-amber-50 text-amber-600", warn: (stats?.low_stock_products ?? 0) > 0 },
    { label: "Out of Stock", value: stats?.out_of_stock_products ?? 0, icon: XCircle, color: "bg-red-50 text-red-600", warn: (stats?.out_of_stock_products ?? 0) > 0 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <Button variant="outline" size="sm" onClick={fetchDashboard}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <motion.div key={s.label} custom={i} initial="hidden" animate="show" variants={fadeUp}>
            <Card className={s.warn ? "border-amber-200" : ""}>
              <CardContent className="flex items-center gap-4 p-5">
                <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${s.color}`}>
                  <s.icon size={20} />
                </div>
                <div>
                  <p className="text-2xl font-bold leading-none">{s.value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Alert Banners */}
      <div className="space-y-3">
        {(stats?.products_without_location ?? 0) > 0 && (
          <Alert variant="warning">
            <div>
              <strong>{stats!.products_without_location} product{stats!.products_without_location > 1 ? "s" : ""} without warehouse location</strong>
              <p className="text-xs mt-0.5 opacity-80">Assign warehouse locations to enable pick-list generation.</p>
            </div>
          </Alert>
        )}
        {(stats?.low_stock_products ?? 0) > 0 && (
          <Alert variant="info">
            <strong>{stats!.low_stock_products}</strong> product{stats!.low_stock_products > 1 ? "s are" : " is"} below reorder point.
          </Alert>
        )}
        {(stats?.out_of_stock_products ?? 0) > 0 && (
          <Alert variant="destructive">
            <strong>{stats!.out_of_stock_products}</strong> product{stats!.out_of_stock_products > 1 ? "s are" : " is"} out of stock.
          </Alert>
        )}
      </div>

      {/* Products Without Location Table */}
      {unlocated.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <Card>
            <div className="flex items-center gap-2 p-5 pb-0">
              <MapPin size={16} className="text-muted-foreground" />
              <h3 className="text-sm font-semibold">Products Without Warehouse Location</h3>
            </div>
            <CardContent className="p-0 pt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>SKU Code</TableHead>
                    <TableHead>Stock</TableHead>
                    <TableHead className="w-[120px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {unlocated.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell><code className="text-xs bg-muted px-1.5 py-0.5 rounded">{p.sku_code}</code></TableCell>
                      <TableCell>{p.stock_at_warehouse}</TableCell>
                      <TableCell>
                        <Button size="sm" onClick={() => navigate(`/products/${p.id}/edit`)}>
                          <Pencil size={12} /> Set Location
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
