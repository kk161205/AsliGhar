import type { SearchTrace } from "../api/types";

const CHECK_LABELS = { address: "Address check", price: "Price check" } as const;

interface HowWeSearchedProps {
  trace: SearchTrace;
}

export default function HowWeSearched({ trace }: HowWeSearchedProps) {
  const { understood, queries, reviewer_used } = trace;
  const photos = trace.photos ?? [];
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
      {photos.length > 0 && (
        <ul className="how-we-searched__photos">
          {photos.map((photo) => (
            <li key={photo.index}>
              Photo {photo.index + 1}: {photo.pages_found} page{photo.pages_found === 1 ? "" : "s"} carry it,{" "}
              {photo.listing_pages} of them {photo.listing_pages === 1 ? "is a property listing" : "are property listings"}.
            </li>
          ))}
        </ul>
      )}
      <ul className="how-we-searched__queries">
        {queries.map((item, index) => (
          <li key={`${item.check}-${index}`}>
            <span>{CHECK_LABELS[item.check]}</span>
            <code>{item.query}</code>
          </li>
        ))}
      </ul>
    </details>
  );
}
