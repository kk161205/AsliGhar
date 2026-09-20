import { Link } from "react-router-dom";
import Nav from "../components/Nav";

export default function NotFound() {
  return (
    <>
      <Nav />
      <main className="page page--not-found">
        <h1>Page not found</h1>
        <p>There's nothing at this address. <Link to="/">Back to the homepage</Link>.</p>
      </main>
    </>
  );
}
