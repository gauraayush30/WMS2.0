import { useEffect, useState, useCallback } from "react";
import "./App.css";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";

import Header from "./components/Header.tsx";
import Controls from "./components/Controls.tsx";
import ForecastTab from "./components/ForecastTab.tsx";
import HistoryTab from "./components/HistoryTab.tsx";
import TransactionTab from "./components/TransactionTab.tsx";
import ReplenishmentTab from "./components/ReplenishmentTab.tsx";
import ProductMetricsTab from "./components/ProductMetricsTab.tsx";
import AlertsTab from "./components/AlertsTab.tsx";
import LoginPage from "./pages/LoginPage.tsx";
import RegisterPage from "./pages/RegisterPage.tsx";
import { AuthProvider, useAuth } from "./context/AuthContext";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler
);

const API = "http://127.0.0.1:8000";

function AppInner() {
  const { user, authLoading } = useAuth();
  const [authView, setAuthView] = useState("login"); // "login" | "register"

  // Show blank while restoring session
  if (authLoading) return null;

  // Show auth pages if not logged in
  if (!user) {
    return authView === "login" ? (
      <LoginPage onSwitchToRegister={() => setAuthView("register")} />
    ) : (
      <RegisterPage onSwitchToLogin={() => setAuthView("login")} />
    );
  }

  return <AppMain />;
}

function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

