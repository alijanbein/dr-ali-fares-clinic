import { useState } from 'react';
import { Field } from './ui';

export const EMPTY_PATIENT = {
  name: '', phone: '', dob: '', age: '', gender: '', address: '', bloodType: '', allergies: '', chronicConditions: '', notes: '',
};

export function toPayload(form) {
  const out = {};
  for (const [k, v] of Object.entries(form)) {
    if (k === 'age') out.age = v === '' || v == null ? null : Number(v);
    else out[k] = typeof v === 'string' ? v.trim() : v;
  }
  return out;
}

export function fromPatient(p) {
  const out = { ...EMPTY_PATIENT };
  for (const k of Object.keys(out)) out[k] = p?.[k] ?? '';
  return out;
}

/** Controlled demographics form, shared by "new patient" and "edit file". */
export default function PatientForm({ value, onChange, autoFocus }) {
  const [form, setForm] = [value, onChange];
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="grid-2">
      <Field label="Full name *" className="span-2">
        <input className="input" value={form.name} onChange={set('name')} autoFocus={autoFocus} placeholder="First and last name" />
      </Field>
      <Field label="Phone">
        <input className="input" value={form.phone} onChange={set('phone')} placeholder="07X XXX XXXX" inputMode="tel" />
      </Field>
      <Field label="Gender">
        <select className="select" value={form.gender} onChange={set('gender')}>
          <option value="">—</option>
          <option>Male</option>
          <option>Female</option>
        </select>
      </Field>
      <Field label="Date of birth">
        <input className="input" type="date" value={form.dob} onChange={set('dob')} />
      </Field>
      <Field label="Age (if no date of birth)">
        <input className="input" type="number" min="0" max="120" value={form.age} onChange={set('age')} disabled={!!form.dob} />
      </Field>
      <Field label="Blood type">
        <select className="select" value={form.bloodType} onChange={set('bloodType')}>
          <option value="">—</option>
          {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((b) => <option key={b}>{b}</option>)}
        </select>
      </Field>
      <Field label="Allergies">
        <input className="input" value={form.allergies} onChange={set('allergies')} placeholder="e.g. Penicillin — leave empty if none" />
      </Field>
      <Field label="Address" className="span-2">
        <input className="input" value={form.address} onChange={set('address')} />
      </Field>
      <Field label="Chronic conditions / medical history" className="span-2">
        <textarea className="textarea" rows={2} value={form.chronicConditions} onChange={set('chronicConditions')} placeholder="Diabetes, hypertension, previous surgeries…" />
      </Field>
      <Field label="Notes" className="span-2">
        <textarea className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
      </Field>
    </div>
  );
}

export function usePatientForm(initial) {
  return useState(initial || EMPTY_PATIENT);
}
