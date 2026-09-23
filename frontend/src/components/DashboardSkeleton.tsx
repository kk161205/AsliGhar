import { Link } from "react-router-dom";

export default function DashboardSkeleton() {
  return (
    <>
      <div className="stat-row" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div className="stat-card" key={i}>
            <div className="skeleton skeleton--icon" />
            <div className="skeleton skeleton--value" />
            <div className="skeleton skeleton--label" />
          </div>
        ))}
      </div>

      <section className="dashboard-scans">
        <div className="dashboard-scans__header">
          <h2>Recent scans</h2>
          <Link to="/scan" className="button-secondary">
            Check a listing
          </Link>
        </div>
        <ul className="recent-scans" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className="recent-scans__card">
              <div className="recent-scans__card-link recent-scans__card-link--static">
                <div className="skeleton skeleton--band" />
                <div className="skeleton skeleton--address" />
                <div className="skeleton skeleton--meta" />
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
