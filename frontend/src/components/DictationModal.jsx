import { useEffect, useRef, useState } from 'react';
import { Mic, Square } from 'lucide-react';
import { useDictation } from '../hooks/useDictation';
import { Modal } from './ui';

const BARS = 32;
const LANG = { en: 'English', ar: 'Arabic', fr: 'French', mixed: 'Arabic + English' };

function Waveform({ analyserRef, active }) {
  const [levels, setLevels] = useState(() => Array(BARS).fill(4));
  useEffect(() => {
    if (!active) return undefined;
    let raf;
    const tick = () => {
      const analyser = analyserRef.current;
      if (analyser) {
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        setLevels(Array.from({ length: BARS }, (_, i) => Math.max(4, (data[i] / 255) * 64)));
      }
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [active, analyserRef]);
  return <div className="wave">{levels.map((h, i) => <span key={i} style={{ height: h }} />)}</div>;
}

const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

/** Record → live caption → AI structuring. Calls onResult(dictationResponse). */
export default function DictationModal({ onResult, onClose }) {
  const [error, setError] = useState(null);
  const d = useDictation({ onResult, onError: setError });
  const startedRef = useRef(false);

  useEffect(() => {
    if (!startedRef.current) { startedRef.current = true; d.start(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = () => { d.cancel(); onClose(); };

  return (
    <Modal
      title="Dictate the visit"
      onClose={close}
      footer={
        <>
          <button className="btn" onClick={close}>Cancel</button>
          {d.isRecording && <button className="btn btn-danger" onClick={d.stop}><Square size={15} /> Stop &amp; process</button>}
          {!d.isRecording && !d.isProcessing && <button className="btn btn-primary" onClick={() => { setError(null); d.start(); }}><Mic size={15} /> Record again</button>}
        </>
      }
    >
      <div className="stack">
        {d.isRecording && (
          <>
            <div className="row">
              <div className="rec-dot" />
              <strong>Recording</strong>
              <span className="muted" style={{ fontVariantNumeric: 'tabular-nums' }}>{mmss(d.elapsed)}</span>
              <span className="spacer" />
              {d.language && <span className="badge badge-kind">{LANG[d.language] || d.language}</span>}
            </div>
            <Waveform analyserRef={d.analyserRef} active={d.isRecording} />
            <div className="caption">{d.caption || <span className="muted">Live caption appears here as you speak…</span>}</div>
            <div className="alert alert-info small">
              Speak naturally. Use the cues <b>“Diagnosis…”</b>, <b>“Diagnostics…”</b> and <b>“Treatment plan…”</b> (Arabic and French work too).
              Mention medications with dose and duration, and say <b>“follow-up in 3 weeks”</b> to set the next visit.
            </div>
          </>
        )}
        {d.isProcessing && (
          <div className="empty">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Transcribing and organising the note…
          </div>
        )}
        {error && <div className="alert alert-error">{error}</div>}
      </div>
    </Modal>
  );
}
