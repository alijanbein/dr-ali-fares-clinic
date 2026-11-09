import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, UserPlus, Users } from 'lucide-react';
import api, { errorMessage } from '../../api';
import { Topbar } from '../../components/Layout';
import PatientForm, { EMPTY_PATIENT, toPayload } from '../../components/PatientForm';
import { Avatar, Empty, Loading, Modal, useToast } from '../../components/ui';
import { formatDate, patientName } from '../../utils/format';

export default function Patients() {
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [quickOnly, setQuickOnly] = useState(false);
  const [patients, setPatients] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState(EMPTY_PATIENT);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      api.get('/api/patients', { params: { q, quick_only: quickOnly, limit: 100 } })
        .then((res) => setPatients(res.data))
        .catch((err) => { toast(errorMessage(err), 'error'); setPatients([]); });
    }, 200);
    return () => clearTimeout(t);
  }, [q, quickOnly, toast]);

  const create = async () => {
    if (!form.name.trim()) { toast('The patient’s name is required', 'error'); return; }
    setBusy(true);
    try {
      const { data } = await api.post('/api/patients', toPayload(form));
      toast(`File ${data.fileNumber} created`, 'success');
      navigate(`/s/patients/${data.id}`);
    } catch (err) {
      toast(errorMessage(err), 'error');
      setBusy(false);
    }
  };

  return (
    <>
      <Topbar title="Patients" sub="Every patient file in the clinic">
        <button className="btn btn-primary" onClick={() => { setForm(EMPTY_PATIENT); setShowNew(true); }}><UserPlus size={16} /> New patient</button>
      </Topbar>
      <div className="content stack">
        <div className="row-wrap">
          <div className="searchbox" style={{ flex: 1, minWidth: 240 }}>
            <Search size={17} className="lead" />
            <input className="input" placeholder="Search by name, phone or file number…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          </div>
          <div className="tabs">
            <button className={`tab ${!quickOnly ? 'active' : ''}`} onClick={() => setQuickOnly(false)}>All</button>
            <button className={`tab ${quickOnly ? 'active' : ''}`} onClick={() => setQuickOnly(true)}>Quick files missing data</button>
          </div>
        </div>

        <div className="card">
          {patients === null ? <Loading /> : patients.length === 0 ? (
            <Empty icon={Users}>{q ? 'No patient matches your search.' : quickOnly ? 'Every quick file has been completed.' : 'No patients yet.'}</Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Patient</th><th>File</th><th>Phone</th><th>Age</th><th>Gender</th><th>Last updated</th></tr>
                </thead>
                <tbody>
                  {patients.map((p) => (
                    <tr key={p.id} className="clickable" onClick={() => navigate(`/s/patients/${p.id}`)}>
                      <td>
                        <div className="row"><Avatar patient={p} /><div><div className="strong">{patientName(p)}</div>{p.isQuick && <span className="badge badge-quick">Missing data</span>}</div></div>
                      </td>
                      <td style={{ fontFamily: 'ui-monospace, monospace' }}>{p.fileNumber}</td>
                      <td>{p.phone || '—'}</td>
                      <td>{p.age ?? '—'}</td>
                      <td>{p.gender || '—'}</td>
                      <td className="muted">{formatDate(p.updatedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showNew && (
        <Modal
          size="lg"
          title="New patient"
          onClose={() => setShowNew(false)}
          footer={<><button className="btn" onClick={() => setShowNew(false)}>Cancel</button><button className="btn btn-primary" onClick={create} disabled={busy}>Create file</button></>}
        >
          <PatientForm value={form} onChange={setForm} autoFocus />
        </Modal>
      )}
    </>
  );
}
