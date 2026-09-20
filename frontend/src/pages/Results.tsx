import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, getScan } from "../api/client";
import type { ScanResponse } from "../api/types";
import AiSummary from "../components/AiSummary";
import EvidenceTrail from "../components/EvidenceTrail";
import Nav from "../components/Nav";
import RiskGauge from "../components/RiskGauge";
import SignalRow from "../components/SignalRow";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; scan: ScanResponse }
  | { status: "error"; message: string };

export default function Results() {
  const { scanId } = useParams<{ scanId: string }>();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    setState({ status: "loading" });
    getScan(scanId)
      .then((scan) => {
        if (!cancelled) setState({ status: "loaded", scan });
      })
      .catch((err) => {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : "Couldn't load this scan.";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  return (
    <>
      <Nav />
      <main className="page page--results">
        {state.status === "loading" && <p>Loading scan result…</p>}
        {state.status === "error" && (
          <p role="alert" className="results__error">
            {state.message}
          </p>
        )}
        {state.status === "loaded" && (
          <>
            <h1>Scan result</h1>
            <p className="mono results__id">{state.scan.scan_id}</p>
            <RiskGauge score={state.scan.risk_score} band={state.scan.risk_band} />
            {state.scan.partial && (
              <p role="note" className="results__partial">
                Some checks couldn't run, so this score may understate the risk.
              </p>
            )}

            <section className="results__signals">
              <SignalRow label="Image reuse" signal={state.scan.signals.image_reuse} />
              <SignalRow label="Address plausibility" signal={state.scan.signals.address_validity} />
              <SignalRow label="Price sanity" signal={state.scan.signals.price_deviation} />
            </section>

            <section className="results__evidence">
              <h2>Evidence trail</h2>
              <EvidenceTrail evidence={state.scan.evidence} />
            </section>

            <AiSummary summary={state.scan.ai_summary} />
          </>
        )}
      </main>
    </>
  );
}
