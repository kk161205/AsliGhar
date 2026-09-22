import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Nav() {
  const { state, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  // No "Log in" link in the nav at all — reachable via the "Already have an
  // account?" link on /signup instead. "Sign up" itself is dropped on
  // Landing (the hero's "Get started" already goes there) and on /login and
  // /signup (each already has its own submit action plus a footer link to
  // the other), so it isn't repeated on a page that already offers it.
  const showSignup = pathname !== "/" && pathname !== "/login" && pathname !== "/signup";
  // On the How it works page itself, a link back to the same page is useless
  // — a "Back" button (to wherever the visitor actually came from) replaces it.
  const isHowItWorks = pathname === "/how-it-works";

  return (
    <header className="site-nav">
      <Link to="/" className="site-nav__brand">
        AsliGhar
      </Link>
      <nav>
        {isHowItWorks ? (
          <button type="button" className="site-nav__button" onClick={() => navigate(-1)}>
            Back
          </button>
        ) : (
          <Link to="/how-it-works">How it works</Link>
        )}
        {state.status === "authenticated" && (
          <>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/scan">Check a listing</Link>
            <button type="button" className="site-nav__button" onClick={handleLogout}>
              Log out
            </button>
          </>
        )}
        {state.status === "anonymous" && showSignup && <Link to="/signup">Sign up</Link>}
      </nav>
    </header>
  );
}
