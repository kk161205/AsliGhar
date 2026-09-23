import { Trash2 } from "lucide-react";
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

export default function RecentScansList({
  scans,
  onDeleteRequest,
}: {
  scans: ScanSummary[];
  onDeleteRequest: (scan: ScanSummary) => void;
}) {
  return (
    <ul className="recent-scans">
      {scans.map((scan) => (
        <li key={scan.scan_id} className="recent-scans__card">
          <button
            type="button"
            className="recent-scans__delete"
            aria-label={`Delete scan of ${scan.address}`}
            onClick={() => onDeleteRequest(scan)}
          >
            <Trash2 aria-hidden="true" size={16} strokeWidth={1.75} />
          </button>
          <Link to={`/scan/${scan.scan_id}`} className="recent-scans__card-link">
            <span className={`recent-scans__band ${BAND_CLASS[scan.risk_band]}`}>
              {scan.risk_band}
              <span className="mono recent-scans__score">{scan.risk_score}/100</span>
            </span>
            <p className="recent-scans__address">{scan.address}</p>
            <p className="recent-scans__meta">
              {scan.city} · {formatDate(scan.created_at)}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
