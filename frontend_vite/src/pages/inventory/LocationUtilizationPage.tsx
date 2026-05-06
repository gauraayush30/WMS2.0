import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowLeft, MapPin, Zap, BarChart3, Settings, Plus, Trash2, X,
  ArrowRightLeft, MoveRight, RefreshCw, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { motion, AnimatePresence } from "framer-motion";

/* ── Types ──────────────────────────────────────────────────────────── */

interface LocationData {
  zone: string; aisle: string; product_count: number; total_stock: number;
  total_outbound: number; total_tx_count: number; turnover_rate: number;
  priority: number; priority_label: string;
}
interface VelocityProduct {
  id: number; name: string; sku_code: string; stock_at_warehouse: number;
  location_zone: string; location_aisle: string; location_rack: string;
  outbound_volume: number; outbound_tx_count: number; daily_avg: number;
  velocity_class: string;
}
interface Suggestion {
  type: string; priority: string; description: string;
  product?: { id: number; name: string; sku: string; velocity: string; outbound: number };
  product_a?: { id: number; name: string; sku: string; velocity: string; outbound: number };
  product_b?: { id: number; name: string; sku: string; velocity: string; outbound: number };
  current_location?: string; suggested_location?: string;
  current_location_a?: string; current_location_b?: string;
  suggested_location_a?: string; suggested_location_b?: string;
}
interface LocationConfig {
  id: number; zone: string; aisle: string; priority: number; label: string;
}

/* ── Helpers ─────────────────────────────────────────────────────────── */

const velocityColor = (v: string) =>
  v === "A" ? "success" : v === "B" ? "warning" : "secondary";
const priorityBadge = (p: string) =>
  p === "high" ? "destructive" : p === "medium" ? "warning" : "secondary";
const heatColor = (outbound: number, max: number) => {
  if (max === 0) return "bg-gray-100 text-gray-500";
  const r = outbound / max;
  if (r > 0.6) return "bg-emerald-100 text-emerald-700 border-emerald-300";
  if (r > 0.25) return "bg-amber-100 text-amber-700 border-amber-300";
  return "bg-red-100 text-red-700 border-red-300";
};
const priorityLabel = (p: number) =>
  ["", "★ Highest", "★ High", "Normal", "Low", "★ Deep Storage"][p] || "Normal";

/* ── Component ──────────────────────────────────────────────────────── */

