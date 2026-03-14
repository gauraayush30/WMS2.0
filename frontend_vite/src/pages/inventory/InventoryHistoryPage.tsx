import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft, ArrowUpCircle, ArrowDownCircle, ClipboardList, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface Batch {
  id: number;
  reason: string;
  reference_no: string | null;
  notes: string;
  total_items: number;
  total_amount: number;
  transaction_at: string;
  created_at: string;
  created_by_name: string;
}

interface BatchLineItem {
  id: number;
  product_id: number;
  product_name: string;
  sku_code: string;
  price: number;
  stock_adjusted: number;
  previous_stock: number;
  current_stock: number;
}

interface BatchDetail extends Batch {
  items: BatchLineItem[];
}

const REASON_OPTIONS = ["delivery", "shipment", "adjustment", "return", "damage", "transfer"];

export default function InventoryHistoryPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [batches, setBatches] = useState<Batch[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);

  const [filterReason, setFilterReason] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchBatches = useCallback(() => {
    setLoading(true);
    let url = `${API}/inventory/batches?page=${page}&per_page=15`;
    if (filterReason) url += `&reason=${filterReason}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    authFetch(url)
      .then((r) => r.json())
      .then((data) => {
        setBatches(data.batches || []);
        setTotalPages(data.total_pages || 0);
      })
      .catch(() => {
        setBatches([]);
        setTotalPages(0);
      })
      .finally(() => setLoading(false));
  }, [authFetch, page, filterReason, startDate, endDate]);

  useEffect(() => {
    fetchBatches();
  }, [fetchBatches]);

  const loadDetail = async (batchId: number) => {
    setDetailLoading(true);
    try {
      const res = await authFetch(`${API}/inventory/batches/${batchId}`);
      const data = await res.json();
      setSelectedBatch(data);
    } catch {
      setSelectedBatch(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const reasonBadge = (reason: string) => (
    <Badge variant="secondary" className="capitalize">{reason.replace("_", " ")}</Badge>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate("/inventory")}>
          <ArrowLeft size={14} /> Back
        </Button>
        <h2 className="text-xl font-bold">Inventory History</h2>
      </div>

      <Card>
        <CardContent className="p-4 flex flex-wrap items-center gap-2">
          <Filter size={14} className="text-muted-foreground" />
          <Select value={filterReason} onChange={(e) => { setFilterReason(e.target.value); setPage(1); }}>
            <option value="">All Reasons</option>
            {REASON_OPTIONS.map((r) => (
              <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </Select>
          <Input type="date" className="w-40" value={startDate} onChange={(e) => { setStartDate(e.target.value); setPage(1); }} />
          <Input type="date" className="w-40" value={endDate} onChange={(e) => { setEndDate(e.target.value); setPage(1); }} />
          {(filterReason || startDate || endDate) && (
            <Button variant="outline" size="sm" onClick={() => { setFilterReason(""); setStartDate(""); setEndDate(""); setPage(1); }}>Clear</Button>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-[420px,1fr] gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Transactions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              <div className="space-y-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-16 rounded-lg" />)}</div>
            ) : batches.length === 0 ? (
              <div className="text-center text-muted-foreground py-10">
                <ClipboardList size={36} className="mx-auto mb-2 opacity-60" />
                <p>No batch transactions yet.</p>
              </div>
            ) : (
              <>
                {batches.map((b) => (
                  <button
                    key={b.id}
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors hover:bg-muted/50 ${selectedBatch?.id === b.id ? "border-primary bg-primary/5" : ""}`}
                    onClick={() => loadDetail(b.id)}
                  >
                    <div className="flex items-center justify-between mb-1">
                      {reasonBadge(b.reason)}
                      <span className="text-xs text-muted-foreground">{new Date(b.transaction_at).toLocaleDateString()}</span>
                    </div>
                    <div className="text-sm font-medium">{b.reference_no || "No reference"}</div>
                    <div className="text-xs text-muted-foreground flex items-center justify-between mt-1">
                      <span>{b.total_items} items</span>
                      <span>₹{Number(b.total_amount).toFixed(2)}</span>
                    </div>
                  </button>
                ))}

                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2">
                    <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</Button>
                    <span className="text-xs text-muted-foreground">{page}/{totalPages}</span>
                    <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Transaction Details</CardTitle>
          </CardHeader>
          <CardContent>
            {detailLoading ? (
              <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
            ) : selectedBatch ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  {reasonBadge(selectedBatch.reason)}
                  <span className="text-sm font-medium">{selectedBatch.reference_no || "No Reference"}</span>
                  <span className="text-xs text-muted-foreground">{new Date(selectedBatch.transaction_at).toLocaleString()}</span>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Total Items</p><p className="text-sm font-semibold">{selectedBatch.total_items}</p></CardContent></Card>
                  <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Total Amount</p><p className="text-sm font-semibold">₹{Number(selectedBatch.total_amount).toFixed(2)}</p></CardContent></Card>
                  <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Products</p><p className="text-sm font-semibold">{selectedBatch.items.length}</p></CardContent></Card>
                  <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Created By</p><p className="text-sm font-semibold">{selectedBatch.created_by_name}</p></CardContent></Card>
                </div>

                {selectedBatch.notes && (
                  <p className="text-sm text-muted-foreground"><span className="font-medium text-foreground">Notes:</span> {selectedBatch.notes}</p>
                )}

                <div className="rounded-lg border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Product</TableHead>
                        <TableHead>Adjustment</TableHead>
                        <TableHead>Before</TableHead>
                        <TableHead>After</TableHead>
                        <TableHead>Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedBatch.items.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>
                            <div className="text-sm font-medium">{item.product_name}</div>
                            <div className="text-xs text-muted-foreground">{item.sku_code}</div>
                          </TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center gap-1 text-xs font-medium ${item.stock_adjusted >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                              {item.stock_adjusted >= 0 ? <ArrowUpCircle size={13} /> : <ArrowDownCircle size={13} />}
                              {item.stock_adjusted >= 0 ? "+" : ""}{item.stock_adjusted}
                            </span>
                          </TableCell>
                          <TableCell className="text-sm">{item.previous_stock}</TableCell>
                          <TableCell className="text-sm font-medium">{item.current_stock}</TableCell>
                          <TableCell className="text-sm">₹{(Math.abs(item.stock_adjusted) * item.price).toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-14">
                <ClipboardList size={38} className="mx-auto mb-2 opacity-60" />
                <p>Select a transaction to view details</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
