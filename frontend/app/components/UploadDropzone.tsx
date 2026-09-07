'use client';
import { useCallback, useState } from 'react';
import { apiUpload } from '../lib/api';

export default function UploadDropzone({ onUploadComplete }: { onUploadComplete?: () => void }) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setMessage({ text: 'Only PDF files are accepted.', type: 'error' });
      return;
    }
    setUploading(true);
    setMessage(null);
    try {
      const result = await apiUpload(file);
      setMessage({ text: result.message || 'Upload successful! Processing started.', type: 'success' });
      onUploadComplete?.();
    } catch (err: unknown) {
      setMessage({ text: (err as Error).message || 'Upload failed.', type: 'error' });
    } finally {
      setUploading(false);
    }
  }, [onUploadComplete]);

  return (
    <div
      className={'dropzone' + (dragOver ? ' dragover' : '')}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleUpload(file);
      }}
      onClick={() => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf';
        input.onchange = (e) => {
          const file = (e.target as HTMLInputElement).files?.[0];
          if (file) handleUpload(file);
        };
        input.click();
      }}
    >
      <div className="dropzone-icon">{uploading ? '⏳' : '📄'}</div>
      <div className="dropzone-text">
        {uploading ? (
          'Uploading and processing...'
        ) : (
          <>Drop a PDF here or <strong>click to browse</strong></>
        )}
      </div>
      {message && (
        <p style={{
          marginTop: '1rem',
          color: message.type === 'error' ? 'var(--color-contradict)' : 'var(--color-corroborate)',
          fontSize: '0.875rem'
        }}>
          {message.text}
        </p>
      )}
    </div>
  );
}
