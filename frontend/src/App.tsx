import { Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Ask from "./pages/Ask";
import Finance from "./pages/Finance";
import Growth from "./pages/Growth";
import HomePage from "./pages/Home";
import Insights from "./pages/Insights";
import Inventory from "./pages/Inventory";
import Khata from "./pages/Khata";
import Login from "./pages/Login";
import Pay from "./pages/Pay";
import Phone from "./pages/Phone";
import Roadmap from "./pages/Roadmap";
import Trust from "./pages/Trust";

export default function App() {
  const { merchant, loading } = useAuth();
  return (
    <Routes>
      <Route path="/pay/:id" element={<Pay />} />
      <Route
        path="*"
        element={
          loading ? <Spinner /> : !merchant ? <Login /> : (
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route path="ask" element={<Ask />} />
                <Route path="insights" element={<Insights />} />
                <Route path="khata" element={<Khata />} />
                <Route path="inventory" element={<Inventory />} />
                <Route path="growth" element={<Growth />} />
                <Route path="finance" element={<Finance />} />
                <Route path="trust" element={<Trust />} />
                <Route path="phone" element={<Phone />} />
                <Route path="roadmap" element={<Roadmap />} />
              </Route>
            </Routes>
          )
        }
      />
    </Routes>
  );
}
