import { Image, IndianRupee, MapPin } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import IconBadge from "../components/IconBadge";
import Nav from "../components/Nav";

// A static, illustrative sample result — never wired to a real scan — filling
// the hero's empty space so the value proposition is shown, not just described.
function SampleScoreCard() {
  return (
    <div className="score-card" aria-hidden="true">
      <p className="score-card__label">
        <span className="score-card__dot" />
        Sample scan result
      </p>
      <div className="score-card__band">
        <span className="score-card__band-name">High risk</span>
        <span className="score-card__score mono">62 / 100</span>
      </div>
      <div className="score-card__track">
        <div className="score-card__fill" />
      </div>
      <div className="score-card__rows">
        <div className="score-card__row">
          <span className="score-card__row-name">
            <Image size={15} strokeWidth={1.75} />
            Image reuse
          </span>
          <span className="score-card__row-value">Proven match</span>
        </div>
        <div className="score-card__row">
          <span className="score-card__row-name">
            <IndianRupee size={15} strokeWidth={1.75} />
            Price sanity
          </span>
          <span className="score-card__row-value">38% below median</span>
        </div>
        <div className="score-card__row">
          <span className="score-card__row-name">
            <MapPin size={15} strokeWidth={1.75} />
            Address
          </span>
          <span className="score-card__row-value">Resolves fine</span>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const { state } = useAuth();

  if (state.status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <>
      <Nav />
      <main className="page page--home">
        <section className="hero">
          <div className="hero__copy">
            <h1>
              Is this rental listing <span className="hero__highlight">real</span>?
            </h1>
            <p className="hero__lede">
              Reused photos are the highest-signal rental scam tell, and reverse-searching
              every photo of every listing you're considering isn't something anyone
              actually does by hand. AsliGhar does it for you, in about 15 seconds.
            </p>
            <Link to="/signup" className="button-primary hero__cta">
              Get started
            </Link>
          </div>
          <div className="hero__visual">
            <SampleScoreCard />
          </div>
        </section>

        <section className="how-it-works-teaser">
          <h2>Three checks, one score</h2>
          <div className="how-it-works-teaser__grid">
            <div>
              <IconBadge>
                <Image aria-hidden="true" size={22} strokeWidth={1.75} />
              </IconBadge>
              <h3>Image reuse</h3>
              <p>Do these exact photos appear elsewhere, under a different price or city?</p>
            </div>
            <div>
              <IconBadge>
                <MapPin aria-hidden="true" size={22} strokeWidth={1.75} />
              </IconBadge>
              <h3>Address plausibility</h3>
              <p>Does the stated address resolve to a real, sensible location?</p>
            </div>
            <div>
              <IconBadge>
                <IndianRupee aria-hidden="true" size={22} strokeWidth={1.75} />
              </IconBadge>
              <h3>Price sanity</h3>
              <p>How far is the rent from comparable listings in that locality?</p>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