function AppMain() {
  const [skus, setSkus] = useState([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [activeTab, setActiveTab] = useState("forecast");
  const [historyDays, setHistoryDays] = useState(7);
  const [forecastDays, setForecastDays] = useState(7);
  const [data, setData] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);

  // Transaction form state
  const [transactionForm, setTransactionForm] = useState({
    sku_id: "",
    sales_qty: 0,
    purchase_qty: 0,
    transaction_date: new Date().toISOString().split("T")[0],
  });
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionMessage, setTransactionMessage] = useState("");
  const [transactionError, setTransactionError] = useState("");

  // Replenishment state
  const [repSettings, setRepSettings] = useState(null);
  const [repRecommendation, setRepRecommendation] = useState(null);
  const [repLoading, setRepLoading] = useState(false);
  const [repError, setRepError] = useState("");
  const [repMessage, setRepMessage] = useState("");
  const [repForm, setRepForm] = useState({
    lead_time_days: 7,
    min_order_qty: 10,
    reorder_point: 50,
    safety_stock: 25,
    target_stock_level: 150,
  });

  // Fetch replenishment settings and recommendation
  const fetchReplenishment = useCallback(async () => {
    if (!selectedSku) return;
    setRepLoading(true);
    setRepError("");
    setRepMessage("");

    try {
      const [settingsRes, recRes] = await Promise.all([
        fetch(`${API}/replenishment-settings/${selectedSku}`),
        fetch(`${API}/replenishment-recommendation?sku_id=${selectedSku}&days=14`),
      ]);

      if (!settingsRes.ok) {
        const err = await settingsRes.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to load replenishment settings");
      }
      if (!recRes.ok) {
        const err = await recRes.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to load replenishment recommendation");
      }

      const settings = await settingsRes.json();
      const recommendation = await recRes.json();

      setRepSettings(settings);
      setRepRecommendation(recommendation);

      setRepForm((prev) => ({
        ...prev,
        lead_time_days: settings.lead_time_days || prev.lead_time_days,
        min_order_qty: settings.min_order_qty || prev.min_order_qty,
        reorder_point: settings.reorder_point || prev.reorder_point,
        safety_stock: settings.safety_stock || prev.safety_stock,
        target_stock_level: settings.target_stock_level || prev.target_stock_level,
      }));
    } catch (err) {
      setRepError(err.message || "Error fetching replenishment data");
    } finally {
      setRepLoading(false);
    }
  }, [selectedSku]);

  // Submit replenishment settings update
  const handleRepSettingsSubmit = async (e) => {
    e.preventDefault();
    setRepError("");
    setRepMessage("");

    try {
      const response = await fetch(`${API}/replenishment-settings/${selectedSku}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(repForm),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save settings");
      }

      const result = await response.json();
      setRepMessage(result.message || "Settings saved");
      fetchReplenishment();
    } catch (err) {
      setRepError(err.message);
    }
  };

  // Fetch SKU list
  const fetchSkus = useCallback(() => {
    fetch(`${API}/skus`)
      .then((r) => r.json())
      .then((res) => {
        setSkus(res.skus || []);
        if (res.skus?.length && !selectedSku) {
          setSelectedSku(res.skus[0].sku_id);
          setTransactionForm((prev) => ({
            ...prev,
            sku_id: res.skus[0].sku_id,
          }));
        }
      })
      .catch(console.error);
  }, [selectedSku]);

  useEffect(() => {
    fetchSkus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch history or forecast whenever controls change
  const fetchData = useCallback(() => {
    if (!selectedSku) return;
    setLoading(true);

    const url =
      activeTab === "forecast"
        ? `${API}/forecast?sku_id=${selectedSku}&days=${forecastDays}`
        : `${API}/history?sku_id=${selectedSku}&days=${historyDays}`;

    fetch(url)
      .then((r) => r.json())
      .then((res) => {
        if (activeTab === "forecast") {
          setData(res.forecast || []);
          setMeta({
            current_stock: res.current_stock,
            total_forecast_demand: res.total_forecast_demand,
            stock_status: res.stock_status,
          });
        } else {
          setData(res.history || []);
          setMeta({
            current_stock: res.current_stock,
          });
        }
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [selectedSku, activeTab, historyDays, forecastDays]);

  useEffect(() => {
    if (activeTab === "replenishment") {
      fetchReplenishment();
    } else if (activeTab !== "transaction") {
      fetchData();
    }
  }, [fetchData, activeTab, fetchReplenishment]);

  // Handle SKU change
  const handleSkuChange = (skuId) => {
    setSelectedSku(skuId);
    setTransactionForm((prev) => ({ ...prev, sku_id: skuId }));
  };

  // Handle transaction form submission
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    setTransactionError("");
    setTransactionMessage("");

    if (!transactionForm.sku_id) {
      setTransactionError("Please select a SKU");
      return;
    }

    if (
      transactionForm.sales_qty === 0 &&
      transactionForm.purchase_qty === 0
    ) {
      setTransactionError("Enter either sales qty or purchase qty");
      return;
    }

    setTransactionLoading(true);

    try {
      const response = await fetch(`${API}/record-transaction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(transactionForm),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to record transaction");
      }

      const result = await response.json();

      setTransactionMessage(
        `\u2713 Transaction recorded! Stock updated: ${result.previous_stock} \u2192 ${result.new_stock_level}`
      );

      setTransactionForm({
        ...transactionForm,
        sales_qty: 0,
        purchase_qty: 0,
        transaction_date: new Date().toISOString().split("T")[0],
      });

      fetchSkus();
      setTimeout(() => {
        setActiveTab("history");
      }, 1500);
    } catch (error) {
      setTransactionError(error.message);
    } finally {
      setTransactionLoading(false);
    }
  };

  const skuInfo = skus.find((s) => s.sku_id === selectedSku);

  // ── render ─────────────────────────────────────────────────
  return (
    <div className="app">
      <Header />

      <Controls
        skus={skus}
        selectedSku={selectedSku}
        onSkuChange={handleSkuChange}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        historyDays={historyDays}
        forecastDays={forecastDays}
        onHistoryDaysChange={setHistoryDays}
        onForecastDaysChange={setForecastDays}
        onRefresh={fetchData}
        loading={loading}
      />

      {activeTab === "forecast" && (
        <ForecastTab data={data} meta={meta} loading={loading} />
      )}

      {activeTab === "history" && (
        <HistoryTab
          data={data}
          meta={meta}
          skuInfo={skuInfo}
          loading={loading}
        />
      )}

      {activeTab === "transaction" && (
        <TransactionTab
          transactionForm={transactionForm}
          onFormChange={setTransactionForm}
          onSubmit={handleTransactionSubmit}
          transactionLoading={transactionLoading}
          transactionMessage={transactionMessage}
          transactionError={transactionError}
          skuInfo={skuInfo}
        />
      )}

      {activeTab === "replenishment" && (
        <ReplenishmentTab
          selectedSku={selectedSku}
          repSettings={repSettings}
          repRecommendation={repRecommendation}
          repLoading={repLoading}
          repError={repError}
          repMessage={repMessage}
          repForm={repForm}
          onRepFormChange={setRepForm}
          onRepSettingsSubmit={handleRepSettingsSubmit}
          onRefresh={fetchReplenishment}
        />
      )}

      {activeTab === "metrics" && <ProductMetricsTab />}

      {activeTab === "alerts" && <AlertsTab />}
    </div>
  );
}

export default App;
