export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function addDays(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(y, m - 1, d + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function formatDate(iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
}

export function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function patientName(p) {
  if (!p) return 'Unknown';
  if (p.name) return p.name;
  return p.isQuick ? `Quick patient · ${p.fileNumber}` : p.fileNumber;
}

export function patientMeta(p) {
  if (!p) return '';
  return [p.fileNumber, p.age != null ? `${p.age} y` : null, p.gender, p.phone].filter(Boolean).join(' · ');
}

export const STATUS_LABELS = {
  scheduled: 'Scheduled',
  waiting: 'Waiting',
  in_progress: 'With doctor',
  done: 'Done',
  cancelled: 'Cancelled',
  no_show: 'No-show',
};

export const KIND_LABELS = {
  scheduled: 'Appointment',
  walk_in: 'Walk-in',
  quick: 'Quick',
  follow_up: 'Follow-up',
};
