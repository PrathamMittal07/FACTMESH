'use client';
import { useEffect, useState } from 'react';
import { apiFetch, IssueType } from '../lib/api';

export default function IssuesPage() {
  const [issues, setIssues] = useState<IssueType[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const url = filter
          ? '/api/issues?issue_type=' + filter + '&limit=200'
          : '/api/issues?limit=200';
        const data = await apiFetch<IssueType[]>(url);
        setIssues(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    setLoading(true);
    load();
  }, [filter]);

  const issueTypes = ['parse_error', 'low_confidence', 'ambiguous_unit', 'llm_refused', 'extraction_note'];

  // One style source per issue_type: matching icon + text color + tinted
  // background + outline so the badge reads at a glance. Informational
  // notes stay neutral gray; real failures stay red.
  const ISSUE_STYLES: Record<string, { icon: string; color: string; bg: string }> = {
    parse_error: { icon: '⚠️', color: 'var(--color-contradict)', bg: 'var(--color-contradict-bg)' },
    low_confidence: { icon: '📉', color: 'var(--color-contextual)', bg: 'var(--color-contextual-bg)' },
    ambiguous_unit: { icon: '❓', color: 'var(--color-contextual)', bg: 'var(--color-contextual-bg)' },
    llm_refused: { icon: '🚫', color: 'var(--color-contradict)', bg: 'var(--color-contradict-bg)' },
    extraction_note: { icon: '📝', color: 'var(--color-unrelated)', bg: 'var(--color-unrelated-bg)' },
  };

  function getIssueStyle(type: string) {
    return ISSUE_STYLES[type] ?? { icon: '⚡', color: 'var(--color-unrelated)', bg: 'var(--color-unrelated-bg)' };
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Extraction Issues</h1>
        <p>Parse errors, low-confidence extractions, and reasoning failures — documented, not hidden.</p>
      </div>

      <div className="filter-bar">
        <button className={'filter-btn' + (filter === null ? ' active' : '')} onClick={() => setFilter(null)}>All ({issues.length})</button>
        {issueTypes.map((t) => (
          <button key={t} className={'filter-btn' + (filter === t ? ' active' : '')} onClick={() => setFilter(t)}>
            {t.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : issues.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✅</div>
          <h3>No issues found</h3>
          <p>All extractions completed without issues{filter ? ' of this type' : ''}.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {issues.map((issue) => (
            <div key={issue.id} className="card animate-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>{getIssueStyle(issue.issue_type).icon}</span>
                  <span className="badge" style={{
                    background: getIssueStyle(issue.issue_type).bg,
                    color: getIssueStyle(issue.issue_type).color,
                    border: '1px solid ' + getIssueStyle(issue.issue_type).color,
                  }}>
                    {issue.issue_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {issue.page_number ? 'Page ' + issue.page_number : 'Document-level'}
                </span>
              </div>

              <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                {issue.detail}
              </div>

              {issue.raw_text_snippet && (
                <div style={{
                  background: 'var(--bg-glass)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem',
                  fontSize: '0.8rem',
                  color: 'var(--text-muted)',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  overflow: 'hidden',
                  maxHeight: '100px',
                }}>
                  {issue.raw_text_snippet}
                </div>
              )}

              <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {issue.document_filename || 'Unknown document'} · {new Date(issue.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
