import { FactType } from '../lib/api';
import Link from 'next/link';

function getConfidenceClass(confidence: number) {
  if (confidence >= 0.7) return 'high-confidence';
  if (confidence >= 0.4) return 'med-confidence';
  return 'low-confidence';
}

export default function FactCard({ fact }: { fact: FactType }) {
  return (
    <Link href={'/facts/' + fact.id} style={{ textDecoration: 'none' }}>
      <div className="card animate-in">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
          <span className={'badge badge-' + fact.fact_type} style={{ background: 'var(--bg-glass)', color: 'var(--accent)' }}>
            {fact.fact_type}
          </span>
          <div className="confidence-bar">
            <div className="confidence-track">
              <div className="confidence-fill" style={{
                width: (fact.confidence * 100) + '%',
                background: fact.confidence >= 0.7 ? 'var(--color-high-conf)' : fact.confidence >= 0.4 ? 'var(--color-med-conf)' : 'var(--color-low-conf)'
              }} />
            </div>
            <span className={'confidence-label badge-' + getConfidenceClass(fact.confidence)} style={{ color: fact.confidence >= 0.7 ? 'var(--color-high-conf)' : fact.confidence >= 0.4 ? 'var(--color-med-conf)' : 'var(--color-low-conf)' }}>
              {(fact.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {fact.entity && <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>{fact.entity}</div>}
        {fact.metric && <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>{fact.metric}</div>}

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          {fact.value && <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--accent)' }}>{fact.value}</span>}
          {fact.unit && <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', alignSelf: 'center' }}>{fact.unit}</span>}
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', fontSize: '0.75rem' }}>
          {fact.time_period && <span className="badge" style={{ background: 'var(--bg-glass)', color: 'var(--text-secondary)' }}>{fact.time_period}</span>}
          {fact.scope && <span className="badge" style={{ background: 'var(--bg-glass)', color: 'var(--text-secondary)' }}>{fact.scope}</span>}
        </div>

        <div className="evidence-panel" style={{ marginTop: '0.75rem' }}>
          <div className="evidence-quote">"{fact.evidence_quote}"</div>
          <div className="evidence-meta">Page {fact.page_number} · {fact.document_filename || 'Unknown document'}</div>
        </div>
      </div>
    </Link>
  );
}
