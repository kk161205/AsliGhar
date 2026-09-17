import { Link } from "react-router-dom";

export default function Nav() {
  return (
    <header className="site-nav">
      <Link to="/" className="site-nav__brand">
        AsliGhar
      </Link>
      <nav>
        <Link to="/scan">Check a listing</Link>
        <Link to="/how-it-works">How it works</Link>
      </nav>
    </header>
  );
}
