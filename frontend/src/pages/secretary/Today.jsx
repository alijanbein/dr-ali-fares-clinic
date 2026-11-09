import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, ChevronLeft, ChevronRight, ClipboardList, LogIn, MoreHorizontal, Plus, RefreshCw, Zap } from 'lucide-react';
import api, { errorMessage } from '../../api';
import { Topbar } from '../../components/Layout';
import AppointmentModal from '../../components/AppointmentModal';
import { Avatar, Empty, KindBadge, Loading, Modal, StatusBadge, useToast } from '../../components/ui';
import { addDays, formatDate, formatTime, patientMeta, patientName, todayIso } from '../../utils/format';

const GROUPS = [
  { id: 'in_progress', title: 'With the doctor', statuses: ['in_progress'] },
  { id: 'waiting', title: 'Waiting line', statuses: ['waiting'] },
  { id: 'scheduled', title: 'Booked — not arrived yet', statuses: ['scheduled'] },
  { id: 'closed', title: 'Finished', statuses: ['done', 'no_show', 'cancelled'] },
];

function QuickModal({ onClose, onCreated }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post('/api/appointments/quick', { reason });
      onCreated(data);
    } catch (err) {
      toast(errorMessage(err), 'error');
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Quick patient — no data"
      onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-warning" onClick={create} disabled={busy}><Zap size={16} /> Send to doctor</button></>}
    >
      <div className="stack">
        <div className="alert alert-warn">
          Creates an empty file and puts the patient straight in the doctor’s waiting line. Fill in their details (or merge with an existing file) later.
        </div>
        <input className="input" placeholder="Optional note for the doctor, e.g. “Back pain, urgent”" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus onKeyDown={(e) => e.key === 'Enter' && create()} />
      </div>
    </Modal>
  );
}

