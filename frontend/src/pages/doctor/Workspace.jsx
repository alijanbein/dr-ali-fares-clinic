import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle, ArrowLeft, CheckCircle2, ClipboardList, FileText, History, Mic, Paperclip, Pill, Play, Plus,
  Printer, RotateCcw, Stethoscope, Trash2, Upload,
} from 'lucide-react';
import api, { errorMessage, withToken } from '../../api';
import { Topbar } from '../../components/Layout';
import DictationModal from '../../components/DictationModal';
import VisitSummary, { DEFAULT_TESTS, DEFAULT_TREATMENTS, SOAP_FIELDS, nameOf } from '../../components/VisitSummary';
import { Avatar, Empty, Field, Loading, Modal, useToast } from '../../components/ui';
import { formatDate, formatDateTime, patientMeta, patientName, todayIso } from '../../utils/format';

const EMPTY_RX = { name: '', dose: '', frequency: '', duration: '', instructions: '' };
const EDITABLE = ['diagnosis', 'notes', 'soapNote', 'diagnostics', 'treatments', 'prescriptions', 'followUpDate', 'transcript', 'audioFilename'];

function pickEditable(v) {
  const out = {};
  for (const k of EDITABLE) out[k] = v[k];
  out.soapNote = { ...(v.soapNote || {}) };
  return out;
}

/** Merges an AI-structured dictation into the visit without throwing away
 * what the doctor already typed: new text wins where the dictation said
 * something, tests/treatments are added, not replaced. */
function mergeDictation(form, data) {
  const s = data.structured || {};
  const soap = { ...form.soapNote };
  for (const f of SOAP_FIELDS) if (s.soap?.[f.id]) soap[f.id] = s.soap[f.id];

  const diagnostics = [...form.diagnostics];
  for (const t of s.diagnostic_tests || []) {
    if (!diagnostics.some((d) => d.type === t)) diagnostics.push({ type: t, status: 'ordered', result: '' });
  }

  const treatments = [...form.treatments];
  for (const t of s.treatments || []) {
    const i = treatments.findIndex((x) => x.type === t.type);
    const entry = { type: t.type, duration: t.duration || '', details: t.details || '', followUpDate: t.followUpDate || '' };
    if (i === -1) treatments.push(entry);
    else treatments[i] = { ...treatments[i], ...Object.fromEntries(Object.entries(entry).filter(([, v]) => v)) };
  }

  const dates = treatments.map((t) => t.followUpDate).filter((d) => d && d > todayIso()).sort();
  return {
    ...form,
    diagnosis: s.diagnosis || form.diagnosis,
    notes: form.notes || '',
    soapNote: soap,
    diagnostics,
    treatments,
    followUpDate: form.followUpDate || dates[0] || null,
    transcript: [form.transcript, data.text].filter(Boolean).join('\n\n'),
    audioFilename: data.audioFilename || form.audioFilename,
  };
}

function Intake({ intake }) {
  if (!intake) return null;
  const flags = Array.isArray(intake.redFlags) ? intake.redFlags.filter((f) => f && f !== 'none') : [];
  return (
    <div className="card">
      <div className="card-head"><h3><ClipboardList size={16} /> Pre-visit questionnaire</h3>{intake.urgent && <span className="badge badge-danger">Urgent</span>}</div>
      <div className="card-body">
        <dl className="kv">
          <dt>Area</dt><dd>{intake.bodyArea}{intake.side ? ` (${intake.side})` : ''}</dd>
          <dt>Complaint</dt><dd>{intake.chiefComplaint}</dd>
          <dt>Onset</dt><dd>{(intake.onset || '').replaceAll('_', ' ')}</dd>
          <dt>Cause</dt><dd>{intake.mechanism}</dd>
          {intake.painScore != null && <><dt>Pain</dt><dd>{intake.painScore}/10</dd></>}
          {intake.promName && <><dt>{intake.promName}</dt><dd>{intake.finalScore ?? '—'}{intake.interpretation?.label ? ` · ${intake.interpretation.label}` : ''}</dd></>}
          {intake.history && <><dt>History</dt><dd>{intake.history}</dd></>}
          {intake.notes && <><dt>Notes</dt><dd>{intake.notes}</dd></>}
        </dl>
        {flags.length > 0 && <div className="allergy mt"><AlertTriangle size={15} /> Red flags: {flags.join(', ').replaceAll('_', ' ')}</div>}
      </div>
    </div>
  );
}

