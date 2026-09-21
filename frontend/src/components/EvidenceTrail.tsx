import type { ImageMatchEvidence } from "../api/types";
import TierBadge from "./TierBadge";

function formatRupees(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

function photoLabel(indexes: number[]): string {
  const numbers = indexes.map((index) => index + 1);
  if (numbers.length === 1) return `Photo ${numbers[0]}`;
  return `Photos ${numbers.slice(0, -1).join(", ")} and ${numbers[numbers.length - 1]}`;
}

// Scans stored before each item carried its own reasons only have the two
// prices and cities, so those are still described the old way.
function fallbackReason(item: ImageMatchEvidence): string {
  const listed = item.listed_price === null ? "an unknown price" : formatRupees(item.listed_price);
  return `Listed at ${listed}${item.listed_city ? ` in ${item.listed_city}` : ""}, versus your submitted ${formatRupees(
    item.submitted_price,
  )} in ${item.submitted_city}.`;
}

interface EvidenceTrailProps {
  evidence: ImageMatchEvidence[];
}

export default function EvidenceTrail({ evidence }: EvidenceTrailProps) {
  if (evidence.length === 0) {
    return (
      <p className="evidence-trail__empty">
        No page carrying your photos contradicts this listing.
      </p>
    );
  }

  return (
    <ul className="evidence-trail">
      {evidence.map((item) => {
        const photos = item.photo_indexes?.length ? item.photo_indexes : [item.photo_index];
        const reasons = item.reasons?.length ? item.reasons : [fallbackReason(item)];
        const matchedBy = item.matched_by ?? [];
        return (
          <li key={`${item.photo_index}-${item.source_url}`} className="evidence-trail__item">
            <details>
              <summary>
                {photoLabel(photos)} also {photos.length === 1 ? "appears" : "appear"} on{" "}
                <span className="mono">{item.source_domain}</span> <TierBadge tier={item.tier ?? "indicator"} />
              </summary>
              <div className="evidence-trail__detail">
                <p className="evidence-trail__title">{item.source_title}</p>
                <ul className="evidence-trail__reasons">
                  {reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
                {matchedBy.length > 1 && (
                  <p className="evidence-trail__matched">
                    Identified as the same home by: {matchedBy.join(", ")}.
                  </p>
                )}
                {item.source_snippet && (
                  <blockquote className="evidence-trail__quote">
                    <span className="evidence-trail__quote-label">The page says</span>
                    {item.source_snippet}
                  </blockquote>
                )}
                <a href={item.source_url} target="_blank" rel="noreferrer noopener">
                  Open the page
                </a>
              </div>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
