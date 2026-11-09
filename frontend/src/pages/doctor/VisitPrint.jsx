import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Printer } from 'lucide-react';
import api, { errorMessage } from '../../api';
import VisitSummary from '../../components/VisitSummary';
import { Loading } from '../../components/ui';
import { formatDate, patientName } from '../../utils/format';

const CLINIC_NAME = import.meta.env.VITE_CLINIC_NAME || 'Orthopedic Clinic';

export default function VisitPrint() {
  const { id } = useParams();
  const [visit, setVisit] = useState(null);
  const [patient, setPatient] = useState(null);
  const [options, setOptions] = useState(null);
  const [mode, setMode] = useState('report');
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const v = (await api.get(`/api/visits/${id}`)).data;
        const [p, o] = await Promise.all([api.get(`/api/patients/${v.patientId}`), api.get('/api/options')]);
        setVisit(v); setPatient(p.data); setOptions(o.data);
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, [id]);

  if (error) return <div className="print-page"><div className="alert alert-error">{error}</div></div>;
  if (!visit || !patient) return <Loading />;

  const rxOnly = mode === 'rx';
  return (
    <div style={{ background: 'var(--bg)', minHeight: '100vh', padding: '20px 0' }}>
      <div className="no-print row" style={{ maxWidth: 800, margin: '0 auto 12px', padding: '0 16px' }}>
        <div className="tabs">
          <button className={`tab ${!rxOnly ? 'active' : ''}`} onClick={() => setMode('report')}>Visit report</button>
          <button className={`tab ${rxOnly ? 'active' : ''}`} onClick={() => setMode('rx')} disabled={!visit.prescriptions.length}>Prescription only</button>
        </div>
        <span className="spacer" />
        <button className="btn btn-primary" onClick={() => window.print()}><Printer size={16} /> Print</button>
      </div>

      <div className="print-page card">
        <div className="print-head">
          <div>
            <h1>{CLINIC_NAME}</h1>
            <div className="muted">{visit.doctor}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="strong">{rxOnly ? 'Prescription' : 'Visit report'}</div>
            <div className="muted">{formatDate(visit.date)}</div>
          </div>
        </div>

        <div className="grid-3 mb" style={{ fontSize: 13 }}>
          <div><span className="muted">Patient</span><div className="strong">{patientName(patient)}</div></div>
          <div><span className="muted">File</span><div className="strong">{patient.fileNumber}</div></div>
          <div><span className="muted">Age / gender</span><div className="strong">{[patient.age, patient.gender].filter((x) => x != null && x !== '').join(' · ') || '—'}</div></div>
          {patient.allergies && <div className="span-3" style={{ color: 'var(--danger)' }}><b>Allergies:</b> {patient.allergies}</div>}
        </div>

        {rxOnly ? (
          <VisitSummary
            visit={{ prescriptions: visit.prescriptions, diagnosis: visit.diagnosis, followUpDate: visit.followUpDate }}
            tests={options.diagnosticTests}
            treatments={options.treatmentOptions}
          />
        ) : (
          <VisitSummary visit={{ ...visit, notes: '' }} tests={options.diagnosticTests} treatments={options.treatmentOptions} />
        )}

        <div style={{ marginTop: 48, display: 'flex', justifyContent: 'flex-end' }}>
          <div style={{ borderTop: '1px solid var(--border-dark)', paddingTop: 6, width: 220, textAlign: 'center' }} className="small muted">
            Signature · {visit.doctor}
          </div>
        </div>
      </div>
    </div>
  );
}
