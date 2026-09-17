import type { ImageMatchEvidence } from "../api/types";

function formatRupees(value: number | null): string {
  return value === null ? "unknown" : `₹${value.toLocaleString("en-IN")}`;
}

interface EvidenceTrailProps {
  evidence: ImageMatchEvidence[];
}

export default function EvidenceTrail({ evidence }: EvidenceTrailProps) {
  if (evidence.length === 0) {
    return (
      <p className="evidence-trail__empty">
        No reused photos found on other listings for this scan.
      </p>
    );
  }

  return (
    <ul className="evidence-trail">
      {evidence.map((item) => (
        <li key={`${item.photo_index}-${item.source_url}`} className="evidence-trail__item">
          <details>
            <summary>
              Photo {item.photo_index + 1} also appears on{" "}
              <span className="mono">{item.source_domain}</span>
            </summary>
            <div className="evidence-trail__detail">
              <p>{item.source_title}</p>
              <p>
                Listed at {formatRupees(item.listed_price)}
                {item.listed_city ? ` in ${item.listed_city}` : ""}, versus your submitted{" "}
                {formatRupees(item.submitted_price)} in {item.submitted_city}.
              </p>
              <a href={item.source_url} target="_blank" rel="noreferrer noopener">
                View source listing
              </a>
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}