function AppointmentRow({ appt, onAction, onEdit, onOpen }) {
  const [menu, setMenu] = useState(false);
  const p = appt.patient;
  const numClass = appt.status === 'in_progress' ? 'active' : appt.status === 'done' ? 'done' : appt.status === 'waiting' ? '' : 'time';
  return (
    <div className="list-item">
      <div className={`queue-num ${numClass}`}>{appt.status === 'waiting' || appt.status === 'in_progress' ? `#${appt.queueNumber ?? '–'}` : appt.time || '—'}</div>
      <Avatar patient={p} />
      <div className="grow clickable" style={{ cursor: 'pointer' }} onClick={() => onOpen(p)}>
        <div className="title row" style={{ gap: 8 }}>
          {patientName(p)} <KindBadge kind={appt.kind} />
          {appt.hasIntake && <span className="badge badge-kind" title="Pre-visit questionnaire from the website"><ClipboardList size={12} /> Questionnaire</span>}
        </div>
        <div className="meta">
          {[patientMeta(p), appt.reason, appt.checkedInAt && appt.status === 'waiting' ? `arrived ${formatTime(appt.checkedInAt)}` : null].filter(Boolean).join(' · ')}
        </div>
      </div>
      <StatusBadge status={appt.status} />
      {appt.status === 'scheduled' && (
        <button className="btn btn-sm btn-primary" onClick={() => onAction(appt, 'check-in')}><LogIn size={14} /> Arrived</button>
      )}
      {p?.isQuick && <button className="btn btn-sm btn-warning" onClick={() => onOpen(p)}>Complete data</button>}
      {['scheduled', 'waiting', 'no_show', 'cancelled'].includes(appt.status) && (
        <div style={{ position: 'relative' }}>
          <button className="btn btn-sm btn-ghost btn-icon" onClick={() => setMenu(!menu)} aria-label="More"><MoreHorizontal size={16} /></button>
          {menu && (
            <div className="search-results" style={{ left: 'auto', width: 190 }} onMouseLeave={() => setMenu(false)}>
              {appt.status === 'scheduled' || appt.status === 'waiting' ? (
                <>
                  <div className="list-item clickable" onClick={() => { setMenu(false); onEdit(appt); }}>Edit / reschedule</div>
                  {appt.status === 'waiting' && <div className="list-item clickable" onClick={() => { setMenu(false); onAction(appt, 'scheduled'); }}>Undo arrival</div>}
                  <div className="list-item clickable" onClick={() => { setMenu(false); onAction(appt, 'no_show'); }}>Mark no-show</div>
                  <div className="list-item clickable" style={{ color: 'var(--danger)' }} onClick={() => { setMenu(false); onAction(appt, 'cancelled'); }}>Cancel appointment</div>
                </>
              ) : (
                <div className="list-item clickable" onClick={() => { setMenu(false); onAction(appt, 'scheduled'); }}>Restore booking</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Today() {
  const navigate = useNavigate();
  const toast = useToast();
  const [date, setDate] = useState(todayIso());
  const [appts, setAppts] = useState(null);
  const [counts, setCounts] = useState({});
  const [showNew, setShowNew] = useState(false);
  const [showQuick, setShowQuick] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    Promise.all([
      api.get('/api/appointments', { params: { date } }),
      api.get('/api/appointments/summary', { params: { date } }),
    ])
      .then(([a, s]) => { setAppts(a.data); setCounts(s.data.counts); })
      .catch((err) => { toast(errorMessage(err), 'error'); setAppts((x) => x || []); });
  }, [date, toast]);

  useEffect(() => {
    setAppts(null);
    load();
    // Keep the board in step with the doctor's room.
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const action = async (appt, what) => {
    try {
      if (what === 'check-in') await api.post(`/api/appointments/${appt.id}/check-in`);
      else await api.patch(`/api/appointments/${appt.id}`, { status: what });
      load();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const isToday = date === todayIso();
  const openPatient = (p) => p && navigate(`/s/patients/${p.id}`);

  return (
    <>
      <Topbar title="Appointments" sub={isToday ? `Today · ${formatDate(date, { weekday: 'long', day: 'numeric', month: 'long' })}` : formatDate(date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}>
        <div className="row" style={{ gap: 4 }}>
          <button className="btn btn-outline btn-icon" onClick={() => setDate(addDays(date, -1))} aria-label="Previous day"><ChevronLeft size={17} /></button>
          <input className="input" type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} style={{ width: 150 }} />
          <button className="btn btn-outline btn-icon" onClick={() => setDate(addDays(date, 1))} aria-label="Next day"><ChevronRight size={17} /></button>
          {!isToday && <button className="btn btn-outline" onClick={() => setDate(todayIso())}>Today</button>}
          <button className="btn btn-ghost btn-icon" onClick={load} title="Refresh"><RefreshCw size={16} /></button>
        </div>
        <button className="btn btn-warning" onClick={() => setShowQuick(true)}><Zap size={16} /> Quick patient</button>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}><Plus size={16} /> New appointment</button>
      </Topbar>

      <div className="content">
        <div className="stats">
          <div className="stat"><div className="num">{counts.total ?? 0}</div><div className="lbl">Patients today</div></div>
          <div className="stat"><div className="num">{counts.scheduled ?? 0}</div><div className="lbl">Not arrived</div></div>
          <div className="stat warn"><div className="num">{counts.waiting ?? 0}</div><div className="lbl">Waiting</div></div>
          <div className="stat info"><div className="num">{counts.in_progress ?? 0}</div><div className="lbl">With doctor</div></div>
          <div className="stat ok"><div className="num">{counts.done ?? 0}</div><div className="lbl">Seen</div></div>
        </div>

        {appts === null ? <Loading /> : appts.length === 0 ? (
          <div className="card"><Empty icon={CalendarDays}>No appointments on this day.</Empty></div>
        ) : (
          <div className="stack">
            {GROUPS.map((g) => {
              const items = appts.filter((a) => g.statuses.includes(a.status));
              if (!items.length) return null;
              return (
                <div key={g.id} className="card">
                  <div className="card-head"><h3>{g.title} <span className="muted">({items.length})</span></h3></div>
                  {items.map((a) => <AppointmentRow key={a.id} appt={a} onAction={action} onEdit={setEditing} onOpen={openPatient} />)}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showQuick && <QuickModal onClose={() => setShowQuick(false)} onCreated={(a) => { setShowQuick(false); toast(`Quick patient #${a.queueNumber} sent to the doctor`, 'success'); setDate(todayIso()); load(); }} />}
      {showNew && <AppointmentModal defaultDate={date} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); toast('Appointment booked', 'success'); load(); }} />}
      {editing && <AppointmentModal appointment={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); toast('Appointment updated', 'success'); load(); }} />}
    </>
  );
}
