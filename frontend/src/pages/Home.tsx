import { Link } from "react-router-dom";
import Nav from "../components/Nav";
import ScanFlow from "../components/ScanFlow";

export default function Home() {
  return (
    <>
      <Nav />
      <main className="page page--home">
        <section className="hero">
          <h1>Is this rental listing real?</h1>
          <p className="hero__lede">
            Reused photos are the highest-signal rental scam tell, and reverse-searching
            every photo of every listing you're considering isn't something anyone
            actually does by hand. AsliGhar does it for you, in about 15 seconds.
          </p>
        </section>

        <section className="scan-section" aria-label="Check a listing">
          <ScanFlow />
        </section>

        <section className="how-it-works-teaser">
          <h2>Three checks, one score</h2>
          <div className="how-it-works-teaser__grid">
            <div>
              <h3>Image reuse</h3>
              <p>Do these exact photos appear elsewhere, under a different price or city?</p>
            </div>
            <div>
              <h3>Address plausibility</h3>
              <p>Does the stated address resolve to a real, sensible location?</p>
            </div>
            <div>
              <h3>Price sanity</h3>
              <p>How far is the rent from comparable listings in that locality?</p>
            </div>
          </div>
          <Link to="/how-it-works">Read more about how it works</Link>
        </section>
      </main>
    </>
  );
}
