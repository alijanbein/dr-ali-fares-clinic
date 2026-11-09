import { useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import api from '../api';
import { patientMeta, patientName } from '../utils/format';
import { Avatar } from './ui';

/**
 * Search-as-you-type over name / phone / file number. Also accepts the text a
 * USB QR/barcode scanner "types" (it ends with Enter): an exact code match
 * opens that patient straight away.
 */
export default function PatientSearch({ onSelect, placeholder = 'Search by name, phone or file number…', autoFocus, exclude }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    const term = q.trim();
    if (!term) { setResults([]); return undefined; }
    setLoading(true);
    const t = setTimeout(() => {
      api.get('/api/patients', { params: { q: term, limit: 12 } })
        .then((res) => setResults(res.data.filter((p) => p.id !== exclude)))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 220);
    return () => clearTimeout(t);
  }, [q, exclude]);

  useEffect(() => {
    const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const pick = (p) => { setQ(''); setResults([]); setOpen(false); onSelect(p); };

  const onKeyDown = async (e) => {
    if (e.key !== 'Enter') return;
    const term = q.trim();
    if (!term) return;
    try {
      const { data } = await api.get('/api/patients/lookup', { params: { code: term } });
      pick(data);
    } catch {
      if (results.length === 1) pick(results[0]);
    }
  };

  return (
    <div className="searchbox" ref={boxRef}>
      <Search size={17} className="lead" />
      <input
        className="input"
        value={q}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {open && q.trim() && (
        <div className="search-results">
          {loading && !results.length && <div className="list-item muted">Searching…</div>}
          {!loading && !results.length && <div className="list-item muted">No patient found</div>}
          {results.map((p) => (
            <div key={p.id} className="list-item clickable" onClick={() => pick(p)}>
              <Avatar patient={p} />
              <div className="grow">
                <div className="title">{patientName(p)}</div>
                <div className="meta">{patientMeta(p)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
