import { useEffect, useRef } from 'react';
import QRCode from 'qrcode';
import { Printer } from 'lucide-react';
import { patientName } from '../utils/format';
import { Modal } from './ui';

export const qrPayload = (patient) => `CLINIC-PATIENT:${patient.qrToken}`;

/** The patient's card: QR code + file number, printable. */
export default function PatientCard({ patient, onClose }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (canvasRef.current) QRCode.toCanvas(canvasRef.current, qrPayload(patient), { width: 130, margin: 1 }).catch(() => {});
  }, [patient]);

  const print = () => {
    const dataUrl = canvasRef.current.toDataURL('image/png');
    const w = window.open('', '_blank', 'width=480,height=360');
    if (!w) return;
    const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    w.document.write(`<!doctype html><html><head><title>Patient card</title><style>
      body{font-family:Inter,Arial,sans-serif;margin:24px}
      .c{width:86mm;height:54mm;border:1px solid #999;border-radius:10px;padding:12px;display:flex;gap:12px;align-items:center;box-sizing:border-box}
      .k{font-size:9px;font-weight:700;color:#2d6a5a;letter-spacing:.08em;text-transform:uppercase}
      .n{font-size:15px;font-weight:800;margin:4px 0}.f{font-family:monospace;font-size:14px;font-weight:700}
      .s{font-size:10px;color:#555;margin-top:6px}img{width:30mm;height:30mm}
    </style></head><body><div class="c"><img src="${dataUrl}"/><div>
      <div class="k">Clinic patient card</div><div class="n">${esc(patientName(patient))}</div>
      <div class="f">${esc(patient.fileNumber)}</div><div class="s">Show this card at every visit</div>
    </div></div><script>window.onload=()=>{window.print();}</script></body></html>`);
    w.document.close();
  };

  return (
    <Modal
      title="Patient card"
      onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Close</button><button className="btn btn-primary" onClick={print}><Printer size={16} /> Print card</button></>}
    >
      <div className="stack" style={{ alignItems: 'center' }}>
        <div className="id-card">
          <canvas ref={canvasRef} />
          <div>
            <div className="clinic">Clinic patient card</div>
            <div className="nm">{patientName(patient)}</div>
            <div className="fn">{patient.fileNumber}</div>
          </div>
        </div>
        <div className="muted small" style={{ textAlign: 'center' }}>
          The doctor scans this code to open the patientâ€™s file.
        </div>
      </div>
    </Modal>
  );
}
