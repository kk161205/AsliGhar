import Nav from "../components/Nav";

export default function HowItWorks() {
  return (
    <>
      <Nav />
      <main className="page page--how-it-works">
        <h1>How it works</h1>
        <p>
          AsliGhar runs three independent checks against a listing's photos, address, and
          rent, then combines them into one explainable risk score. The score is computed
          by a transparent, deterministic formula, not a black-box model — every point
          on it traces back to a specific piece of evidence you can see.
        </p>

        <section>
          <h2>Image reuse</h2>
          <p>
            Faking a full photoshoot of a fake apartment is expensive and rare. Reusing
            someone else's real photos is cheap and common — so each submitted photo is
            reverse-searched for other listings using the same image under a different
            price or city.
          </p>
        </section>

        <section>
          <h2>Address plausibility</h2>
          <p>
            The stated address is checked against real map data. An address that doesn't
            resolve at all, or resolves to something implausible for a home (an industrial
            plot, a business park), is flagged.
          </p>
        </section>

        <section>
          <h2>Price sanity</h2>
          <p>
            The rent is compared against real comparable listings in the same locality. A
            rent well below the local median — the classic scam bait — raises the score;
            an above-median rent doesn't, since overpriced listings aren't the fraud
            pattern this tool targets.
          </p>
        </section>

        <section>
          <h2>Limitations — read this before trusting a score</h2>
          <ul>
            <li>
              This is a risk signal, not a verdict. A high score means verify further
              before paying anything, not that a listing is definitely a scam.
            </li>
            <li>
              Reverse image search coverage depends on what's indexed online. A
              brand-new scam listing with genuinely unindexed stolen photos can still
              score low.
            </li>
            <li>
              No claims are made about any individual — the tool evaluates a listing's
              internal consistency, not a person.
            </li>
          </ul>
        </section>
      </main>
    </>
  );
}
