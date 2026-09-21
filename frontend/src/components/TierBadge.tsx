import type { Tier } from "../api/types";

const LABELS: Record<Tier, { text: string; help: string }> = {
  proven: { text: "Proven", help: "An exact match we can link to." },
  indicator: { text: "Indicator", help: "Worth checking, but not proof." },
};

interface TierBadgeProps {
  tier: Tier;
}

// Single-tone on purpose: the tier says how solid the evidence is, not how
// alarming it is, so it doesn't borrow a severity colour.
export default function TierBadge({ tier }: TierBadgeProps) {
  const { text, help } = LABELS[tier];
  return (
    <span className={`tier tier--${tier}`} title={help}>
      {text}
    </span>
  );
}