export default function Workspace() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const apptId = params.get('appt');
  const navigate = useNavigate();
  const toast = useToast();

  const [record, setRecord] = useState(null);
  const [options, setOptions] = useState({ diagnosticTests: DEFAULT_TESTS, treatmentOptions: DEFAULT_TREATMENTS });
  const [visit, setVisit] = useState(null);
  const [form, setForm] = useState(null);
  const [saveState, setSaveState] = useState('saved');
  const [dictating, setDictating] = useState(false);
  const [viewVisit, setViewVisit] = useState(null);
  const [showComplete, setShowComplete] = useState(false);
  const [bookFollowUp, setBookFollowUp] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const fileRef = useRef(null);
  const dirtyRef = useRef(false);
  const formRef = useRef(null);
  formRef.current = form;

  const loadRecord = useCallback(() => api.get(`/api/patients/${id}/record`).then((r) => { setRecord(r.data); return r.data; }), [id]);

  const openVisit = (v) => { setVisit(v); setForm(pickEditable(v)); dirtyRef.current = false; setSaveState('saved'); };

  const startVisit = useCallback(async (appointmentId) => {
    try {
      const { data } = await api.post('/api/visits/start', { patient_id: id, appointment_id: appointmentId || null });
      openVisit(data);
      loadRecord();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  }, [id, loadRecord, toast]);

  useEffect(() => {
    setRecord(null); setVisit(null); setForm(null);
    api.get('/api/options').then((r) => setOptions(r.data)).catch(() => {});
    loadRecord()
      .then((rec) => {
        // Coming from the queue → open the visit. Otherwise resume today's
        // unfinished visit if there is one, else just show the record.
        const draft = rec.visits.find((v) => v.status === 'draft' && v.date === todayIso());
        if (apptId) startVisit(apptId);
        else if (draft) openVisit(draft);
      })
      .catch((err) => { toast(errorMessage(err), 'error'); navigate('/d/queue'); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, apptId]);

  const save = useCallback(async () => {
    if (!visit || !formRef.current) return null;
    setSaveState('saving');
    dirtyRef.current = false;
    try {
      const { data } = await api.put(`/api/visits/${visit.id}`, formRef.current);
      setVisit(data);
      setSaveState(dirtyRef.current ? 'dirty' : 'saved');
      return data;
    } catch (err) {
      dirtyRef.current = true;
      setSaveState('error');
      toast(errorMessage(err, 'Could not save'), 'error');
      return null;
    }
  }, [visit, toast]);

  // Autosave two seconds after the last change.
  useEffect(() => {
    if (saveState !== 'dirty') return undefined;
    const t = setTimeout(save, 2000);
    return () => clearTimeout(t);
  }, [form, saveState, save]);

  const update = (patch) => {
    setForm((f) => ({ ...f, ...(typeof patch === 'function' ? patch(f) : patch) }));
    dirtyRef.current = true;
    setSaveState('dirty');
  };
  const setSoap = (k, v) => update((f) => ({ soapNote: { ...f.soapNote, [k]: v } }));
  const setListItem = (key, i, patch) => update((f) => ({ [key]: f[key].map((x, j) => (j === i ? { ...x, ...patch } : x)) }));
  const removeListItem = (key, i) => update((f) => ({ [key]: f[key].filter((_, j) => j !== i) }));

  const toggleTest = (testId) => update((f) => ({
    diagnostics: f.diagnostics.some((d) => d.type === testId)
      ? f.diagnostics.filter((d) => d.type !== testId)
      : [...f.diagnostics, { type: testId, status: 'ordered', result: '' }],
  }));

  const onDictation = (data) => {
    setDictating(false);
    update((f) => mergeDictation(f, data));
    toast(data.structured?.ai_structured ? 'Dictation added to the visit' : 'Transcribed — AI structuring was unavailable, please review', data.structured?.ai_structured ? 'success' : 'error');
  };

  const complete = async () => {
    const saved = await save();
    if (!saved) return;
    try {
      const { data } = await api.post(`/api/visits/${visit.id}/complete`, { bookFollowUp });
      setShowComplete(false);
      toast(data.followUpAppointmentId ? `Visit completed · follow-up booked for ${formatDate(data.followUpDate)}` : 'Visit completed', 'success');
      navigate('/d/queue');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const discard = async () => {
    if (!window.confirm('Discard this unfinished visit? The patient goes back to the waiting line.')) return;
    try {
      await api.delete(`/api/visits/${visit.id}`);
      navigate('/d/queue');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const reopen = async (v) => {
    try {
      const { data } = await api.post(`/api/visits/${v.id}/reopen`);
      setViewVisit(null);
      openVisit(data);
      loadRecord();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    if (visit) fd.append('visit_id', visit.id);
    try {
      await api.post(`/api/patients/${id}/documents`, fd);
      await loadRecord();
      toast('File attached', 'success');
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setUploading(false);
    }
  };

  const deleteDoc = async (doc) => {
    if (!window.confirm(`Delete ${doc.originalName}?`)) return;
    try {
      await api.delete(`/api/documents/${doc.id}`);
      loadRecord();
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };

  const printVisit = async (v) => {
    if (visit && v.id === visit.id && saveState !== 'saved') await save();
    window.open(`/d/visits/${v.id}/print`, '_blank');
  };

  const intake = useMemo(() => {
    if (!record) return null;
    const withIntake = record.appointments.filter((a) => a.intake);
    return (withIntake.find((a) => a.id === (visit?.appointmentId || apptId)) || withIntake[0])?.intake || null;
  }, [record, visit, apptId]);

  if (!record) return <><Topbar title="Patient" /><div className="content"><Loading /></div></>;
  const p = record.patient;
  const pastVisits = record.visits.filter((v) => !visit || v.id !== visit.id);
  const tests = options.diagnosticTests;
  const treatOpts = options.treatmentOptions;

  return (
    <>
      <Topbar title={patientName(p)} sub={patientMeta(p)}>
        <button className="btn btn-ghost" onClick={() => navigate('/d/queue')}><ArrowLeft size={16} /> Queue</button>
        {!visit && <button className="btn btn-primary" onClick={() => startVisit(null)}><Stethoscope size={16} /> Start visit</button>}
      </Topbar>

      <div className="content">
        <div className="ws">
          {/* ── Left: the patient's record ── */}
          <aside className="ws-side">
            <div className="card card-pad stack-sm">
              <div className="patient-head">
                <Avatar patient={p} size="lg" />
                <div>
                  <h2>{patientName(p)}</h2>
                  <div className="muted small" style={{ fontFamily: 'ui-monospace, monospace' }}>{p.fileNumber}</div>
                  {p.isQuick && <span className="badge badge-quick" style={{ marginTop: 4 }}>Quick file — secretary will add details</span>}
                </div>
              </div>
              {p.allergies && <div className="allergy"><AlertTriangle size={15} /> Allergies: {p.allergies}</div>}
              <dl className="kv mt">
                <dt>Age</dt><dd>{p.age ?? '—'}</dd>
                <dt>Gender</dt><dd>{p.gender || '—'}</dd>
                <dt>Phone</dt><dd>{p.phone || '—'}</dd>
                <dt>Blood type</dt><dd>{p.bloodType || '—'}</dd>
                {p.chronicConditions && <><dt>Conditions</dt><dd>{p.chronicConditions}</dd></>}
                {p.notes && <><dt>Notes</dt><dd>{p.notes}</dd></>}
              </dl>
            </div>

            <Intake intake={intake} />

            <div className="card">
              <div className="card-head"><h3><History size={16} /> Previous visits</h3><span className="muted small">{pastVisits.length}</span></div>
              {pastVisits.length === 0 ? <Empty>First visit.</Empty> : pastVisits.map((v) => (
                <div key={v.id} className="timeline-item" onClick={() => setViewVisit(v)}>
                  <div className="row"><strong>{formatDate(v.date)}</strong><span className="spacer" />{v.status === 'draft' && <span className="badge badge-draft">Unfinished</span>}</div>
                  <div className="small" style={{ marginTop: 2 }}>{v.diagnosis || <span className="muted">No diagnosis recorded</span>}</div>
                  {v.prescriptions?.length > 0 && <div className="muted small">{v.prescriptions.map((m) => m.name).join(', ')}</div>}
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-head">
                <h3><Paperclip size={16} /> Files & imaging</h3>
                <button className="btn btn-sm btn-outline" onClick={() => fileRef.current?.click()} disabled={uploading}><Upload size={14} /> {uploading ? 'Uploading…' : 'Attach'}</button>
                <input ref={fileRef} type="file" accept="image/*,application/pdf" hidden onChange={upload} />
              </div>
              {record.documents.length === 0 ? <Empty>No files.</Empty> : record.documents.map((d) => (
                <div key={d.id} className="list-item">
                  <FileText size={18} className="muted" />
                  <div className="grow">
                    <a className="title" href={withToken(`/api/files/${d.filename}`)} target="_blank" rel="noreferrer" style={{ display: 'block' }}>{d.originalName}</a>
                    <div className="meta">{formatDateTime(d.uploadedAt)}</div>
                  </div>
                  <button className="btn btn-ghost btn-icon btn-sm" onClick={() => deleteDoc(d)} aria-label="Delete file"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          </aside>

          {/* ── Right: today's visit ── */}
          <section>
            {!visit ? (
              <div className="card">
                <Empty icon={Stethoscope}>
                  <div style={{ marginBottom: 12 }}>No visit open for this patient.</div>
                  <button className="btn btn-primary" onClick={() => startVisit(null)}><Stethoscope size={16} /> Start visit</button>
                </Empty>
              </div>
            ) : (
              <div className="stack">
                {visit.status === 'completed' && (
                  <div className="alert alert-success">This visit was completed {formatDateTime(visit.completedAt)}. Changes are saved to it directly.</div>
                )}

                <div className="dictate-hero">
                  <Mic size={30} />
                  <div className="grow">
                    <h3>Dictate the visit</h3>
                    <p>Speak the findings, tests and plan in one take — the note fills itself in for you to review.</p>
                  </div>
                  <button className="btn btn-lg" onClick={() => setDictating(true)}><Mic size={17} /> Start dictation</button>
                </div>

                <div className="card">
                  <div className="card-head"><h3><Stethoscope size={16} /> Clinical note</h3></div>
                  <div className="card-body stack">
                    <Field label="Diagnosis">
                      <input className="input" value={form.diagnosis || ''} onChange={(e) => update({ diagnosis: e.target.value })} placeholder="e.g. Osteoarthritis grade 3, right knee" style={{ fontWeight: 600 }} />
                    </Field>
                    <div className="soap-grid">
                      {SOAP_FIELDS.map((f) => (
                        <Field key={f.id} label={f.label}>
                          <textarea className="textarea" rows={3} value={form.soapNote[f.id] || ''} onChange={(e) => setSoap(f.id, e.target.value)} />
                        </Field>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="card-head"><h3>Investigations</h3><span className="muted small">Tap to request · add the result when it’s back</span></div>
                  <div className="card-body stack">
                    <div className="row-wrap">
                      {tests.map((t) => (
                        <button key={t.id} className={`chip-toggle ${form.diagnostics.some((d) => d.type === t.id) ? 'on' : ''}`} onClick={() => toggleTest(t.id)}>{t.name}</button>
                      ))}
                    </div>
                    {form.diagnostics.map((d, i) => (
                      <div key={d.type} className="row">
                        <strong style={{ width: 130, flexShrink: 0 }}>{nameOf(tests, d.type)}</strong>
                        <input className="input" placeholder="Result (leave empty while pending)" value={d.result || ''} onChange={(e) => setListItem('diagnostics', i, { result: e.target.value, status: e.target.value ? 'resulted' : 'ordered' })} />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div className="card-head">
                    <h3>Treatment plan</h3>
                    <button className="btn btn-sm btn-outline" onClick={() => update((f) => ({ treatments: [...f.treatments, { type: treatOpts[0]?.id || 'medication', duration: '', details: '', followUpDate: '' }] }))}><Plus size={14} /> Add</button>
                  </div>
                  <div className="card-body stack-sm">
                    {form.treatments.length === 0 && <div className="muted small">No treatment yet.</div>}
                    {form.treatments.map((t, i) => (
                      <div key={i} className="entry treat-grid">
                        <Field label="Treatment">
                          <select className="select" value={t.type} onChange={(e) => setListItem('treatments', i, { type: e.target.value })}>
                            {treatOpts.map((o) => <option key={o.id} value={o.id}>{o.id === 'surgery' ? 'Surgery (referral)' : o.name}</option>)}
                          </select>
                        </Field>
                        <Field label="Duration"><input className="input" value={t.duration || ''} onChange={(e) => setListItem('treatments', i, { duration: e.target.value })} placeholder="6 weeks" /></Field>
                        <Field label="Review on"><input className="input" type="date" value={t.followUpDate || ''} onChange={(e) => setListItem('treatments', i, { followUpDate: e.target.value })} /></Field>
                        <Field label="Details"><input className="input" value={t.details || ''} onChange={(e) => setListItem('treatments', i, { details: e.target.value })} /></Field>
                        <button className="btn btn-ghost btn-icon" onClick={() => removeListItem('treatments', i)} aria-label="Remove"><Trash2 size={15} /></button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div className="card-head">
                    <h3><Pill size={16} /> Prescription</h3>
                    <button className="btn btn-sm btn-outline" onClick={() => update((f) => ({ prescriptions: [...f.prescriptions, { ...EMPTY_RX }] }))}><Plus size={14} /> Add medication</button>
                  </div>
                  <div className="card-body stack-sm">
                    {form.prescriptions.length === 0 && <div className="muted small">No medication prescribed.</div>}
                    {form.prescriptions.map((m, i) => (
                      <div key={i} className="entry entry-grid">
                        <Field label="Medication"><input className="input" value={m.name} onChange={(e) => setListItem('prescriptions', i, { name: e.target.value })} placeholder="Ibuprofen" autoFocus={!m.name} /></Field>
                        <Field label="Dose"><input className="input" value={m.dose} onChange={(e) => setListItem('prescriptions', i, { dose: e.target.value })} placeholder="400 mg" /></Field>
                        <Field label="How often"><input className="input" value={m.frequency} onChange={(e) => setListItem('prescriptions', i, { frequency: e.target.value })} placeholder="3× daily" /></Field>
                        <Field label="Duration · instructions">
                          <div className="row" style={{ gap: 6 }}>
                            <input className="input" value={m.duration} onChange={(e) => setListItem('prescriptions', i, { duration: e.target.value })} placeholder="7 days" style={{ width: 90 }} />
                            <input className="input" value={m.instructions} onChange={(e) => setListItem('prescriptions', i, { instructions: e.target.value })} placeholder="After food" />
                          </div>
                        </Field>
                        <button className="btn btn-ghost btn-icon" onClick={() => removeListItem('prescriptions', i)} aria-label="Remove"><Trash2 size={15} /></button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div className="card-body grid-2">
                    <Field label="Next visit (follow-up)">
                      <input className="input" type="date" value={form.followUpDate || ''} min={todayIso()} onChange={(e) => update({ followUpDate: e.target.value || null })} />
                    </Field>
                    <Field label="Private notes">
                      <input className="input" value={form.notes || ''} onChange={(e) => update({ notes: e.target.value })} />
                    </Field>
                  </div>
                  {(form.transcript || form.audioFilename) && (
                    <div className="card-body" style={{ borderTop: '1px solid var(--border)' }}>
                      <button className="btn btn-sm btn-ghost" onClick={() => setShowTranscript(!showTranscript)}><Play size={14} /> {showTranscript ? 'Hide' : 'Show'} dictation recording & transcript</button>
                      {showTranscript && (
                        <div className="stack-sm mt">
                          {form.audioFilename && <audio controls src={withToken(`/api/audio/${form.audioFilename}`)} style={{ width: '100%' }} />}
                          <div className="caption" style={{ whiteSpace: 'pre-wrap' }}>{form.transcript}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="savebar">
                  <span className="small muted">
                    {{ saved: 'All changes saved', dirty: 'Unsaved changes…', saving: 'Saving…', error: 'Not saved — check the connection' }[saveState]}
                  </span>
                  <span className="spacer" />
                  {visit.status === 'draft' && !visit.completedAt && <button className="btn btn-ghost" onClick={discard}><Trash2 size={15} /> Discard</button>}
                  <button className="btn btn-outline" onClick={() => printVisit(visit)}><Printer size={15} /> Print</button>
                  {visit.status === 'draft'
                    ? <button className="btn btn-success" onClick={() => setShowComplete(true)}><CheckCircle2 size={16} /> Complete visit</button>
                    : <button className="btn btn-primary" onClick={save}>Save</button>}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>

      {dictating && <DictationModal onResult={onDictation} onClose={() => setDictating(false)} />}

      {showComplete && (
        <Modal
          title="Complete visit"
          onClose={() => setShowComplete(false)}
          footer={<><button className="btn" onClick={() => setShowComplete(false)}>Back</button><button className="btn btn-success" onClick={complete}><CheckCircle2 size={16} /> Complete</button></>}
        >
          <div className="stack">
            {!form.diagnosis && <div className="alert alert-warn">No diagnosis recorded yet.</div>}
            {form.followUpDate ? (
              <label className="row" style={{ cursor: 'pointer' }}>
                <input type="checkbox" checked={bookFollowUp} onChange={(e) => setBookFollowUp(e.target.checked)} />
                Book the follow-up on <b>{formatDate(form.followUpDate)}</b> in the secretary’s calendar
              </label>
            ) : <div className="muted">No follow-up date set.</div>}
            <div className="muted small">The patient is marked as seen and leaves your queue.</div>
          </div>
        </Modal>
      )}

      {viewVisit && (
        <Modal
          size="lg"
          title={`Visit · ${formatDate(viewVisit.date)}`}
          onClose={() => setViewVisit(null)}
          footer={
            <>
              <button className="btn btn-outline" onClick={() => printVisit(viewVisit)}><Printer size={15} /> Print</button>
              <button className="btn btn-outline" onClick={() => reopen(viewVisit)}><RotateCcw size={15} /> {viewVisit.status === 'draft' ? 'Continue this visit' : 'Edit this visit'}</button>
              <button className="btn" onClick={() => setViewVisit(null)}>Close</button>
            </>
          }
        >
          <div className="muted small mb">By {viewVisit.doctor || '—'}</div>
          <VisitSummary visit={viewVisit} tests={tests} treatments={treatOpts} />
        </Modal>
      )}
    </>
  );
}
