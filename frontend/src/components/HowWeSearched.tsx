import type { SearchTrace } from "../api/types";

const CHECK_LABELS = { address: "Address check", price: "Price check" } as const;

interface HowWeSearchedProps {
  trace: SearchTrace;
}

export default function HowWeSearched({ trace }: HowWeSearchedProps) {
  const { understood, queries, reviewer_used } = trace;
  const facts = [
    ["Area", understood.locality],
    ["Landmark", understood.landmark],
    ["Pincode", understood.pincode],
    ["BHK", understood.bhk],
  ].filter((fact): fact is [string, string] => fact[1] !== null);

  return (
    <details className="how-we-searched">
      <summary>How we searched</summary>
      <p className="how-we-searched__lead">
        {reviewer_used
          ? "We read your address to find the area to compare prices against."
          : "We couldn't read the address in detail, so prices were compared across the whole city."}
      </p>
      {facts.length > 0 && (
        <dl className="how-we-searched__facts">
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <ul className="how-we-searched__queries">
        {queries.map((item) => (
          <li key={item.check}>
            <span>{CHECK_LABELS[item.check]}</span>
            <code>{item.query}</code>
          </li>
        ))}
      </ul>
    </details>
  );
}
