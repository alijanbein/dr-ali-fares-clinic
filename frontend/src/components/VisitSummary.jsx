export const SOAP_FIELDS = [
  { id: 'chiefComplaint', label: 'Chief complaint' },
  { id: 'historyOfPresentIllness', label: 'History of present illness' },
  { id: 'pastMedicalHistory', label: 'Past medical history' },
  { id: 'examination', label: 'Examination' },
  { id: 'assessment', label: 'Assessment' },
  { id: 'plan', label: 'Plan' },
];

export const DEFAULT_TESTS = [
  { id: 'xray', name: 'X-Ray' }, { id: 'mri', name: 'MRI' }, { id: 'ct', name: 'CT Scan' },
  { id: 'lab', name: 'Laboratory Tests' }, { id: 'us', name: 'Ultrasound' },
];
export const DEFAULT_TREATMENTS = [
  { id: 'medication', name: 'Medication' }, { id: 'physio', name: 'Physiotherapy' },
  { id: 'injection', name: 'Injection Therapy' }, { id: 'rest', name: 'Rest & Monitoring' },
  { id: 'rehab', name: 'Long-term Rehab' }, { id: 'surgery', name: 'Surgery (referral)' },
];

export const nameOf = (list, id) => list.find((x) => x.id === id)?.name || id;

function Section({ title, children }) {
  if (!children || (Array.isArray(children) && !children.length)) return null;
  return (
    <div className="print-section">
      <h4>{title}</h4>
      {typeof children === 'string' ? <p>{children}</p> : children}
    </div>
  );
}

/** Read-only rendering of a visit, used in the history modal and for print. */
export default function VisitSummary({ visit, tests = DEFAULT_TESTS, treatments = DEFAULT_TREATMENTS }) {
  const soap = visit.soapNote || {};
  return (
    <div>
      <Section title="Diagnosis">{visit.diagnosis || ''}</Section>
      {SOAP_FIELDS.map((f) => <Section key={f.id} title={f.label}>{soap[f.id] || ''}</Section>)}
      {visit.diagnostics?.length > 0 && (
        <Section title="Investigations">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {visit.diagnostics.map((d, i) => (
              <li key={i}><b>{nameOf(tests, d.type)}</b>{d.result ? ` — ${d.result}` : ' — requested'}</li>
            ))}
          </ul>
        </Section>
      )}
      {visit.treatments?.length > 0 && (
        <Section title="Treatment plan">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {visit.treatments.map((t, i) => (
              <li key={i}>
                <b>{nameOf(treatments, t.type)}</b>
                {[t.duration, t.details].filter(Boolean).length > 0 && ` — ${[t.duration, t.details].filter(Boolean).join(', ')}`}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {visit.prescriptions?.length > 0 && (
        <Section title="Prescription">
          <table className="rx-table">
            <thead><tr><th>Medication</th><th>Dose</th><th>How often</th><th>Duration</th><th>Instructions</th></tr></thead>
            <tbody>
              {visit.prescriptions.map((m, i) => (
                <tr key={i}><td><b>{m.name}</b></td><td>{m.dose}</td><td>{m.frequency}</td><td>{m.duration}</td><td>{m.instructions}</td></tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      <Section title="Notes">{visit.notes || ''}</Section>
      {visit.followUpDate && <Section title="Follow-up">{visit.followUpDate}</Section>}
    </div>
  );
}
