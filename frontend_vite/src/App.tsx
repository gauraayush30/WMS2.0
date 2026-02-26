import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./App.css";

import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import ProductsPage from "./pages/ProductsPage";
import InventoryPage from "./pages/InventoryPage";
import InventoryOverviewPage from "./pages/inventory/InventoryOverviewPage";
import InventoryHistoryPage from "./pages/inventory/InventoryHistoryPage";
import BusinessPage from "./pages/BusinessPage";
import UsersPage from "./pages/UsersPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import { AuthProvider, useAuth } from "./context/AuthContext";

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
          <Route path="/inventory" element={<InventoryPage />} />
          <Route
            path="/inventory/overview"
            element={<InventoryOverviewPage />}
          />
          <Route path="/inventory/history" element={<InventoryHistoryPage />} />
          <Route path="/business" element={<BusinessPage />} />
          <Route path="/users" element={<UsersPage />} />
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
