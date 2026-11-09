import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Stethoscope } from 'lucide-react';
import { CLINIC_NAME } from '../components/Layout';
import { useAuth } from '../auth';
import { errorMessage } from '../api';
import { Field } from '../components/ui';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password);
      navigate(user.role === 'doctor' ? '/d/queue' : '/s/today', { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not sign in'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <section className="login-art">
        <div className="brand" style={{ color: '#f6f2eb', padding: 0 }}>
          <div className="brand-mark"><Stethoscope size={19} color="var(--primary-dark)" strokeWidth={2.4} /></div>
          <div className="brand-title">{CLINIC_NAME}</div>
        </div>
        <div>
          <h2>Your patients, your clinic, one calm workspace.</h2>
          <p>Appointments at the front desk, the full record in the consulting room.</p>
        </div>
      </section>
      <div className="login-side">
      <form className="login-card stack" onSubmit={submit}>
        <div>
          <h1>Welcome back</h1>
          <div className="muted" style={{ marginTop: 4 }}>Sign in with your doctor or secretary account</div>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <Field label="Email">
          <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
        </Field>
        <Field label="Password">
          <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <button className="btn btn-primary btn-lg" disabled={busy}><LogIn size={17} /> {busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      </div>
    </div>
  );
}
