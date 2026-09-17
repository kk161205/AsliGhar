import type { SignalResult } from "../api/types";

interface SignalRowProps {
  label: string;
  signal: SignalResult;
}

// Deliberately no severity color-bucketing here (e.g. a green/amber/red dot).
// A signal's score can have more than two meaningful outcomes — address_validity
// has four (clean, resolved-with-no-category-data, category mismatch, unresolved)
// — and collapsing that into a flag/no-flag color would quietly throw away
// precision the backend's scoring was built to carry. The exact score and the
// full finding text are always shown instead; the proportional bar is a plain,
// single-tone visual aid, not a second, lossier encoding of the same signal.
export default function SignalRow({ label, signal }: SignalRowProps) {
  const ratio = signal.max > 0 ? signal.score / signal.max : 0;
  return (
    <div className="signal-row">
      <div className="signal-row__header">
        <span className="signal-row__label">{label}</span>
        <span className="signal-row__score mono">
          {signal.score} / {signal.max}
        </span>
      </div>
      <div
        className="signal-row__track"
        role="progressbar"
        aria-valuenow={signal.score}
        aria-valuemin={0}
        aria-valuemax={signal.max}
        aria-label={`${label}: ${signal.score} out of ${signal.max}`}
      >
        <div className="signal-row__fill" style={{ width: `${ratio * 100}%` }} />
      </div>
      <p className="signal-row__finding">{signal.finding}</p>
    </div>
  );
}
