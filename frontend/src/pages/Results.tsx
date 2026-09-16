import { useParams } from "react-router-dom";

export default function Results() {
  const { scanId } = useParams();
  return (
    <main>
      <h1>Scan result</h1>
      <p className="mono">{scanId}</p>
    </main>
  );
}
