import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CalendarCheck, Globe, Phone, XCircle } from 'lucide-react';
import api, { errorMessage } from '../../api';
import { Topbar } from '../../components/Layout';
import { Empty, Field, Loading, Modal, useToast } from '../../components/ui';
import { formatDate, formatDateTime, todayIso } from '../../utils/format';

const TIME_LABELS = { any: 'Any time', morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' };

function ScheduleModal({ request, onClose, onDone }) {
  const [date, setDate] = useState(request.preferredDate && request.preferredDate >= todayIso() ? request.preferredDate : todayIso());
  const [time, setTime] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/api/booking-requests/${request.reference}/schedule`, { date, time: time || null });
      onDone();
    } catch (err) {
      toast(errorMessage(err), 'error');
      setBusy(false);
    }
  };
  return (
    <Modal
      title={`Book ${request.name}`}
      onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={save} disabled={busy}><CalendarCheck size={16} /> Book appointment</button></>}
    >
      <div className="stack">
        <div className="muted">Creates (or reuses) the patient’s clinic file and books the appointment. The questionnaire answers go to the doctor with it.</div>
        <div className="grid-2">
          <Field label="Date"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label={`Time (asked for: ${TIME_LABELS[request.preferredTime] || request.preferredTime})`}><input className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} /></Field>
        </div>
      </div>
    </Modal>
  );
}

export default function Requests() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [booking, setBooking] = useState(null);

  const load = useCallback(() => {
    api.get('/api/booking-requests')
      .then((res) => setData(res.data))
      .catch((err) => { toast(errorMessage(err), 'error'); setData({ available: true, items: [] }); });
  }, [toast]);

  useEffect(load, [load]);

  const close = async (r) => {
    if (!window.confirm(`Close ${r.name}’s request without booking?`)) return;
    try {
      await api.post(`/api/booking-requests/${r.reference}/close`);
      load();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  return (
    <>
      <Topbar title="Website requests" sub="Appointment requests sent from the doctor’s website" />
      <div className="content">
        {data === null ? <Loading /> : !data.available ? (
          <div className="card"><Empty icon={Globe}>Website requests aren’t connected to this database.</Empty></div>
        ) : data.items.length === 0 ? (
          <div className="card"><Empty icon={Globe}>No open requests.</Empty></div>
        ) : (
          <div className="card">
            {data.items.map((r) => (
              <div key={r.reference} className="list-item" style={{ alignItems: 'flex-start' }}>
                <div className="grow">
                  <div className="title row" style={{ gap: 8 }}>
                    {r.name}
                    <span className="muted small" style={{ fontWeight: 500 }}>{r.age} y · {r.gender}</span>
                    {r.urgent && <span className="badge badge-danger"><AlertTriangle size={12} /> Urgent</span>}
                    <span className="badge badge-kind">{r.reference}</span>
                  </div>
                  <div className="meta" style={{ marginTop: 4 }}>
                    <Phone size={12} style={{ verticalAlign: -1 }} /> {r.phone} ({r.contactMethod === 'whatsapp' ? 'WhatsApp' : 'call'}) · {r.bodyArea}{r.side ? ` (${r.side})` : ''}
                    {r.painScore != null && ` · pain ${r.painScore}/10`}
                  </div>
                  <div style={{ marginTop: 6 }}>{r.chiefComplaint}</div>
                  <div className="meta" style={{ marginTop: 4 }}>
                    Prefers {r.preferredDate ? formatDate(r.preferredDate) : 'any day'}, {TIME_LABELS[r.preferredTime] || r.preferredTime} · sent {formatDateTime(r.createdAt)}
                  </div>
                </div>
                <div className="stack-sm">
                  <button className="btn btn-sm btn-primary" onClick={() => setBooking(r)}><CalendarCheck size={14} /> Book</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => close(r)}><XCircle size={14} /> Close</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {booking && <ScheduleModal request={booking} onClose={() => setBooking(null)} onDone={() => { setBooking(null); toast('Appointment booked', 'success'); load(); }} />}
    </>
  );
}
