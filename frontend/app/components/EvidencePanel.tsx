import { FactType } from '../lib/api';

export default function EvidencePanel({ fact }: { fact: FactType }) {
  return (
    <div className="evidence-panel">
      <div className="evidence-quote">&ldquo;{fact.evidence_quote}&rdquo;</div>
      <div className="evidence-meta">
        Page {fact.page_number} &middot; {fact.document_filename || 'Unknown document'}
        {fact.scope && <> &middot; {fact.scope}</>}
        {fact.time_period && <> &middot; {fact.time_period}</>}
      </div>
    </div>
  );
}
