import { Image, IndianRupee, MapPin } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import HouseIllustration from "../components/HouseIllustration";
import IconBadge from "../components/IconBadge";
import Nav from "../components/Nav";

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
            <HouseIllustration />
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
