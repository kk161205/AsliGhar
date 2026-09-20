import { useEffect, useState } from "react";

interface ChecklistStep {
  id: string;
  label: string;
  // Expected completion time, in ms after submit. These are a paced UX
  // approximation, not literal backend telemetry — the API returns one
  // combined JSON response, it doesn't stream per-check progress. The order
  // and timing are set from real measured latency: the address is read in
  // ~0.5-2s, then address/price resolve ~4s later, and google_lens (the photo
  // check) is the long pole at ~9-12s. If the
  // real response is slower than this schedule, the last step keeps
  // animating rather than falsely completing.
  etaMs: number;
}

function buildSteps(photoCount: number): ChecklistStep[] {
  return [
    { id: "read", label: "Reading your address", etaMs: 1500 },
    { id: "address", label: "Verifying address", etaMs: 5500 },
    { id: "price", label: "Comparing local prices", etaMs: 6000 },
    {
      id: "photos",
      label: `Checking ${photoCount} photo${photoCount === 1 ? "" : "s"} for reuse`,
      etaMs: 11000,
    },
  ];
}

interface ScanningStateProps {
  photoCount: number;
  complete: boolean;
}

export default function ScanningState({ photoCount, complete }: ScanningStateProps) {
  const [elapsedMs, setElapsedMs] = useState(0);
  const steps = buildSteps(photoCount);

  useEffect(() => {
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 200);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <div className="scanning-state" role="status" aria-live="polite">
      <p className="scanning-state__heading">Checking this listing…</p>
      <ul className="scanning-state__list">
        {steps.map((step) => {
          const done = complete || elapsedMs >= step.etaMs;
          return (
            <li
              key={step.id}
              className={done ? "is-done" : "is-pending"}
              aria-label={`${step.label}: ${done ? "done" : "in progress"}`}
            >
              <span aria-hidden="true">{done ? "✓" : "•"}</span> {step.label}
              {done ? "" : "…"}
            </li>
          );
        })}
      </ul>
      <p className="scanning-state__note">
        Real checks against live listing and photo data — typically 10–15
        seconds, mostly spent cross-referencing photos.
      </p>
    </div>
  );
}
