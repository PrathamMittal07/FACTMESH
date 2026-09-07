'use client';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch, DocumentType } from './lib/api';
import UploadDropzone from './components/UploadDropzone';

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentType[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await apiFetch<DocumentType[]>('/api/documents');
      setDocuments(docs);
    } catch {
      console.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    // Poll for status updates every 5s
    const interval = setInterval(loadDocuments, 5000);
    return () => clearInterval(interval);
  }, [loadDocuments]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Fact Knowledge Layer</h1>
        <p>Upload PDFs to extract, ground, and reconcile facts across documents.</p>
      </div>

      <UploadDropzone onUploadComplete={loadDocuments} />

      <div style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary)' }}>
          Documents ({documents.length})
        </h2>

        {loading ? (
          <div className="loading"><div className="spinner" /></div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📁</div>
            <h3>No documents yet</h3>
            <p>Upload a PDF above to get started.</p>
          </div>
        ) : (
          <div className="card-grid">
            {documents.map((doc) => (
              <Link key={doc.id} href={'/documents/' + doc.id} style={{ textDecoration: 'none' }}>
                <div className="card animate-in">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
                      📄 {doc.filename}
                    </div>
                    <span className={'badge badge-' + doc.status}>{doc.status}</span>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    <span>{doc.page_count ?? '?'} pages</span>
                    <span>{doc.fact_count ?? 0} facts</span>
                    <span>{doc.issue_count ?? 0} issues</span>
                  </div>

                  <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Uploaded {new Date(doc.uploaded_at).toLocaleString()}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
