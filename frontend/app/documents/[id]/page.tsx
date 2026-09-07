'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { apiFetch, DocumentType, FactType } from '../../lib/api';
import FactCard from '../../components/FactCard';

interface DocumentDetail extends DocumentType {
  relationship_count: number;
}

export default function DocumentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [facts, setFacts] = useState<FactType[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [docData, factsData] = await Promise.all([
          apiFetch<DocumentDetail>('/api/documents/' + id),
          apiFetch<FactType[]>('/api/facts?document_id=' + id + '&limit=500'),
        ]);
        setDoc(docData);
        setFacts(factsData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <div className="page-container"><div className="loading"><div className="spinner" /></div></div>;
  if (!doc) return <div className="page-container"><div className="empty-state"><h3>Document not found</h3></div></div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>{doc.filename}</h1>
        <p>
          <span className={'badge badge-' + doc.status} style={{ marginRight: '0.5rem' }}>{doc.status}</span>
          {doc.page_count} pages &middot; Uploaded {new Date(doc.uploaded_at).toLocaleString()}
        </p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{doc.fact_count ?? facts.length}</div>
          <div className="stat-label">Facts Extracted</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{doc.relationship_count ?? 0}</div>
          <div className="stat-label">Relationships</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{doc.issue_count ?? 0}</div>
          <div className="stat-label">Issues</div>
        </div>
      </div>

      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>
        Extracted Facts ({facts.length})
      </h2>

      {facts.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#128270;</div>
          <h3>No facts extracted yet</h3>
          <p>{doc.status === 'processing' ? 'Document is still being processed...' : 'No facts could be extracted from this document.'}</p>
        </div>
      ) : (
        <div className="card-grid">
          {facts.map((fact) => (
            <FactCard key={fact.id} fact={fact} />
          ))}
        </div>
      )}
    </div>
  );
}