import type { Insight } from "../api/types";
import TierBadge from "./TierBadge";

function linkLabel(url: string): string {
  return url.includes("google.com/maps") ? "Open in Google Maps" : "Open the page";
}

interface InsightsProps {
  insights: Insight[];
}

export default function Insights({ insights }: InsightsProps) {
  if (insights.length === 0) return null;
  return (
    <section className="results__insights">
      <h2>Also worth knowing</h2>
      <p className="results__legend">These don't change the score.</p>
      <ul className="insights">
        {insights.map((insight, index) => (
          <li key={`${insight.title}-${index}`}>
            <p className="insights__title">
              {insight.title} <TierBadge tier={insight.tier} />
            </p>
            <p className="insights__detail">{insight.detail}</p>
            {insight.url && (
              <a href={insight.url} target="_blank" rel="noreferrer noopener">
                {linkLabel(insight.url)}
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
