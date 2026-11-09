import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './styles.css';
import { AuthProvider, useAuth } from './auth';
import { ToastProvider } from './components/ui';
import Layout from './components/Layout';
import Login from './pages/Login';
import Today from './pages/secretary/Today';
import Patients from './pages/secretary/Patients';
import PatientFile from './pages/secretary/PatientFile';
import Requests from './pages/secretary/Requests';
import Queue from './pages/doctor/Queue';
import FindPatient from './pages/doctor/FindPatient';
import Workspace from './pages/doctor/Workspace';
import VisitPrint from './pages/doctor/VisitPrint';

function home(user) {
  if (!user) return '/login';
  return user.role === 'doctor' ? '/d/queue' : '/s/today';
}

function RequireRole({ role, children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={home(user)} replace />;
  return children;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={home(user)} replace /> : <Login />} />

      <Route element={<RequireRole role="secretary"><Layout /></RequireRole>}>
        <Route path="/s/today" element={<Today />} />
        <Route path="/s/patients" element={<Patients />} />
        <Route path="/s/patients/:id" element={<PatientFile />} />
        <Route path="/s/requests" element={<Requests />} />
      </Route>

      <Route element={<RequireRole role="doctor"><Layout /></RequireRole>}>
        <Route path="/d/queue" element={<Queue />} />
        <Route path="/d/patients" element={<FindPatient />} />
        <Route path="/d/patients/:id" element={<Workspace />} />
      </Route>
      <Route path="/d/visits/:id/print" element={<RequireRole role="doctor"><VisitPrint /></RequireRole>} />

      <Route path="*" element={<Navigate to={home(user)} replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  // No StrictMode: its double-mounted effects would open the QR camera twice.
  <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
  </BrowserRouter>,
);
