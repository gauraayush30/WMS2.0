import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import { Plus, Search, MoreVertical, Eye, Pencil, Trash2, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  location_zone: string;
  location_aisle: string;
  location_rack: string;
  location_shelf: string;
  location_level: string;
  location_bin: string;
  created_at: string;
  updated_at: string;
}

export default function ProductsPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const searchRef = useRef<ReturnType<typeof setTimeout>>();

  const fetchProducts = useCallback(() => {
    setLoading(true);
    authFetch(`${API}/products?page=${page}&per_page=15&search=${encodeURIComponent(search)}`)
      .then((r) => r.json())
      .then((data) => {
        setProducts(data.products || []);
        setTotalPages(data.total_pages || 0);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch, page, search]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const handleSearch = (v: string) => {
    clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => { setSearch(v); setPage(1); }, 300);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this product? All related inventory transactions will also be deleted.")) return;
    try {
      const res = await authFetch(`${API}/products/${id}`, { method: "DELETE" });
      if (!res.ok) { const err = await res.json().catch(() => ({})); alert(err.detail || "Failed to delete"); return; }
      fetchProducts();
    } catch { alert("Error deleting product"); }
  };

  const stockBadge = (stock: number) => {
    if (stock === 0) return <Badge variant="destructive">{stock}</Badge>;
    if (stock <= 10) return <Badge variant="warning">{stock}</Badge>;
    return <Badge variant="success">{stock}</Badge>;
  };

  const hasLocation = (p: Product) =>
    !!(p.location_zone || p.location_aisle || p.location_rack || p.location_shelf || p.location_level || p.location_bin);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold tracking-tight">Products</h2>
          <Badge variant="secondary" className="text-xs">{total} total</Badge>
        </div>
        <Button onClick={() => navigate("/products/create")}>
          <Plus size={16} /> Add Product
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search by name or SKU..."
          className="pl-9"
          defaultValue={search}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}
        </div>
      ) : products.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Package size={40} className="mb-3 opacity-30" />
            <p>No products found.</p>
          </CardContent>
        </Card>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
          <Card className="overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>SKU Code</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>UOM</TableHead>
                  <TableHead>Stock</TableHead>
                  <TableHead className="w-12">Loc</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((p) => (
                  <TableRow key={p.id} className="cursor-pointer" onClick={() => navigate(`/products/${p.id}`)}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell><code className="text-xs bg-muted px-1.5 py-0.5 rounded">{p.sku_code}</code></TableCell>
                    <TableCell>₹{Number(p.price).toFixed(2)}</TableCell>
                    <TableCell className="text-muted-foreground">{p.uom || "pcs"}</TableCell>
                    <TableCell>{stockBadge(p.stock_at_warehouse)}</TableCell>
                    <TableCell>
                      <MapPin size={14} className={hasLocation(p) ? "text-emerald-500" : "text-muted-foreground/40"} />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">{new Date(p.updated_at).toLocaleDateString()}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu
                        trigger={
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical size={14} />
                          </Button>
                        }
                      >
                        <DropdownMenuItem onClick={() => navigate(`/products/${p.id}`)}>
                          <Eye size={14} /> View
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigate(`/products/${p.id}/edit`)}>
                          <Pencil size={14} /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem destructive onClick={() => handleDelete(p.id)}>
                          <Trash2 size={14} /> Delete
                        </DropdownMenuItem>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </motion.div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 py-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
