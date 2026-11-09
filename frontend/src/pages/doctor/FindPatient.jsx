import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { QrCode, Users } from 'lucide-react';
import api from '../../api';
import { Topbar } from '../../components/Layout';
import PatientSearch from '../../components/PatientSearch';
import QrScanner from '../../components/QrScanner';
import { Avatar, Empty, Loading } from '../../components/ui';
import { formatDate, patientMeta, patientName } from '../../utils/format';

export default function FindPatient() {
  const navigate = useNavigate();
  const [scan, setScan] = useState(false);
  const [recent, setRecent] = useState(null);

  useEffect(() => {
    api.get('/api/patients', { params: { limit: 25 } }).then((r) => setRecent(r.data)).catch(() => setRecent([]));
  }, []);

  const open = (p) => navigate(`/d/patients/${p.id}`);

  return (
    <>
      <Topbar title="Find patient" sub="Search by name, phone or file number — or scan the patient’s card" />
      <div className="content stack" style={{ maxWidth: 860 }}>
        <div className="row">
          <div style={{ flex: 1 }}><PatientSearch onSelect={open} autoFocus /></div>
          <button className="btn btn-primary" onClick={() => setScan(true)}><QrCode size={16} /> Scan card</button>
        </div>
        <div className="muted small">Using a USB QR scanner? Click in the search box and scan — the file opens automatically.</div>
        <div className="card">
          <div className="card-head"><h3>Recently updated</h3></div>
          {recent === null ? <Loading /> : recent.length === 0 ? <Empty icon={Users}>No patients yet.</Empty> : recent.map((p) => (
            <div key={p.id} className="list-item clickable" onClick={() => open(p)}>
              <Avatar patient={p} />
              <div className="grow">
                <div className="title">{patientName(p)}</div>
                <div className="meta">{patientMeta(p)}</div>
              </div>
              <span className="muted small">{formatDate(p.updatedAt)}</span>
            </div>
          ))}
        </div>
      </div>
      {scan && <QrScanner onClose={() => setScan(false)} onFound={(p) => { setScan(false); open(p); }} />}
    </>
  );
}
