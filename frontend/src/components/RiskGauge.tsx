import type { RiskBand } from "../api/types";

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
          className={`risk-gauge__fill risk-gauge__fill--${band.toLowerCase()}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}
