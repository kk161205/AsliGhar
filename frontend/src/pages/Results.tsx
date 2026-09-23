import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, getScan } from "../api/client";
import type { ScanResponse } from "../api/types";
import AiSummary from "../components/AiSummary";
import EvidenceTrail from "../components/EvidenceTrail";
import HowWeSearched from "../components/HowWeSearched";
import Insights from "../components/Insights";
import Nav from "../components/Nav";
import ResultsSkeleton from "../components/ResultsSkeleton";
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
        <h1>Scan result</h1>
        {scanId && <p className="mono results__id">{scanId}</p>}

        {state.status === "loading" && (
          <>
            <p className="sr-only" role="status">
              Loading scan result…
            </p>
            <ResultsSkeleton />
          </>
        )}
        {state.status === "error" && (
          <p role="alert" className="fetch-error">
            {state.message}
          </p>
        )}
        {state.status === "loaded" && (
          <>
            <RiskGauge score={state.scan.risk_score} band={state.scan.risk_band} />
            {state.scan.partial ? (
              <p role="note" className="results__partial">
                {state.scan.checks_run} of {state.scan.checks_total} checks ran, so this score may
                understate the risk.
              </p>
            ) : (
              <p className="results__coverage">All {state.scan.checks_total} checks ran.</p>
            )}

            {state.scan.override_reason && (
              <p role="note" className="results__override">
                The rent was flagged as unusual. Reason given: “{state.scan.override_reason}”. This is
                shown for context and doesn't change the score.
              </p>
            )}

            <section className="results__signals">
              <SignalRow label="Image reuse" signal={state.scan.signals.image_reuse} />
              <SignalRow label="Address plausibility" signal={state.scan.signals.address_validity} />
              <SignalRow label="Price sanity" signal={state.scan.signals.price_deviation} />
            </section>

            <section className="results__evidence">
              <h2>Evidence trail</h2>
              <p className="results__legend">
                <strong>Proven</strong> means an exact match we can link to. <strong>Indicator</strong>{" "}
                means worth checking, but not proof.
              </p>
              <EvidenceTrail evidence={state.scan.evidence} />
            </section>

            <Insights insights={state.scan.insights ?? []} />

            <AiSummary summary={state.scan.ai_summary} />

            {state.scan.search_trace && <HowWeSearched trace={state.scan.search_trace} />}
          </>
        )}
      </main>
    </>
  );
}
