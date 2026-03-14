import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface ProductStock {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  updated_at: string;
}

export default function InventoryOverviewPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [products, setProducts] = useState<ProductStock[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await authFetch(
          `${API}/inventory/overview?page=${page}&per_page=18&search=${encodeURIComponent(search)}`,
        );
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
  }, [authFetch, page, search]);

  const stockVariant = (stock: number) => {
    if (stock === 0) return "destructive" as const;
    if (stock <= 10) return "warning" as const;
    return "success" as const;
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
                <TableHead className="text-right">Stock</TableHead>
                <TableHead>UOM</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium text-sm">{p.name}</TableCell>
                  <TableCell><code className="text-xs">{p.sku_code}</code></TableCell>
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
    </div>
  );
}