export default function LocationUtilizationPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("suggestions");

  // Data
  const [locations, setLocations] = useState<LocationData[]>([]);
  const [products, setProducts] = useState<VelocityProduct[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [velocitySummary, setVelocitySummary] = useState<Record<string, number>>({});
  const [suggestionSummary, setSuggestionSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  // Config dialog
  const [configOpen, setConfigOpen] = useState(false);
  const [configs, setConfigs] = useState<LocationConfig[]>([]);
  const [detectedZones, setDetectedZones] = useState<{ zone: string; aisle: string }[]>([]);
  const [cfgForm, setCfgForm] = useState({ zone: "", aisle: "", priority: "3", label: "" });
  const [cfgSaving, setCfgSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ovRes, velRes, sugRes] = await Promise.all([
        authFetch(`${API}/location-utilization/overview`),
        authFetch(`${API}/location-utilization/velocity`),
        authFetch(`${API}/location-utilization/suggestions`),
      ]);
      if (ovRes.ok) { const d = await ovRes.json(); setLocations(d.locations || []); }
      if (velRes.ok) { const d = await velRes.json(); setProducts(d.products || []); setVelocitySummary(d.summary || {}); }
      if (sugRes.ok) { const d = await sugRes.json(); setSuggestions(d.suggestions || []); setSuggestionSummary(d.summary || {}); }
    } catch { /* ignore */ }
    setLoading(false);
  }, [authFetch]);

  const fetchConfig = useCallback(async () => {
    try {
      const r = await authFetch(`${API}/location-utilization/config`);
      if (r.ok) { const d = await r.json(); setConfigs(d.configs || []); setDetectedZones(d.detected_zones || []); }
    } catch { /* ignore */ }
  }, [authFetch]);

  useEffect(() => { fetchAll(); fetchConfig(); }, [fetchAll, fetchConfig]);

  const handleSaveConfig = async () => {
    if (!cfgForm.zone.trim()) return;
    setCfgSaving(true);
    try {
      await authFetch(`${API}/location-utilization/config`, {
        method: "POST",
        body: JSON.stringify({
          zone: cfgForm.zone.trim(), aisle: cfgForm.aisle.trim(),
          priority: parseInt(cfgForm.priority) || 3, label: cfgForm.label.trim(),
        }),
      });
      setCfgForm({ zone: "", aisle: "", priority: "3", label: "" });
      await fetchConfig();
      await fetchAll();
    } catch { /* ignore */ }
    setCfgSaving(false);
  };

  const handleDeleteConfig = async (id: number) => {
    await authFetch(`${API}/location-utilization/config/${id}`, { method: "DELETE" });
    await fetchConfig();
    await fetchAll();
  };

  const maxOutbound = Math.max(...locations.map(l => l.total_outbound), 1);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-3 gap-4">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => navigate("/inventory")}><ArrowLeft size={14} /> Back</Button>
        <div className="flex items-center gap-2">
          <MapPin size={18} className="text-primary" />
          <h2 className="text-xl font-bold">Location Utilization</h2>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchAll}><RefreshCw size={14} /> Refresh</Button>
          <Button variant="outline" size="sm" onClick={() => { setConfigOpen(true); fetchConfig(); }}><Settings size={14} /> Configure Zones</Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total Suggestions</p><p className="text-2xl font-bold">{suggestions.length}</p></CardContent></Card>
        <Card className={suggestionSummary.high > 0 ? "border-red-200" : ""}><CardContent className="p-4"><p className="text-xs text-muted-foreground">High Priority</p><p className="text-2xl font-bold text-red-600">{suggestionSummary.high || 0}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Active Zones</p><p className="text-2xl font-bold">{new Set(locations.map(l => l.zone)).size}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Products Tracked</p><p className="text-2xl font-bold">{products.length}</p></CardContent></Card>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="suggestions"><Zap size={14} className="mr-1.5" />Suggestions{suggestions.length > 0 && <Badge variant="destructive" className="ml-2 text-[10px] h-5">{suggestions.length}</Badge>}</TabsTrigger>
          <TabsTrigger value="heatmap"><MapPin size={14} className="mr-1.5" />Heatmap</TabsTrigger>
          <TabsTrigger value="velocity"><BarChart3 size={14} className="mr-1.5" />Product Velocity</TabsTrigger>
        </TabsList>

        {/* ── Suggestions Tab ─────────────────────── */}
        <TabsContent value="suggestions">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3 mt-4">
            {suggestions.length === 0 ? (
              <Card><CardContent className="py-12 text-center text-muted-foreground">
                <Zap size={32} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm font-medium">No suggestions right now</p>
                <p className="text-xs mt-1">Configure zone priorities and add products with locations to get smart placement suggestions.</p>
              </CardContent></Card>
            ) : (
              suggestions.map((s, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                  <Card className={s.priority === "high" ? "border-red-200 bg-red-50/30" : s.priority === "medium" ? "border-amber-200 bg-amber-50/20" : ""}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${s.type === "swap" ? "bg-purple-100 text-purple-600" : s.type === "relocate_fast" ? "bg-red-100 text-red-600" : s.type === "move_slow" ? "bg-amber-100 text-amber-600" : "bg-blue-100 text-blue-600"}`}>
                          {s.type === "swap" ? <ArrowRightLeft size={16} /> : <MoveRight size={16} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <Badge variant={priorityBadge(s.priority) as "destructive" | "warning" | "secondary"} className="text-[10px]">
                              {s.priority.toUpperCase()}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] capitalize">{s.type.replace(/_/g, " ")}</Badge>
                          </div>
                          <p className="text-sm leading-relaxed">{s.description}</p>
                          {s.type === "swap" ? (
                            <div className="flex gap-2 mt-3">
                              <Button size="sm" variant="outline" onClick={() => navigate(`/products/${s.product_a?.id}/edit`)}><Settings size={12} /> Edit {s.product_a?.name?.slice(0, 15)}</Button>
                              <Button size="sm" variant="outline" onClick={() => navigate(`/products/${s.product_b?.id}/edit`)}><Settings size={12} /> Edit {s.product_b?.name?.slice(0, 15)}</Button>
                            </div>
                          ) : s.product?.id ? (
                            <Button size="sm" variant="outline" className="mt-3" onClick={() => navigate(`/products/${s.product!.id}/edit`)}>
                              <Settings size={12} /> Edit Location <ChevronRight size={12} />
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))
            )}
          </motion.div>
        </TabsContent>

        {/* ── Heatmap Tab ─────────────────────────── */}
        <TabsContent value="heatmap">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4">
            {locations.length === 0 ? (
              <Card><CardContent className="py-12 text-center text-muted-foreground">
                <MapPin size={32} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">No products with warehouse locations found.</p>
              </CardContent></Card>
            ) : (
              <>
                <div className="flex items-center gap-4 mb-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-200 inline-block" /> High activity</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-200 inline-block" /> Medium</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-200 inline-block" /> Low / Idle</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {locations.map((loc, i) => (
                    <motion.div key={i} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.03 }}>
                      <Card className={`border-2 transition-all hover:shadow-md ${heatColor(loc.total_outbound, maxOutbound)}`}>
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-bold">{loc.zone}{loc.aisle ? ` / ${loc.aisle}` : ""}</h4>
                            <Badge variant="outline" className="text-[10px]">P{loc.priority}</Badge>
                          </div>
                          {loc.priority_label && <p className="text-[10px] mb-2 opacity-70">{loc.priority_label}</p>}
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                            <span className="text-muted-foreground">Products</span><span className="font-semibold text-right">{loc.product_count}</span>
                            <span className="text-muted-foreground">Stock</span><span className="font-semibold text-right">{loc.total_stock}</span>
                            <span className="text-muted-foreground">Outbound</span><span className="font-semibold text-right">{loc.total_outbound}</span>
                            <span className="text-muted-foreground">Turnover</span><span className="font-semibold text-right">{loc.turnover_rate}x</span>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              </>
            )}
          </motion.div>
        </TabsContent>

        {/* ── Velocity Tab ────────────────────────── */}
        <TabsContent value="velocity">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4 mt-4">
            <div className="flex gap-3">
              <Badge variant="success" className="text-xs">A: Fast ({velocitySummary.A || 0})</Badge>
              <Badge variant="warning" className="text-xs">B: Medium ({velocitySummary.B || 0})</Badge>
              <Badge variant="secondary" className="text-xs">C: Slow ({velocitySummary.C || 0})</Badge>
            </div>
            {products.length === 0 ? (
              <Card><CardContent className="py-12 text-center text-muted-foreground"><p className="text-sm">No products found.</p></CardContent></Card>
            ) : (
              <Card className="overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Product</TableHead>
                      <TableHead>SKU</TableHead>
                      <TableHead>Class</TableHead>
                      <TableHead className="text-right">Outbound (90d)</TableHead>
                      <TableHead className="text-right">Daily Avg</TableHead>
                      <TableHead>Location</TableHead>
                      <TableHead className="text-right">Stock</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {products.map((p) => (
                      <TableRow key={p.id} className={p.velocity_class === "A" ? "bg-emerald-50/40" : p.velocity_class === "C" ? "bg-amber-50/30" : ""}>
                        <TableCell className="font-medium text-sm">{p.name}</TableCell>
                        <TableCell><code className="text-xs">{p.sku_code}</code></TableCell>
                        <TableCell><Badge variant={velocityColor(p.velocity_class) as "success" | "warning" | "secondary"}>{p.velocity_class}</Badge></TableCell>
                        <TableCell className="text-right text-sm font-semibold">{p.outbound_volume}</TableCell>
                        <TableCell className="text-right text-sm">{p.daily_avg}</TableCell>
                        <TableCell className="text-xs">{p.location_zone ? `${p.location_zone}${p.location_aisle ? ` / ${p.location_aisle}` : ""}${p.location_rack ? ` / R${p.location_rack}` : ""}` : <span className="text-muted-foreground">—</span>}</TableCell>
                        <TableCell className="text-right text-sm">{p.stock_at_warehouse}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </motion.div>
        </TabsContent>
      </Tabs>

      {/* ── Config Dialog ──────────────────────────── */}
      <AnimatePresence>
        {configOpen && (
          <>
            <motion.div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setConfigOpen(false)} />
            <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}>
              <div className="bg-background rounded-xl shadow-2xl border w-full max-w-lg max-h-[85vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b bg-muted/30">
                  <h3 className="text-sm font-bold flex items-center gap-2"><Settings size={16} /> Zone Priority Configuration</h3>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setConfigOpen(false)}><X size={16} /></Button>
                </div>
                <div className="overflow-auto flex-1 px-6 py-4 space-y-4">
                  <p className="text-xs text-muted-foreground">Set accessibility priority for each zone. Priority 1 = most accessible (near door), 5 = deep storage.</p>

                  {/* Add form */}
                  <div className="grid grid-cols-4 gap-2">
                    <div className="space-y-1"><Label className="text-[10px]">Zone *</Label><Input placeholder="A" value={cfgForm.zone} onChange={e => setCfgForm(f => ({ ...f, zone: e.target.value }))} className="h-8 text-xs" /></div>
                    <div className="space-y-1"><Label className="text-[10px]">Aisle</Label><Input placeholder="1" value={cfgForm.aisle} onChange={e => setCfgForm(f => ({ ...f, aisle: e.target.value }))} className="h-8 text-xs" /></div>
                    <div className="space-y-1"><Label className="text-[10px]">Priority</Label>
                      <select className="w-full h-8 rounded-md border text-xs px-2 bg-background" value={cfgForm.priority} onChange={e => setCfgForm(f => ({ ...f, priority: e.target.value }))}>
                        <option value="1">1 - Near Door</option><option value="2">2 - High</option><option value="3">3 - Normal</option><option value="4">4 - Low</option><option value="5">5 - Deep</option>
                      </select>
                    </div>
                    <div className="space-y-1"><Label className="text-[10px]">Label</Label>
                      <div className="flex gap-1"><Input placeholder="Near dock" value={cfgForm.label} onChange={e => setCfgForm(f => ({ ...f, label: e.target.value }))} className="h-8 text-xs" />
                        <Button size="sm" className="h-8 px-2" onClick={handleSaveConfig} disabled={cfgSaving}><Plus size={14} /></Button>
                      </div>
                    </div>
                  </div>

                  {/* Detected zones hint */}
                  {detectedZones.length > 0 && (
                    <div>
                      <p className="text-[10px] text-muted-foreground mb-1">Detected zones from your products:</p>
                      <div className="flex flex-wrap gap-1">
                        {detectedZones.map((z, i) => (
                          <Badge key={i} variant="outline" className="text-[10px] cursor-pointer hover:bg-muted" onClick={() => setCfgForm(f => ({ ...f, zone: z.zone, aisle: z.aisle || "" }))}>
                            {z.zone}{z.aisle ? ` / ${z.aisle}` : ""}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Existing configs */}
                  {configs.length > 0 ? (
                    <Table>
                      <TableHeader><TableRow><TableHead>Zone</TableHead><TableHead>Aisle</TableHead><TableHead>Priority</TableHead><TableHead>Label</TableHead><TableHead className="w-10" /></TableRow></TableHeader>
                      <TableBody>
                        {configs.map(c => (
                          <TableRow key={c.id}>
                            <TableCell className="text-xs font-medium">{c.zone}</TableCell>
                            <TableCell className="text-xs">{c.aisle || "—"}</TableCell>
                            <TableCell><Badge variant={c.priority <= 2 ? "success" : c.priority >= 4 ? "warning" : "secondary"} className="text-[10px]">{c.priority} - {priorityLabel(c.priority)}</Badge></TableCell>
                            <TableCell className="text-xs">{c.label || "—"}</TableCell>
                            <TableCell><Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={() => handleDeleteConfig(c.id)}><Trash2 size={12} /></Button></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="text-xs text-muted-foreground text-center py-4">No zone priorities configured yet. Add zones above to enable smart placement suggestions.</p>
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
