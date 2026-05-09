import { useEffect, useState, useMemo } from "react";
import { API, useAuth } from "../../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, Search } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface OutboundDetail {
  shipment_number: string;
  date: string;
  buyer_name: string;
  location: string;
  product_name: string;
  sku_code: string;
  quantity: number;
  price: number;
  batch_code: string | null;
}

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function OutboundDetailsPage() {
  const { authFetch } = useAuth();
  const [items, setItems] = useState<OutboundDetail[]>([]);
  const [buyerFilter, setBuyerFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");

  useEffect(() => {
    authFetch(`${API}/reports/outbound-details?days=30`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((data) => setItems(data.items || []));
  }, [authFetch]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchBuyer = (item.buyer_name || "").toLowerCase().includes(buyerFilter.toLowerCase());
      const matchLocation = (item.location || "").toLowerCase().includes(locationFilter.toLowerCase());
      if (buyerFilter && !matchBuyer) return false;
      if (locationFilter && !matchLocation) return false;
      return true;
    });
  }, [items, buyerFilter, locationFilter]);

  const downloadCSV = () => {
    if (filteredItems.length === 0) return;
    
    const headers = ["Date", "Shipment No", "Buyer", "Location", "Product", "SKU", "Qty", "Unit Price", "Batch No"];
    const csvRows = [headers.join(",")];
    
    for (const item of filteredItems) {
      const row = [
        item.date,
        item.shipment_number,
        `"${(item.buyer_name || "").replace(/"/g, '""')}"`,
        `"${(item.location || "").replace(/"/g, '""')}"`,
        `"${(item.product_name || "").replace(/"/g, '""')}"`,
        `"${(item.sku_code || "").replace(/"/g, '""')}"`,
        item.quantity,
        item.price,
        `"${(item.batch_code || "—").replace(/"/g, '""')}"`
      ];
      csvRows.push(row.join(","));
    }
    
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `outbound_details_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Upload className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Outbound Details</h1>
        </div>
        <Button variant="outline" onClick={downloadCSV} disabled={filteredItems.length === 0}>
          <Upload className="mr-2 h-4 w-4" />
          Download CSV
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-3 border-b">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            <CardTitle className="text-sm">Stock Out (Last 30 days)</CardTitle>
            <div className="flex gap-2 w-full sm:w-auto">
              <div className="relative w-full sm:w-48">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Filter buyer..."
                  className="pl-8"
                  value={buyerFilter}
                  onChange={(e) => setBuyerFilter(e.target.value)}
                />
              </div>
              <div className="relative w-full sm:w-48">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Filter location..."
                  className="pl-8"
                  value={locationFilter}
                  onChange={(e) => setLocationFilter(e.target.value)}
                />
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          {filteredItems.length === 0 ? (
            <div className="text-sm text-muted-foreground">No outbound records found.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Shipment No</TableHead>
                  <TableHead>Buyer</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Unit Price</TableHead>
                  <TableHead>Batch No</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item, i) => (
                  <TableRow key={i}>
                    <TableCell>{item.date}</TableCell>
                    <TableCell className="font-mono text-xs">{item.shipment_number}</TableCell>
                    <TableCell>{item.buyer_name}</TableCell>
                    <TableCell>{item.location}</TableCell>
                    <TableCell>{item.product_name}</TableCell>
                    <TableCell className="font-mono text-xs">{item.sku_code}</TableCell>
                    <TableCell>{item.quantity}</TableCell>
                    <TableCell>{fmtINR(item.price)}</TableCell>
                    <TableCell className="font-mono text-xs">{item.batch_code || "—"}</TableCell>
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
