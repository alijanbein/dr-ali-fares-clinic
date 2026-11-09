import { useState } from 'react';
import { UserPlus, X } from 'lucide-react';
import api, { errorMessage } from '../api';
import { patientMeta, patientName, todayIso } from '../utils/format';
import PatientForm, { EMPTY_PATIENT, toPayload } from './PatientForm';
import PatientSearch from './PatientSearch';
import { Avatar, Field, Modal } from './ui';

/**
 * Book an appointment for an existing file or a brand-new patient.
 * `patient` presets the file (from the patient page); `appointment` edits /
 * reschedules an existing one.
 */
export default function AppointmentModal({ patient: presetPatient, appointment, defaultDate, onClose, onSaved }) {
  const editing = !!appointment;
  const [patient, setPatient] = useState(presetPatient || appointment?.patient || null);
  const [creating, setCreating] = useState(false);
  const [newPatient, setNewPatient] = useState(EMPTY_PATIENT);
  const [date, setDate] = useState(appointment?.date || defaultDate || todayIso());
  const [time, setTime] = useState(appointment?.time || '');
  const [kind, setKind] = useState(appointment?.kind || 'scheduled');
  const [reason, setReason] = useState(appointment?.reason || '');
  const [checkIn, setCheckIn] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const isToday = date === todayIso();

  const save = async () => {
    setError(null);
    if (!patient && !creating) { setError('Choose a patient or add a new one'); return; }
    if (creating && !newPatient.name.trim()) { setError('The new patient’s name is required'); return; }
    setBusy(true);
    try {
      if (editing) {
        const { data } = await api.patch(`/api/appointments/${appointment.id}`, { date, time: time || null, reason });
        onSaved(data);
        return;
      }
      let target = patient;
      if (creating) target = (await api.post('/api/patients', toPayload(newPatient))).data;
      const { data } = await api.post('/api/appointments', {
        patient_id: target.id, date, time: time || null, kind, reason, checkIn: isToday && checkIn,
      });
      onSaved(data, target);
    } catch (err) {
      setError(errorMessage(err, 'Could not save the appointment'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      size="lg"
      title={editing ? 'Edit appointment' : 'New appointment'}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Book appointment'}</button>
        </>
      }
    >
      <div className="stack">
        {error && <div className="alert alert-error">{error}</div>}

        <div className="stack-sm">
          <div className="row">
            <strong>Patient</strong>
            <span className="spacer" />
            {!editing && !presetPatient && !patient && (
              <button className="btn btn-sm btn-outline" onClick={() => setCreating(!creating)}>
                {creating ? 'Search existing instead' : <><UserPlus size={15} /> New patient</>}
              </button>
            )}
          </div>
          {patient ? (
            <div className="list-item card" style={{ borderRadius: 12 }}>
              <Avatar patient={patient} />
              <div className="grow">
                <div className="title">{patientName(patient)}</div>
                <div className="meta">{patientMeta(patient)}</div>
              </div>
              {!editing && !presetPatient && (
                <button className="btn btn-ghost btn-icon" onClick={() => setPatient(null)} aria-label="Change patient"><X size={16} /></button>
              )}
            </div>
          ) : creating ? (
            <div className="card card-pad"><PatientForm value={newPatient} onChange={setNewPatient} autoFocus /></div>
          ) : (
            <PatientSearch onSelect={setPatient} autoFocus />
          )}
        </div>

        <div className="grid-3">
          <Field label="Date">
            <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field label="Time">
            <input className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          </Field>
          <Field label="Type">
            <select className="select" value={kind} onChange={(e) => { setKind(e.target.value); if (e.target.value === 'walk_in') { setDate(todayIso()); setCheckIn(true); } }} disabled={editing}>
              <option value="scheduled">Appointment</option>
              <option value="walk_in">Walk-in (here now)</option>
              <option value="follow_up">Follow-up</option>
            </select>
          </Field>
          <Field label="Reason for visit" className="span-3">
            <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Knee pain for 3 weeks" />
          </Field>
        </div>

        {!editing && isToday && (
          <label className="row" style={{ cursor: 'pointer' }}>
            <input type="checkbox" checked={checkIn} onChange={(e) => setCheckIn(e.target.checked)} />
            The patient is at the clinic now — add to the doctor’s waiting line
          </label>
        )}
      </div>
    </Modal>
  );
}
