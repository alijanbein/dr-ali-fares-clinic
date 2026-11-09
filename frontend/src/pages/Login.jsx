import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Plus } from 'lucide-react';
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
      <form className="login-card stack" onSubmit={submit}>
        <div>
          <div className="brand-mark" style={{ display: 'grid', placeItems: 'center' }}><Plus size={26} color="#fff" strokeWidth={3} /></div>
          <h1>Clinic sign in</h1>
          <div className="muted" style={{ marginTop: 4 }}>Doctor and secretary accounts</div>
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
  );
}
