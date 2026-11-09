import { NavLink, Outlet } from 'react-router-dom';
import { CalendarDays, Globe, ListOrdered, LogOut, Plus, Search, Users } from 'lucide-react';
import { useAuth } from '../auth';
import { Avatar } from './ui';

const NAV = {
  secretary: [
    { to: '/s/today', icon: CalendarDays, label: 'Appointments' },
    { to: '/s/patients', icon: Users, label: 'Patients' },
    { to: '/s/requests', icon: Globe, label: 'Website requests' },
  ],
  doctor: [
    { to: '/d/queue', icon: ListOrdered, label: 'Today’s queue' },
    { to: '/d/patients', icon: Search, label: 'Find patient' },
  ],
};

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Plus size={20} color="#fff" strokeWidth={3} /></div>
          <div>
            <div className="brand-title">Clinic</div>
            <div className="brand-sub">{user.role} portal</div>
          </div>
        </div>
        <nav className="nav">
          {NAV[user.role].map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} title={label}>
              <Icon size={18} /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user">
          <Avatar patient={{ name: user.name }} />
          <div className="who">
            <div>{user.name}</div>
            <div>{user.role}</div>
          </div>
          <button className="btn btn-ghost btn-icon" style={{ color: 'var(--sidebar-text)' }} onClick={logout} title="Sign out">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

export function Topbar({ title, sub, children }) {
  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {children && <div className="topbar-actions">{children}</div>}
    </header>
  );
}
