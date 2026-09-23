import Nav from "./Nav";

export default function ScanPageSkeleton() {
  return (
    <>
      <Nav />
      <main className="page page--scan">
        <div className="scan-layout">
          <div className="scan-layout__main">
            <h1>Check a listing</h1>
            <p className="sr-only" role="status">
              Loading…
            </p>
            <div className="upload-form" aria-hidden="true">
              <div className="skeleton skeleton--dropzone" />
              <div className="skeleton skeleton--form-field" />
              <div className="upload-form__row">
                <div className="skeleton skeleton--form-field" />
                <div className="skeleton skeleton--form-field" />
                <div className="skeleton skeleton--form-field" />
              </div>
            </div>
          </div>

          <aside className="scan-layout__aside" aria-label="What we check">
            <h2>What we check</h2>
            <ul className="check-list" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <li key={i}>
                  <div className="skeleton skeleton--check-icon" />
                  <div className="check-list__skeleton-lines">
                    <div className="skeleton skeleton--check-title" />
                    <div className="skeleton skeleton--check-body" />
                  </div>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </main>
    </>
  );
}
