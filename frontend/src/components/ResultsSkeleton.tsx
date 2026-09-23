export default function ResultsSkeleton() {
  return (
    <>
      <div className="risk-gauge" aria-hidden="true">
        <div className="risk-gauge__header">
          <div className="skeleton skeleton--gauge-label" />
          <div className="skeleton skeleton--gauge-score" />
        </div>
        <div className="skeleton skeleton--gauge-track" />
      </div>

      <section className="results__signals" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div className="signal-row" key={i}>
            <div className="signal-row__header">
              <div className="skeleton skeleton--signal-label" />
              <div className="skeleton skeleton--signal-score" />
            </div>
            <div className="skeleton skeleton--signal-track" />
            <div className="skeleton skeleton--signal-finding" />
          </div>
        ))}
      </section>

      <section className="results__evidence">
        <h2>Evidence trail</h2>
        <p className="results__legend">
          <strong>Proven</strong> means an exact match we can link to. <strong>Indicator</strong>{" "}
          means worth checking, but not proof.
        </p>
        <div className="evidence-trail" aria-hidden="true">
          {[0, 1].map((i) => (
            <div className="skeleton skeleton--evidence-item" key={i} />
          ))}
        </div>
      </section>
    </>
  );
}
