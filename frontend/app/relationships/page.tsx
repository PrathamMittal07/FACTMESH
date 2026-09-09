'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiFetch, RelationshipType } from '../lib/api';
import RelationshipBadge from '../components/RelationshipBadge';

export default function RelationshipsPage() {
  const [relationships, setRelationships] = useState<RelationshipType[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);
  // True per-type totals, fetched once unfiltered (the display list above is
  // capped at 200 rows, so its length can't serve as a count). 500 is the
  // API's max page size; totals cap there on very large corpora.
  const [counts, setCounts] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    async function loadCounts() {
      try {
        const all = await apiFetch<RelationshipType[]>('/api/relationships?limit=500');
        const tally: Record<string, number> = { all: all.length };
        for (const rel of all) {
          tally[rel.relationship_type] = (tally[rel.relationship_type] ?? 0) + 1;
        }
        setCounts(tally);
      } catch (err) {
        console.error(err); // buttons simply render without counts
      }
    }
    loadCounts();
  }, []);

  useEffect(() => {
    async function load() {
      try {
        const url = filter
          ? '/api/relationships?relationship_type=' + filter + '&limit=200'
          : '/api/relationships?limit=200';
        const data = await apiFetch<RelationshipType[]>(url);
        setRelationships(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    setLoading(true);
    load();
  }, [filter]);

  const types = ['corroborates', 'contradicts', 'contextual_difference'];

  function countLabel(t: string | null) {
    if (!counts) return '';
    const n = t === null ? counts.all ?? 0 : counts[t] ?? 0;
    return ' (' + n + ')';
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Cross-Document Relationships</h1>
        <p>Facts compared across documents — corroborations, contradictions, and contextual differences.</p>
      </div>

      <div className="filter-bar">
        <button className={'filter-btn' + (filter === null ? ' active' : '')} onClick={() => setFilter(null)}>All{countLabel(null)}</button>
        {types.map((t) => (
          <button key={t} className={'filter-btn' + (filter === t ? ' active' : '')} onClick={() => setFilter(t)}>
            {t === 'contextual_difference' ? 'Contextual' : t.charAt(0).toUpperCase() + t.slice(1)}{countLabel(t)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : relationships.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#128279;</div>
          <h3>No relationships found</h3>
          <p>Upload and process documents to discover cross-document relationships.</p>
        </div>
      ) : (
        relationships.map((rel) => (
          <div key={rel.id} className="relationship-card animate-in">
            <div className="relationship-header">
              <RelationshipBadge type={rel.relationship_type} />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Confidence: {(rel.confidence * 100).toFixed(0)}%
              </span>
            </div>

            <div className="relationship-facts">
              {rel.fact_a && (
                <Link href={'/facts/' + rel.fact_a.id} style={{ textDecoration: 'none' }}>
                  <div className="card">
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                      {rel.fact_a.entity}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{rel.fact_a.metric}</div>
                    <div style={{ color: 'var(--accent)', fontWeight: 700, margin: '0.5rem 0' }}>
                      {rel.fact_a.value} {rel.fact_a.unit || ''}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {rel.fact_a.document_filename}
                      {rel.fact_a.time_period && <> · {rel.fact_a.time_period}</>}
                      {rel.fact_a.scope && <> · {rel.fact_a.scope}</>}
                    </div>
                  </div>
                </Link>
              )}

              <div className="relationship-arrow">⟷</div>

              {rel.fact_b && (
                <Link href={'/facts/' + rel.fact_b.id} style={{ textDecoration: 'none' }}>
                  <div className="card">
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                      {rel.fact_b.entity}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{rel.fact_b.metric}</div>
                    <div style={{ color: 'var(--accent)', fontWeight: 700, margin: '0.5rem 0' }}>
                      {rel.fact_b.value} {rel.fact_b.unit || ''}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {rel.fact_b.document_filename}
                      {rel.fact_b.time_period && <> · {rel.fact_b.time_period}</>}
                      {rel.fact_b.scope && <> · {rel.fact_b.scope}</>}
                    </div>
                  </div>
                </Link>
              )}
            </div>

            <div className="relationship-reasoning">
              <strong style={{ color: 'var(--text-primary)' }}>Reasoning:</strong> {rel.reasoning}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
