'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiFetch, FactType, RelationshipType } from '../../lib/api';
import EvidencePanel from '../../components/EvidencePanel';
import RelationshipBadge from '../../components/RelationshipBadge';

interface FactDetail extends FactType {
  relationships: RelationshipType[];
}

export default function FactDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [fact, setFact] = useState<FactDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<FactDetail>('/api/facts/' + id);
        setFact(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <div className="page-container"><div className="loading"><div className="spinner" /></div></div>;
  if (!fact) return <div className="page-container"><div className="empty-state"><h3>Fact not found</h3></div></div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>{fact.entity}: {fact.metric}</h1>
        <p>
          <span className="badge" style={{ background: 'var(--bg-glass)', color: 'var(--accent)', marginRight: '0.5rem' }}>{fact.fact_type}</span>
          From <Link href={'/documents/' + fact.document_id} style={{ color: 'var(--accent)' }}>{fact.document_filename}</Link>
          , page {fact.page_number}
        </p>
      </div>

      <div className="card" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Value</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent)', marginTop: '0.25rem' }}>{fact.value || 'N/A'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Unit</div>
            <div style={{ fontSize: '1rem', marginTop: '0.25rem', color: 'var(--text-secondary)' }}>{fact.unit || 'None'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Time Period</div>
            <div style={{ fontSize: '1rem', marginTop: '0.25rem', color: 'var(--text-secondary)' }}>{fact.time_period || 'Not specified'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Scope</div>
            <div style={{ fontSize: '1rem', marginTop: '0.25rem', color: 'var(--text-secondary)' }}>{fact.scope || 'Not specified'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Confidence</div>
            <div style={{ marginTop: '0.25rem' }}>
              <div className="confidence-bar">
                <div className="confidence-track" style={{ maxWidth: '120px' }}>
                  <div className="confidence-fill" style={{
                    width: (fact.confidence * 100) + '%',
                    background: fact.confidence >= 0.7 ? 'var(--color-high-conf)' : fact.confidence >= 0.4 ? 'var(--color-med-conf)' : 'var(--color-low-conf)'
                  }} />
                </div>
                <span className="confidence-label">{(fact.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        </div>

        <EvidencePanel fact={fact} />
      </div>

      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>
        Relationships ({fact.relationships?.length || 0})
      </h2>

      {(!fact.relationships || fact.relationships.length === 0) ? (
        <div className="empty-state" style={{ padding: '2rem' }}>
          <h3>No relationships found</h3>
          <p>This fact has no cross-document relationships yet.</p>
        </div>
      ) : (
        fact.relationships.map((rel) => {
          const otherFact = rel.fact_a_id === fact.id ? rel.fact_b : rel.fact_a;
          return (
            <div key={rel.id} className="relationship-card animate-in">
              <div className="relationship-header">
                <RelationshipBadge type={rel.relationship_type} />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Confidence: {(rel.confidence * 100).toFixed(0)}%
                </span>
              </div>

              {otherFact && (
                <Link href={'/facts/' + otherFact.id} style={{ textDecoration: 'none' }}>
                  <div className="card" style={{ marginBottom: '1rem' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{otherFact.entity}: {otherFact.metric}</div>
                    <div style={{ color: 'var(--accent)', fontWeight: 700, margin: '0.25rem 0' }}>{otherFact.value} {otherFact.unit || ''}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {otherFact.document_filename} &middot; Page {otherFact.page_number}
                      {otherFact.time_period && <> &middot; {otherFact.time_period}</>}
                      {otherFact.scope && <> &middot; {otherFact.scope}</>}
                    </div>
                  </div>
                </Link>
              )}

              <div className="relationship-reasoning">
                <strong style={{ color: 'var(--text-primary)' }}>Reasoning:</strong> {rel.reasoning}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}