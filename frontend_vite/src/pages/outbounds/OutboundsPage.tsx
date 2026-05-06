import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Truck } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface OutboundOrder {
  id: number;
  shipment_number: string;
  status: string;
  total_qty: number;
  total_amount: number;
  shipped_at: string;
  pick_strategy: string;
  so_number: string;
  customer_name: string | null;
  customer_code: string | null;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  draft: "outline",
  shipped: "default",
  cancelled: "secondary",
};

export default function OutboundsPage() {
  const { authFetch, effectiveCustomerId, selectedWarehouseId, isWarehouse } = useAuth();
  const [orders, setOrders] = useState<OutboundOrder[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (effectiveCustomerId) params.set("customer_id", String(effectiveCustomerId));
    if (selectedWarehouseId) params.set("warehouse_id", String(selectedWarehouseId));
    const r = await authFetch(`${API}/outbounds?${params.toString()}`);
    if (r.ok) {
      const d = await r.json();
      setOrders(d.items || []);
    }
    setLoading(false);
  }, [authFetch, effectiveCustomerId, selectedWarehouseId]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Truck className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Outbounds (Shipments)</h1>
        </div>
        <Button asChild>
          <Link to="/outbounds/new">
            <Plus size={16} /> New outbound
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent shipments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : orders.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No outbound orders yet. Create one to ship stock.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ship #</TableHead>
                  <TableHead>SO #</TableHead>
                  {isWarehouse && !effectiveCustomerId && <TableHead>Customer</TableHead>}
                  <TableHead>Shipped</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Amount (₹)</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((o) => (
                  <TableRow key={o.id}>
                    <TableCell className="font-mono text-xs">
                      {o.shipment_number}
                    </TableCell>
                    <TableCell className="text-sm">{o.so_number || "—"}</TableCell>
                    {isWarehouse && !effectiveCustomerId && (
                      <TableCell className="text-xs text-muted-foreground">
                        {o.customer_name || "—"}
                        {o.customer_code && <span className="ml-1 opacity-60">({o.customer_code})</span>}
                      </TableCell>
                    )}
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(o.shipped_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>{o.total_qty}</TableCell>
                    <TableCell>
                      {Number(o.total_amount).toLocaleString("en-IN")}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">
                        {o.pick_strategy}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[o.status] || "outline"}>
                        {o.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link to={`/outbounds/${o.id}`}>View</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
