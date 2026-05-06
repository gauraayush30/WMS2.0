import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import ProductsPage from "./pages/ProductsPage";
import CreateProduct from "./pages/products/CreateProduct";
import ViewProduct from "./pages/products/ViewProduct";
import EditProduct from "./pages/products/EditProduct";
import InventoryPage from "./pages/InventoryPage";
import InventoryOverviewPage from "./pages/inventory/InventoryOverviewPage";
import InventoryHistoryPage from "./pages/inventory/InventoryHistoryPage";
import LocationUtilizationPage from "./pages/inventory/LocationUtilizationPage";
import BusinessPage from "./pages/BusinessPage";
import BusinessDetailsPage from "./pages/business/BusinessDetailsPage";
import InvitesPage from "./pages/business/InvitesPage";
import DeliveryLocationsPage from "./pages/business/DeliveryLocationsPage";
import CustomersPage from "./pages/customers/CustomersPage";
import WarehousesPage from "./pages/warehouses/WarehousesPage";
import InboundsPage from "./pages/inbounds/InboundsPage";
import NewInboundPage from "./pages/inbounds/NewInboundPage";
import ViewInboundPage from "./pages/inbounds/ViewInboundPage";
import OutboundsPage from "./pages/outbounds/OutboundsPage";
import NewOutboundPage from "./pages/outbounds/NewOutboundPage";
import ViewOutboundPage from "./pages/outbounds/ViewOutboundPage";
import UsersPage from "./pages/UsersPage";
import ReportsPage from "./pages/ReportsPage";
import FastSlowMovingPage from "./pages/reports/FastSlowMovingPage";
import InboundOutboundPage from "./pages/reports/InboundOutboundPage";
import FifoFefoPage from "./pages/reports/FifoFefoPage";
import CompleteAnalysisPage from "./pages/reports/CompleteAnalysisPage";
import BehaviorAnalysisPage from "./pages/reports/BehaviorAnalysisPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import { AuthProvider, useAuth } from "./context/AuthContext";

function WarehouseOnly({ children }: { children: React.ReactNode }) {
  const { isWarehouse } = useAuth();
  return isWarehouse ? <>{children}</> : <Navigate to="/" replace />;
}

function WarehouseAdminOnly({ children }: { children: React.ReactNode }) {
  const { isWarehouseAdmin } = useAuth();
  return isWarehouseAdmin ? <>{children}</> : <Navigate to="/" replace />;
}

function AppInner() {
  const { user, authLoading } = useAuth();
  const [authView, setAuthView] = useState<"login" | "register">("login");

  if (authLoading) return null;

  if (!user) {
    return authView === "login" ? (
      <LoginPage onSwitchToRegister={() => setAuthView("register")} />
    ) : (
      <RegisterPage onSwitchToLogin={() => setAuthView("login")} />
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/create" element={<CreateProduct />} />
          <Route path="/products/:id" element={<ViewProduct />} />
          <Route path="/products/:id/edit" element={<EditProduct />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route
            path="/inventory/overview"
            element={<InventoryOverviewPage />}
          />
          <Route path="/inventory/history" element={<InventoryHistoryPage />} />
          <Route path="/inventory/location-utilization" element={<LocationUtilizationPage />} />
          <Route path="/inbounds" element={<InboundsPage />} />
          <Route path="/inbounds/new" element={<NewInboundPage />} />
          <Route path="/inbounds/:id" element={<ViewInboundPage />} />
          <Route path="/outbounds" element={<OutboundsPage />} />
          <Route path="/outbounds/new" element={<NewOutboundPage />} />
          <Route path="/outbounds/:id" element={<ViewOutboundPage />} />
          <Route path="/business" element={<BusinessPage />} />
          <Route path="/business/details" element={<BusinessDetailsPage />} />
          <Route path="/business/invites" element={<InvitesPage />} />
          <Route
            path="/business/delivery-locations"
            element={<DeliveryLocationsPage />}
          />
          <Route
            path="/customers"
            element={
              <WarehouseOnly>
                <CustomersPage />
              </WarehouseOnly>
            }
          />
          <Route
            path="/warehouses"
            element={
              <WarehouseOnly>
                <WarehousesPage />
              </WarehouseOnly>
            }
          />
          <Route
            path="/users"
            element={
              <WarehouseAdminOnly>
                <UsersPage />
              </WarehouseAdminOnly>
            }
          />
          <Route path="/reports" element={<ReportsPage />} />
          <Route
            path="/reports/fast-slow-moving"
            element={<FastSlowMovingPage />}
          />
          <Route
            path="/reports/inbound-outbound"
            element={<InboundOutboundPage />}
          />
          <Route path="/reports/fifo-fefo" element={<FifoFefoPage />} />
          <Route
            path="/reports/complete-analysis"
            element={<CompleteAnalysisPage />}
          />
          <Route
            path="/reports/behavior"
            element={<BehaviorAnalysisPage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

export default App;
