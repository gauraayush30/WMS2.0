import { useEffect, useState } from "react";
import { Recycle, AlertTriangle } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
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

interface Compliance {
  total_picks: number;
  total_qty: number;
  fifo_compliant_picks: number;
  fefo_compliant_picks: number;
  fifo_compliance_pct: number | null;
  fefo_compliance_pct: number | null;
}

interface AgingBucket {
  bucket: string;
  sku_count: number;
  units: number;
  value: number;
}

interface ExpiryItem {
  batch_id: number;
  product_id: number;
  product_name: string;
  sku_code: string;
  remaining_qty: number;
  expires_at: string | null;
  days_to_expiry: number | null;
  value_at_risk: number;
}

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function FifoFefoPage() {
  const { authFetch, effectiveCustomerId } = useAuth();
  const [comp, setComp] = useState<Compliance | null>(null);
  const [aging, setAging] = useState<AgingBucket[]>([]);
  const [expiry, setExpiry] = useState<ExpiryItem[]>([]);

  useEffect(() => {
    const cs = effectiveCustomerId
      ? `customer_id=${effectiveCustomerId}`
      : "";
    Promise.all([
      authFetch(`${API}/analytics/fifo-fefo?${cs}`).then((r) =>
        r.ok ? r.json() : null,
      ),
      authFetch(`${API}/analytics/aging?${cs}`).then((r) =>
        r.ok ? r.json() : { buckets: [] },
      ),
      authFetch(`${API}/analytics/expiry-risk?days=30&${cs}`).then((r) =>
        r.ok ? r.json() : { items: [] },
      ),
    ]).then(([c, a, e]) => {
      setComp(c);
      setAging(a.buckets || []);
      setExpiry(e.items || []);
    });
  }, [authFetch, effectiveCustomerId]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <Recycle className="text-muted-foreground" />
        <h1 className="text-2xl font-semibold">FIFO / FEFO + Aging</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">FIFO compliance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-semibold">
              {comp?.fifo_compliance_pct == null
                ? "—"
                : `${comp.fifo_compliance_pct.toFixed(1)}%`}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {comp?.fifo_compliant_picks ?? 0} of {comp?.total_picks ?? 0} picks
              consumed the oldest available batch (by purchased_at).
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">FEFO compliance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-semibold">
              {comp?.fefo_compliance_pct == null
                ? "—"
                : `${comp.fefo_compliance_pct.toFixed(1)}%`}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {comp?.fefo_compliant_picks ?? 0} of {comp?.total_picks ?? 0} picks
              consumed the earliest-expiring batch.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Stock aging</CardTitle>
        </CardHeader>
        <CardContent>
          {aging.length === 0 ? (
            <div className="text-sm text-muted-foreground">No active stock.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Age (days)</TableHead>
                  <TableHead>SKUs</TableHead>
                  <TableHead>Units</TableHead>
                  <TableHead>Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {aging.map((b) => (
                  <TableRow key={b.bucket}>
                    <TableCell>
                      <Badge variant="outline">{b.bucket}</Badge>
                    </TableCell>
                    <TableCell>{b.sku_count}</TableCell>
                    <TableCell>{Number(b.units).toLocaleString("en-IN")}</TableCell>
                    <TableCell>{fmtINR(Number(b.value))}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle size={14} className="text-amber-600" />
            Expiry risk (next 30 days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {expiry.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No batches expiring in the next 30 days.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Remaining</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Days left</TableHead>
                  <TableHead>Value at risk</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expiry.map((e) => (
                  <TableRow key={e.batch_id}>
                    <TableCell className="font-mono text-xs">{e.sku_code}</TableCell>
                    <TableCell>{e.product_name}</TableCell>
                    <TableCell>{e.remaining_qty}</TableCell>
                    <TableCell>{e.expires_at}</TableCell>
                    <TableCell>{e.days_to_expiry}</TableCell>
                    <TableCell>{fmtINR(Number(e.value_at_risk))}</TableCell>
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
