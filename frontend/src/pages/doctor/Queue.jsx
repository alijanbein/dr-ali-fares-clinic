import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ClipboardList, Coffee, QrCode, RefreshCw } from 'lucide-react';
import api, { errorMessage } from '../../api';
import { Topbar } from '../../components/Layout';
import PatientSearch from '../../components/PatientSearch';
import QrScanner from '../../components/QrScanner';
import { Avatar, Empty, KindBadge, Loading, useToast } from '../../components/ui';
import { formatDate, formatTime, patientMeta, patientName, todayIso } from '../../utils/format';

export default function Queue() {
  const navigate = useNavigate();
  const toast = useToast();
  const [appts, setAppts] = useState(null);
  const [scan, setScan] = useState(false);

  const load = useCallback(() => {
    api.get('/api/appointments', { params: { date: todayIso() } })
      .then((res) => setAppts(res.data))
      .catch((err) => { toast(errorMessage(err), 'error'); setAppts((x) => x || []); });
  }, [toast]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const open = (patient, appt) => navigate(`/d/patients/${patient.id}${appt ? `?appt=${appt.id}` : ''}`);

  const inRoom = (appts || []).filter((a) => a.status === 'in_progress');
  const waiting = (appts || []).filter((a) => a.status === 'waiting');
  const later = (appts || []).filter((a) => a.status === 'scheduled');
  const seen = (appts || []).filter((a) => a.status === 'done');
  const next = waiting[0];

  const Row = ({ a, num, cls, action }) => (
    <div className="list-item clickable" onClick={() => open(a.patient, a)}>
      <div className={`queue-num ${cls}`}>{num}</div>
      <Avatar patient={a.patient} />
      <div className="grow">
        <div className="title row" style={{ gap: 8 }}>
          {patientName(a.patient)} <KindBadge kind={a.kind} />
          {a.hasIntake && <span className="badge badge-kind"><ClipboardList size={12} /> Questionnaire</span>}
        </div>
        <div className="meta">{[patientMeta(a.patient), a.reason].filter(Boolean).join(' · ')}</div>
      </div>
      {action}
    </div>
  );

  return (
    <>
      <Topbar title="Today’s queue" sub={formatDate(todayIso(), { weekday: 'long', day: 'numeric', month: 'long' })}>
        <div style={{ width: 340 }}><PatientSearch onSelect={(p) => open(p)} placeholder="Find any patient…" /></div>
        <button className="btn btn-primary" onClick={() => setScan(true)}><QrCode size={16} /> Scan card</button>
        <button className="btn btn-ghost btn-icon" onClick={load} title="Refresh"><RefreshCw size={16} /></button>
      </Topbar>

      <div className="content stack">
        {appts === null ? <Loading /> : (
          <>
            {inRoom.length > 0 && (
              <div className="card">
                <div className="card-head"><h3>In your room</h3></div>
                {inRoom.map((a) => <Row key={a.id} a={a} num={`#${a.queueNumber ?? '–'}`} cls="active" action={<button className="btn btn-sm btn-primary">Continue <ArrowRight size={14} /></button>} />)}
              </div>
            )}

            {next ? (
              <div className="dictate-hero">
                <div className="queue-num" style={{ background: '#fff', width: 52, height: 52, fontSize: 20 }}>#{next.queueNumber}</div>
                <div className="grow">
                  <h3>Next: {patientName(next.patient)}</h3>
                  <p>{[patientMeta(next.patient), next.reason].filter(Boolean).join(' · ') || 'No details yet'}</p>
                </div>
                <button className="btn btn-lg" onClick={() => open(next.patient, next)}>Call in <ArrowRight size={16} /></button>
              </div>
            ) : inRoom.length === 0 && (
              <div className="card"><Empty icon={Coffee}>Nobody is waiting right now.</Empty></div>
            )}

            {waiting.length > 1 && (
              <div className="card">
                <div className="card-head"><h3>Waiting <span className="muted">({waiting.length - 1} after next)</span></h3></div>
                {waiting.slice(1).map((a) => <Row key={a.id} a={a} num={`#${a.queueNumber}`} cls="" action={a.checkedInAt && <span className="muted small">since {formatTime(a.checkedInAt)}</span>} />)}
              </div>
            )}

            {later.length > 0 && (
              <div className="card">
                <div className="card-head"><h3>Booked, not arrived yet</h3></div>
                {later.map((a) => <Row key={a.id} a={a} num={a.time || '—'} cls="time" />)}
              </div>
            )}

            {seen.length > 0 && (
              <div className="card">
                <div className="card-head"><h3>Seen today <span className="muted">({seen.length})</span></h3></div>
                {seen.map((a) => <Row key={a.id} a={a} num="✓" cls="done" />)}
              </div>
            )}
          </>
        )}
      </div>

      {scan && <QrScanner onClose={() => setScan(false)} onFound={(p) => { setScan(false); open(p); }} />}
    </>
  );
}
