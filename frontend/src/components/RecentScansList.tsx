import { Link } from "react-router-dom";
import type { RiskBand, ScanSummary } from "../api/types";

const BAND_CLASS: Record<RiskBand, string> = {
  Low: "is-low",
  Moderate: "is-moderate",
  High: "is-high",
  Severe: "is-severe",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function RecentScansList({ scans }: { scans: ScanSummary[] }) {
  return (
    <ul className="recent-scans">
      {scans.map((scan) => (
        <li key={scan.scan_id}>
          <Link to={`/scan/${scan.scan_id}`} className="recent-scans__row">
            <div>
              <p className="recent-scans__address">{scan.address}</p>
              <p className="recent-scans__meta">
                {scan.city} · {formatDate(scan.created_at)}
              </p>
            </div>
            <span className={`recent-scans__band ${BAND_CLASS[scan.risk_band]}`}>
              {scan.risk_band}
              <span className="mono recent-scans__score">{scan.risk_score}/100</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
