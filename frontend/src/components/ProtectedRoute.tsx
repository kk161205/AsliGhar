import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === "loading") {
    return <>{fallback ?? <p className="auth-loading">Loading…</p>}</>;
  }

  if (state.status === "anonymous") {
    const next = encodeURIComponent(location.pathname);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  return <>{children}</>;
}
