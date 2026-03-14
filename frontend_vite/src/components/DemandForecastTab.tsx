import { useCallback, useEffect, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Upload,
  Download,
  Brain,
  TrendingDown,
  BarChart3,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Trash2,
  FileSpreadsheet,
  RefreshCw,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  ReferenceLine,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";

interface ModelStatus {
  has_model: boolean;
  status?: string;
  trained_at?: string;
  data_start_date?: string;
  data_end_date?: string;
  total_data_points?: number;
  cv_mae?: number;
  cv_mape?: number;
  features_used?: string[];
}

interface TrainingDataSummary {
  auto_data: {
    count: number;
    date_range: { start: string; end: string } | null;
  };
  uploaded_data: {
    count: number;
    date_range: { start: string; end: string } | null;
  };
  merged: { count: number; date_range: { start: string; end: string } | null };
}

interface PredictionDay {
  date: string;
  predicted_outbound: number;
  predicted_inbound: number;
  projected_stock: number;
}

interface PredictionResult {
  product_id: number;
  days_ahead: number;
  current_stock: number;
  stockout_date: string | null;
  predictions: PredictionDay[];
}

export default function DemandForecastTab({
  productId,
}: {
  productId: string;
}) {
  const { authFetch } = useAuth();
  const [tab, setTab] = useState("overview");
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [trainingData, setTrainingData] = useState<TrainingDataSummary | null>(
    null,
  );
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [days, setDays] = useState(30);
  const [msg, setMsg] = useState<{
    type: "success" | "destructive" | "warning";
    text: string;
  } | null>(null);

  const base = `${API}/products/${productId}/forecast`;

  const fetchStatus = useCallback(async () => {
    try {
      const [sRes, tRes] = await Promise.all([
        authFetch(`${base}/status`),
        authFetch(`${base}/training-data`),
      ]);
      if (sRes.ok) setStatus(await sRes.json());
      if (tRes.ok) setTrainingData(await tRes.json());
    } catch {
      /* ignore */
    }
  }, [authFetch, base]);

  useEffect(() => {
    setLoading(true);
    fetchStatus().finally(() => setLoading(false));
  }, [fetchStatus]);

  const handleTrain = async () => {
    setTraining(true);
    setMsg(null);
    try {
      const res = await authFetch(`${base}/train`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setMsg({ type: "destructive", text: data.detail || "Training failed" });
        return;
      }
      setMsg({
        type: "success",
        text: `Model trained! MAE: ${data.cv_mae?.toFixed(1)}, MAPE: ${data.cv_mape?.toFixed(1)}%`,
      });
      await fetchStatus();
    } catch {
      setMsg({ type: "destructive", text: "Training request failed" });
    } finally {
      setTraining(false);
    }
  };

  const handlePredict = async () => {
    setPredicting(true);
    setMsg(null);
    try {
      const res = await authFetch(`${base}/predict?days=${days}`);
      const data = await res.json();
      if (!res.ok) {
        setMsg({
          type: "destructive",
          text: data.detail || "Prediction failed",
        });
        return;
      }
      setPrediction(data);
      setTab("forecast");
    } catch {
      setMsg({ type: "destructive", text: "Prediction request failed" });
    } finally {
      setPredicting(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg(null);
    try {
      const token = localStorage.getItem("wms_token");
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${base}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await res.json();
      if (!res.ok) {
        setMsg({ type: "destructive", text: data.detail || "Upload failed" });
        return;
      }
      setMsg({
        type: "success",
        text: `Uploaded ${data.rows_saved} rows successfully.`,
      });
      await fetchStatus();
    } catch {
      setMsg({ type: "destructive", text: "Upload request failed" });
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const token = localStorage.getItem("wms_token");
      const res = await fetch(`${base}/template`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ml_history_template_${productId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
  };

  const handleDeleteModel = async () => {
    if (!confirm("Delete the trained model for this product?")) return;
    setDeleting(true);
    try {
      const res = await authFetch(`${base}/model`, { method: "DELETE" });
      if (res.ok) {
        setMsg({ type: "success", text: "Model deleted." });
        setPrediction(null);
        await fetchStatus();
      }
    } catch {
      /* ignore */
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4 p-1">
        <Skeleton className="h-32 rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <AnimatePresence>
        {msg && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Alert variant={msg.type}>{msg.text}</Alert>
          </motion.div>
        )}
      </AnimatePresence>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">
            <BarChart3 size={14} className="mr-1.5" /> Overview
          </TabsTrigger>
          <TabsTrigger value="data">
            <FileSpreadsheet size={14} className="mr-1.5" /> Data
          </TabsTrigger>
          <TabsTrigger value="forecast">
            <TrendingDown size={14} className="mr-1.5" /> Forecast
          </TabsTrigger>
        </TabsList>

        {/* ── Overview Tab ─────────────────────────── */}
        <TabsContent value="overview">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            {/* Model Status */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Brain size={14} /> Model Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                {status?.has_model ? (
                  <div className="space-y-2">
                    <Badge variant="success" className="mb-2">
                      <CheckCircle2 size={12} className="mr-1" /> Ready
                    </Badge>
                    <div className="text-xs text-muted-foreground space-y-1">
                      <p>
                        Trained:{" "}
                        {status.trained_at
                          ? new Date(status.trained_at).toLocaleDateString()
                          : "—"}
                      </p>
                      <p>
                        Data range: {status.data_start_date} →{" "}
                        {status.data_end_date}
                      </p>
                      <p>Points: {status.total_data_points}</p>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    <Badge variant="secondary" className="mb-2">
                      No model
                    </Badge>
                    <p className="text-xs">
                      Train a model to enable demand forecasting.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Accuracy */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 size={14} /> Accuracy
                </CardTitle>
              </CardHeader>
              <CardContent>
                {status?.has_model ? (
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-muted-foreground">CV MAE</span>
                        <span className="font-medium">
                          {status.cv_mae?.toFixed(1)}
                        </span>
                      </div>
                      <Progress
                        value={Math.max(0, 100 - (status.cv_mae ?? 0))}
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-muted-foreground">CV MAPE</span>
                        <span className="font-medium">
                          {status.cv_mape?.toFixed(1)}%
                        </span>
                      </div>
                      <Progress
                        value={Math.max(0, 100 - (status.cv_mape ?? 0))}
                      />
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No model trained yet.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Training Data */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Calendar size={14} /> Training Data
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xs space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Auto (transactions)
                    </span>
                    <span className="font-medium">
                      {trainingData?.auto_data?.count ?? 0} days
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Uploaded (CSV)
                    </span>
                    <span className="font-medium">
                      {trainingData?.uploaded_data?.count ?? 0} days
                    </span>
                  </div>
                  <div className="flex justify-between border-t pt-1.5">
                    <span className="text-muted-foreground font-medium">
                      Merged total
                    </span>
                    <span className="font-semibold">
                      {trainingData?.merged?.count ?? 0} days
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3 mt-4">
            <Button onClick={handleTrain} disabled={training}>
              {training ? (
                <>
                  <RefreshCw size={14} className="animate-spin" /> Training...
                </>
              ) : (
                <>
                  <Brain size={14} /> Train Model
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={handlePredict}
              disabled={predicting || !status?.has_model}
            >
              {predicting ? (
                <>
                  <Clock size={14} className="animate-spin" /> Predicting...
                </>
              ) : (
                <>
                  <TrendingDown size={14} /> Predict Demand
                </>
              )}
            </Button>
            <div className="flex items-center gap-2 ml-auto">
              <Label
                htmlFor="days-input"
                className="text-xs text-muted-foreground"
              >
                Days:
              </Label>
              <Input
                id="days-input"
                type="number"
                min={7}
                max={180}
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-20 h-8"
              />
            </div>
          </div>

          {status?.has_model && (
            <div className="flex justify-end mt-2">
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={handleDeleteModel}
                disabled={deleting}
              >
                <Trash2 size={14} /> {deleting ? "Deleting..." : "Delete Model"}
              </Button>
            </div>
          )}
        </TabsContent>

        {/* ── Data Tab ──────────────────────────────── */}
        <TabsContent value="data">
          <div className="space-y-4 mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Upload Historical Data
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-xs text-muted-foreground">
                  Upload a CSV with historical inbound/outbound data for this
                  product. This improves model accuracy, especially for products
                  with limited transaction history in the system.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadTemplate}
                  >
                    <Download size={14} /> Download Template
                  </Button>
                  <div className="relative">
                    <Button
                      variant="default"
                      size="sm"
                      disabled={uploading}
                      asChild
                    >
                      <label className="cursor-pointer">
                        <Upload size={14} />{" "}
                        {uploading ? "Uploading..." : "Upload CSV"}
                        <input
                          type="file"
                          accept=".csv"
                          className="hidden"
                          onChange={handleUpload}
                        />
                      </label>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Data Summary */}
            {trainingData && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">
                    Data Summary
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <div className="p-3 rounded-lg bg-muted/50 space-y-1">
                      <p className="font-medium">Auto-aggregated</p>
                      <p className="text-muted-foreground">
                        {trainingData?.auto_data?.count} days
                      </p>
                      {trainingData?.auto_data?.date_range && (
                        <p className="text-muted-foreground">
                          {trainingData?.auto_data?.date_range.start} →{" "}
                          {trainingData?.auto_data?.date_range.end}
                        </p>
                      )}
                    </div>
                    <div className="p-3 rounded-lg bg-muted/50 space-y-1">
                      <p className="font-medium">Uploaded</p>
                      <p className="text-muted-foreground">
                        {trainingData?.uploaded_data?.count ?? 0} days
                      </p>
                      {trainingData?.uploaded_data?.date_range && (
                        <p className="text-muted-foreground">
                          {trainingData.uploaded_data.date_range.start} →{" "}
                          {trainingData.uploaded_data.date_range.end}
                        </p>
                      )}
                    </div>
                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/10 space-y-1">
                      <p className="font-semibold">Merged Total</p>
                      <p className="text-muted-foreground font-medium">
                        {trainingData?.merged?.count ?? 0} days
                      </p>
                      {trainingData?.merged?.date_range && (
                        <p className="text-muted-foreground">
                          {trainingData.merged.date_range.start} →{" "}
                          {trainingData.merged.date_range.end}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* ── Forecast Tab ──────────────────────────── */}
        <TabsContent value="forecast">
          {!prediction ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <TrendingDown size={40} className="mb-3 opacity-30" />
              <p className="text-sm">
                No prediction yet. Train a model and run prediction first.
              </p>
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4 mt-4"
            >
              {/* Key Stats */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card>
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground">
                      Current Stock
                    </p>
                    <p className="text-2xl font-bold">
                      {prediction.current_stock}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground">
                      Forecast Period
                    </p>
                    <p className="text-2xl font-bold">
                      {prediction.days_ahead} days
                    </p>
                  </CardContent>
                </Card>
                <Card
                  className={
                    prediction.stockout_date
                      ? "border-red-200"
                      : "border-emerald-200"
                  }
                >
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground">
                      Stockout Risk
                    </p>
                    {prediction.stockout_date ? (
                      <div className="flex items-center gap-2">
                        <AlertTriangle size={18} className="text-red-500" />
                        <span className="text-lg font-bold text-red-600">
                          {new Date(
                            prediction.stockout_date,
                          ).toLocaleDateString()}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={18} className="text-emerald-500" />
                        <span className="text-lg font-bold text-emerald-600">
                          Safe
                        </span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Stock Projection Chart */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    Projected Stock Level
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={prediction.predictions}
                        margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
                      >
                        <defs>
                          <linearGradient
                            id="stockGrad"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor="oklch(0.6 0.118 184.704)"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="95%"
                              stopColor="oklch(0.6 0.118 184.704)"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="oklch(0.9 0 0)"
                        />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11 }}
                          tickFormatter={(v: string) => v.slice(5)}
                        />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RTooltip
                          contentStyle={{
                            fontSize: 12,
                            borderRadius: 8,
                            border: "1px solid oklch(0.9 0 0)",
                          }}
                        />
                        <Area
                          type="monotone"
                          dataKey="projected_stock"
                          stroke="oklch(0.6 0.118 184.704)"
                          fill="url(#stockGrad)"
                          strokeWidth={2}
                          name="Stock"
                        />
                        {prediction.stockout_date && (
                          <ReferenceLine
                            x={prediction.stockout_date}
                            stroke="oklch(0.577 0.245 27.325)"
                            strokeDasharray="4 4"
                            label={{
                              value: "Stockout",
                              fontSize: 11,
                              fill: "oklch(0.577 0.245 27.325)",
                            }}
                          />
                        )}
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Demand Chart */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    Predicted Daily Demand
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={prediction.predictions}
                        margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="oklch(0.9 0 0)"
                        />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11 }}
                          tickFormatter={(v: string) => v.slice(5)}
                        />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RTooltip
                          contentStyle={{
                            fontSize: 12,
                            borderRadius: 8,
                            border: "1px solid oklch(0.9 0 0)",
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="predicted_outbound"
                          stroke="oklch(0.577 0.245 27.325)"
                          strokeWidth={2}
                          dot={false}
                          name="Outbound"
                        />
                        <Line
                          type="monotone"
                          dataKey="predicted_inbound"
                          stroke="oklch(0.6 0.118 184.704)"
                          strokeWidth={2}
                          dot={false}
                          name="Inbound"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Data Table */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    Daily Predictions
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-72 overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead className="text-right">
                            Pred. Outbound
                          </TableHead>
                          <TableHead className="text-right">
                            Pred. Inbound
                          </TableHead>
                          <TableHead className="text-right">
                            Proj. Stock
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {prediction.predictions.map((d) => (
                          <TableRow key={d.date}>
                            <TableCell className="text-xs">{d.date}</TableCell>
                            <TableCell className="text-right text-red-600 font-medium">
                              {d.predicted_outbound.toFixed(0)}
                            </TableCell>
                            <TableCell className="text-right text-emerald-600 font-medium">
                              {d.predicted_inbound.toFixed(0)}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {d.projected_stock.toFixed(0)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
