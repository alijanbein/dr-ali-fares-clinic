import { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';
import { KIND_LABELS, STATUS_LABELS, patientName } from '../utils/format';

/* ── Toasts ── */
const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-wrap">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

/* ── Modal ── */
export function Modal({ title, onClose, children, footer, size }) {
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${size === 'lg' ? 'modal-lg' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h3>{title}</h3>
          {onClose && (
            <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close"><X size={18} /></button>
          )}
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

/* ── Badges ── */
export function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

export function KindBadge({ kind }) {
  if (kind === 'scheduled') return null;
  return <span className={`badge ${kind === 'quick' ? 'badge-quick' : 'badge-kind'}`}>{KIND_LABELS[kind] || kind}</span>;
}

export function Avatar({ patient, size }) {
  const name = patient?.name || '';
  const initials = name ? name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() : '?';
  return <div className={`avatar ${patient?.isQuick ? 'avatar-quick' : ''} ${size === 'lg' ? 'avatar-lg' : ''}`}>{initials}</div>;
}

export function PatientTitle({ patient }) {
  return <>{patientName(patient)}</>;
}

export function Field({ label, children, className = '' }) {
  return (
    <div className={`field ${className}`}>
      {label && <label>{label}</label>}
      {children}
    </div>
  );
}

export function Empty({ icon: Icon, children }) {
  return (
    <div className="empty">
      {Icon && <Icon size={34} />}
      <div>{children}</div>
    </div>
  );
}

export function Loading() {
  return <div className="empty"><div className="spinner" style={{ margin: '0 auto' }} /></div>;
}
