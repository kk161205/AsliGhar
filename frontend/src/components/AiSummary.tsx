interface AiSummaryProps {
  summary: string | null;
}

// Deliberately secondary to the evidence: the system's trust comes from the
// data above, with this as a convenience layer on top, not the other way round.
export default function AiSummary({ summary }: AiSummaryProps) {
  return (
    <div className="ai-summary">
      <h3 className="ai-summary__heading">In plain terms</h3>
      <p className="ai-summary__body">{summary ?? "See evidence below."}</p>
    </div>
  );
}
