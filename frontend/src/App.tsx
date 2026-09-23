import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import DashboardSkeleton from "./components/DashboardSkeleton";
import Nav from "./components/Nav";
import ProtectedRoute from "./components/ProtectedRoute";
import ScanPageSkeleton from "./components/ScanPageSkeleton";
import Dashboard from "./pages/Dashboard";
import HowItWorks from "./pages/HowItWorks";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Results from "./pages/Results";
import Scan from "./pages/Scan";
import Signup from "./pages/Signup";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute
                fallback={
                  <>
                    <Nav />
                    <main className="page page--dashboard">
                      <p className="sr-only" role="status">
                        Loading…
                      </p>
                      <DashboardSkeleton />
                    </main>
                  </>
                }
              >
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scan"
            element={
              <ProtectedRoute fallback={<ScanPageSkeleton />}>
                <Scan />
              </ProtectedRoute>
            }
          />
          <Route path="/scan/:scanId" element={<Results />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
