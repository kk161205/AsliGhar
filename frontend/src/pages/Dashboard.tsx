import { Gauge, ScanSearch, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listScans } from "../api/client";
import type { ScanSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import Nav from "../components/Nav";
import RecentScansList from "../components/RecentScansList";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; scans: ScanSummary[] }
  | { status: "error"; message: string };

function flaggedCount(scans: ScanSummary[]): number {
  return scans.filter((scan) => scan.risk_band === "High" || scan.risk_band === "Severe").length;
}

function averageScore(scans: ScanSummary[]): number {
  if (scans.length === 0) return 0;
  return Math.round(scans.reduce((sum, scan) => sum + scan.risk_score, 0) / scans.length);
}

function firstName(fullName: string | null): string {
  if (!fullName) return "there";
  return fullName.trim().split(/\s+/)[0];
}

export default function Dashboard() {
  const { state: authState } = useAuth();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    listScans()
      .then((scans) => {
        if (!cancelled) setState({ status: "loaded", scans });
      })
      .catch((err) => {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : "Couldn't load your scans.";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const user = authState.status === "authenticated" ? authState.user : null;
  const subLine = user ? [user.email, user.city].filter(Boolean).join(" · ") : "";

  return (
    <>
      <Nav />
      <main className="page page--dashboard">
        <div className="dashboard-header">
          <h1>Welcome back, {firstName(user?.full_name ?? null)}</h1>
          <p className="dashboard-header__sub">{subLine}</p>
        </div>

        {state.status === "loading" && <p className="recent-scans__status">Loading your scans…</p>}
        {state.status === "error" && (
          <p className="recent-scans__status" role="alert">
            {state.message}
          </p>
        )}

        {state.status === "loaded" && (
          <>
            <div className="stat-row">
              <div className="stat-card">
                <ScanSearch aria-hidden="true" size={20} strokeWidth={1.75} />
                <p className="stat-card__value mono">{state.scans.length}</p>
                <p className="stat-card__label">Recent scans</p>
              </div>
              <div className={`stat-card${flaggedCount(state.scans) > 0 ? " stat-card--flagged" : ""}`}>
                <TriangleAlert aria-hidden="true" size={20} strokeWidth={1.75} />
                <p className="stat-card__value mono">{flaggedCount(state.scans)}</p>
                <p className="stat-card__label">High / Severe flagged</p>
              </div>
              <div className="stat-card">
                <Gauge aria-hidden="true" size={20} strokeWidth={1.75} />
                <p className="stat-card__value mono">
                  {state.scans.length > 0 ? averageScore(state.scans) : "—"}
                </p>
                <p className="stat-card__label">Average risk score</p>
              </div>
            </div>

            <section className="dashboard-scans">
              <h2>Recent scans</h2>
              {state.scans.length === 0 ? (
                <p className="recent-scans__status">
                  No scans yet. <Link to="/scan">Check your first listing</Link> to see it here.
                </p>
              ) : (
                <RecentScansList scans={state.scans} />
              )}
            </section>
          </>
        )}
      </main>
    </>
  );
}
