export default function RelationshipBadge({ type }: { type: string }) {
  const labels: Record<string, string> = {
    corroborates: '✓ Corroborates',
    contradicts: '✗ Contradicts',
    contextual_difference: '◐ Contextual',
    unrelated: '○ Unrelated',
  };
  return <span className={'badge badge-' + type}>{labels[type] || type}</span>;
}
