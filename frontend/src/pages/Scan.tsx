import Nav from "../components/Nav";
import ScanFlow from "../components/ScanFlow";

export default function Scan() {
  return (
    <>
      <Nav />
      <main className="page page--scan">
        <h1>Check a listing</h1>
        <ScanFlow />
      </main>
    </>
  );
}
