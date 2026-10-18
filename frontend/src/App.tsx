import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import CreateBusiness from "./business/CreateBusiness";
import { BusinessProvider, useBusiness } from "./context/BusinessContext";
import DailyRecord from "./daily-record/DailyRecord";
import DataValidation from "./data-validation/DataValidation";
import ManualEntry from "./data-validation/ManualEntry";
import UploadDocument from "./data-validation/UploadDocument";
import Inventory from "./inventory/Inventory";
import InventoryDetail from "./inventory/InventoryDetail";
import Landing from "./landing/Landing";
import Login from "./login/Login";
import Overview from "./overview/Overview";
import PrepPlanner from "./prep-planner/PrepPlanner";
import Promotions from "./promotions/Promotions";
import Sales from "./sales/Sales";
import { getToken } from "./services/apiClient";

function ProtectedRoute() {
  const { businesses, loading } = useBusiness();

  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-600">Loading…</p>
      </div>
    );
  }
  if (businesses.length === 0) {
    return <Navigate to="/businesses/new" replace />;
  }
  return <Outlet />;
}

function App() {
  return (
    <BrowserRouter>
      <BusinessProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/businesses/new" element={<CreateBusiness />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/overview" element={<Overview />} />
            <Route path="/daily-record" element={<DailyRecord />} />
            <Route path="/sales" element={<Sales />} />
            <Route path="/prep-planner" element={<PrepPlanner />} />
            <Route path="/promotions" element={<Promotions />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/inventory/:id" element={<InventoryDetail />} />
            <Route path="/data-validation" element={<DataValidation />} />
            <Route path="/data-validation/upload" element={<UploadDocument />} />
            <Route path="/data-validation/manual" element={<ManualEntry />} />
          </Route>
        </Routes>
      </BusinessProvider>
    </BrowserRouter>
  );
}

export default App;
