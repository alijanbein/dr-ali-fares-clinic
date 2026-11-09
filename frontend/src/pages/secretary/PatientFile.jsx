import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CalendarPlus, GitMerge, QrCode, Save } from 'lucide-react';
import api, { errorMessage } from '../../api';
import { Topbar } from '../../components/Layout';
import AppointmentModal from '../../components/AppointmentModal';
import PatientCard from '../../components/PatientCard';
import PatientForm, { fromPatient, toPayload } from '../../components/PatientForm';
import PatientSearch from '../../components/PatientSearch';
import { Empty, KindBadge, Loading, Modal, StatusBadge, useToast } from '../../components/ui';
import { formatDate, patientName } from '../../utils/format';

export default function PatientFile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [patient, setPatient] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const [showBook, setShowBook] = useState(false);
  const [showMerge, setShowMerge] = useState(false);

  const load = useCallback(() => {
    api.get(`/api/patients/${id}`)
      .then((res) => { setPatient(res.data); setForm(fromPatient(res.data)); })
      .catch((err) => { toast(errorMessage(err), 'error'); navigate('/s/patients'); });
  }, [id, navigate, toast]);

  useEffect(load, [load]);

  const save = async () => {
    if (!form.name.trim()) { toast('The patient’s name is required', 'error'); return; }
    setBusy(true);
    try {
      await api.patch(`/api/patients/${id}`, toPayload(form));
      toast('File saved', 'success');
      load();
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setBusy(false);
    }
  };

  const merge = async (target) => {
    if (!window.confirm(`Move this quick visit into ${patientName(target)}’s file (${target.fileNumber})? The empty quick file will be deleted.`)) return;
    try {
      await api.post(`/api/patients/${id}/merge-into/${target.id}`);
      toast('Merged into the existing file', 'success');
      navigate(`/s/patients/${target.id}`, { replace: true });
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  if (!patient) return <><Topbar title="Patient file" /><div className="content"><Loading /></div></>;

  return (
    <>
      <Topbar title={patientName(patient)} sub={`File ${patient.fileNumber}`}>
        <button className="btn btn-ghost" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Back</button>
        <button className="btn btn-outline" onClick={() => setShowCard(true)}><QrCode size={16} /> Patient card</button>
        <button className="btn btn-primary" onClick={() => setShowBook(true)}><CalendarPlus size={16} /> Book appointment</button>
      </Topbar>
      <div className="content">
        <div className="ws ws-file">
          <div className="stack">
            {patient.isQuick && (
              <div className="alert alert-warn" style={{ alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <b>Quick file — no data yet.</b> Fill in the details below, or if this patient already has a file, merge this visit into it.
                </div>
                <button className="btn btn-sm btn-warning" onClick={() => setShowMerge(true)}><GitMerge size={14} /> Merge into existing file</button>
              </div>
            )}
            <div className="card">
              <div className="card-head"><h3>Patient details</h3></div>
              <div className="card-body">
                <PatientForm value={form} onChange={setForm} autoFocus={patient.isQuick} />
                <div className="row mt"><span className="spacer" /><button className="btn btn-primary" onClick={save} disabled={busy}><Save size={16} /> Save</button></div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>Appointments</h3></div>
            {patient.appointments.length === 0 ? <Empty>No appointments yet.</Empty> : patient.appointments.map((a) => (
              <div key={a.id} className="list-item">
                <div className="grow">
                  <div className="title">{formatDate(a.date)} {a.time && <span className="muted">· {a.time}</span>}</div>
                  <div className="meta">{a.reason || '—'}</div>
                </div>
                <KindBadge kind={a.kind} />
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {showCard && <PatientCard patient={patient} onClose={() => setShowCard(false)} />}
      {showBook && <AppointmentModal patient={patient} onClose={() => setShowBook(false)} onSaved={() => { setShowBook(false); toast('Appointment booked', 'success'); load(); }} />}
      {showMerge && (
        <Modal title="Merge into an existing file" onClose={() => setShowMerge(false)}>
          <div className="stack">
            <div className="muted">Find the patient’s real file. This quick visit (and anything the doctor recorded) moves there.</div>
            <PatientSearch onSelect={merge} exclude={patient.id} autoFocus />
          </div>
        </Modal>
      )}
    </>
  );
}
