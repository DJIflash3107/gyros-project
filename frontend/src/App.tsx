import { BrowserRouter, Route, Routes } from "react-router-dom";
import DailyRecord from "./daily-record/DailyRecord";
import Inventory from "./inventory/Inventory";
import InventoryDetail from "./inventory/InventoryDetail";
import Landing from "./landing/Landing";
import Login from "./login/Login";
import Overview from "./overview/Overview";
import PrepPlanner from "./prep-planner/PrepPlanner";
import Sales from "./sales/Sales";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/daily-record" element={<DailyRecord />} />
        <Route path="/sales" element={<Sales />} />
        <Route path="/prep-planner" element={<PrepPlanner />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/inventory/:id" element={<InventoryDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
