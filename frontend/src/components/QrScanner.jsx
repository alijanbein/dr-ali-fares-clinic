import { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import api, { errorMessage } from '../api';
import { Modal } from './ui';

/**
 * Camera QR scan of a patient card ("CLINIC-PATIENT:<token>"). Calls
 * onFound(patient) once the code resolves to a file. A USB scanner doesn't
 * need this: it types into the search box instead.
 */
export default function QrScanner({ onFound, onClose }) {
  const [error, setError] = useState(null);
  const [manual, setManual] = useState('');
  const scannerRef = useRef(null);
  const handledRef = useRef(false);
  const elementId = 'qr-reader';

  const resolve = async (code) => {
    if (handledRef.current) return;
    handledRef.current = true;
    try {
      const { data } = await api.get('/api/patients/lookup', { params: { code } });
      onFound(data);
    } catch (err) {
      setError(errorMessage(err, 'This code does not match any patient'));
      setTimeout(() => { handledRef.current = false; }, 1500);
    }
  };

  useEffect(() => {
    if (!window.isSecureContext) {
      setError('The camera only works on https:// or localhost. Use the search box, a USB scanner, or type the file number below.');
      return undefined;
    }
    const scanner = new Html5Qrcode(elementId, { verbose: false });
    scannerRef.current = scanner;
    let started = false;
    scanner
      .start({ facingMode: 'environment' }, { fps: 10, qrbox: { width: 220, height: 220 } }, (text) => resolve(text), () => {})
      .then(() => { started = true; })
      .catch(() => setError('Could not open the camera. Allow camera access, or type the file number below.'));
    return () => {
      if (started) scanner.stop().then(() => scanner.clear()).catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Modal title="Scan patient card" onClose={onClose}>
      <div className="stack">
        <div id={elementId} className="qr-reader" />
        {error && <div className="alert alert-warn">{error}</div>}
        <form
          className="row"
          onSubmit={(e) => { e.preventDefault(); if (manual.trim()) { handledRef.current = false; resolve(manual.trim()); } }}
        >
          <input className="input" placeholder="Or type the file number, e.g. C-00012" value={manual} onChange={(e) => setManual(e.target.value)} />
          <button className="btn btn-primary" type="submit">Open</button>
        </form>
      </div>
    </Modal>
  );
}
