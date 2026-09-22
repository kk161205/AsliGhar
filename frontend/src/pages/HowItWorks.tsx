import Nav from "../components/Nav";

export default function HowItWorks() {
  return (
    <>
      <Nav />
      <main className="page page--how-it-works">
        <h1>How it works</h1>
        <p>
          You submit a listing's photos, address and rent — plus, if you have them, the
          listing link and the contact number, which sharpen the checks below. AsliGhar runs
          three independent checks and combines them into one explainable risk score (0–100).
          The score itself is a transparent, deterministic formula, not a model's guess —
          every point on it traces back to a specific piece of evidence you can see. A
          language model only reads your address and writes the plain-language summary at the
          bottom; it never decides the score.
        </p>

        <section>
          <h2>Image reuse</h2>
          <p>
            Faking a full photoshoot of a fake apartment is expensive and rare. Reusing
            someone else's real photos is cheap and common — so each submitted photo is
            reverse-searched for other pages carrying that exact image, on any site, not
            a fixed list of them. A match only counts if the page itself contradicts your
            listing: it's for sale rather than rent, it's priced differently, or it's in a
            different city.
          </p>
          <p>
            Each match is labelled <strong>Proven</strong> or <strong>Indicator</strong>.
            Proven means it was confirmed by more than one independent signal — two of your
            photos landing on the same page, or one photo plus the phone number or your
            description's own wording also pointing at it — or a single photo on a site
            we already know how to read reliably. Indicator means one photo turned up
            evidence worth checking, without that second confirmation. Uploading two or
            more photos of the same room is what lets a match reach Proven on any site.
          </p>
        </section>

        <section>
          <h2>Price sanity</h2>
          <p>
            The rent is compared against other pages quoting a rent for the same city and
            home size. Only a rent well below that median counts against the listing — the
            classic scam bait — never an above-median one, since overpriced listings aren't
            the fraud pattern this checks for. Giving the home size (BHK) sharpens the
            comparison; without it, this check counts for less toward the total score. If
            too few comparable rents can be found, the check says so honestly rather than
            guessing from thin data.
          </p>
        </section>

        <section>
          <h2>Address plausibility</h2>
          <p>
            The address is looked up as you typed it. An address that doesn't resolve at
            all, or resolves to something implausible for a home — an industrial plot, a
            business park — is flagged; one that resolves to a real place in a different
            city is flagged too.
          </p>
        </section>

        <section>
          <h2>Also worth knowing — never part of the score</h2>
          <p>
            Alongside the three checks, you'll also see unscored context where it applies:
            phrasing in the description that's common in rental scams (asking for money
            before a visit, pushing you off phone calls, unusual urgency), what a pasted
            listing link says on its own page, where a phone number turns up elsewhere,
            whether the address's pincode matches what the map shows, and whether a photo
            has clearly been online for a long time. None of it changes the
            score — it's there for you to read, not for the tool to judge on your behalf.
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
              Coverage depends on what's actually indexed online. A brand-new scam listing
              with genuinely unindexed stolen photos, or one on a site this tool doesn't
              read well yet, can still score low.
            </li>
            <li>
              A single photo on an unfamiliar site is only ever an Indicator, not proof —
              worth checking yourself, not a confirmed match.
            </li>
            <li>
              If a check couldn't be completed — a search failed, or too little data came
              back — the result says so plainly instead of quietly scoring it as clean.
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
