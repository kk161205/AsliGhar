import type { RiskBand } from "../api/types";

const BAND_COLOR: Record<RiskBand, string> = {
  Low: "var(--moss-600)",
  Moderate: "var(--amber-600)",
  High: "var(--rust-700)",
  Severe: "var(--rust-700)",
};

interface RiskGaugeProps {
  score: number;
  band: RiskBand;
}

export default function RiskGauge({ score, band }: RiskGaugeProps) {
  return (
    <div className="risk-gauge">
      <div className="risk-gauge__header">
        {/* Band is always spelled out in text, never conveyed by color alone. */}
        <span className="risk-gauge__band">{band} risk</span>
        <span className="risk-gauge__score mono">{score} / 100</span>
      </div>
      <div
        className="risk-gauge__track"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Risk score ${score} out of 100, ${band} risk`}
      >
        <div
          className="risk-gauge__fill"
          style={{ width: `${score}%`, backgroundColor: BAND_COLOR[band] }}
        />
      </div>
    </div>
  );
}
