import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Overview from './pages/Overview'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Analytics from './pages/Analytics'
import Logs from './pages/Logs'
import System from './pages/System'

// Icon components (using simple SVG for zero deps)
const Icons = {
  Home: () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>,
  Users: () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>,
  Chart: () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>,
  Terminal: () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>,
  Settings: () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
}

export default function App() {
  const location = useLocation();
  const [pageTitle, setPageTitle] = useState('Overview');

  useEffect(() => {
    const path = location.pathname;
    if (path === '/') setPageTitle('Mission Control');
    else if (path.startsWith('/leads')) setPageTitle('Lead Intelligence');
    else if (path.startsWith('/analytics')) setPageTitle('Performance Analytics');
    else if (path.startsWith('/logs')) setPageTitle('System Logs');
    else if (path.startsWith('/system')) setPageTitle('System Config');
  }, [location]);

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-mark">A</div>
          <span className="logo-text">Antigravity</span>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Icons.Home /> <span>Overview</span>
          </NavLink>
          <NavLink to="/leads" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Icons.Users /> <span>Leads</span>
          </NavLink>
          <NavLink to="/analytics" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Icons.Chart /> <span>Analytics</span>
          </NavLink>
          <NavLink to="/logs" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Icons.Terminal /> <span>Logs</span>
          </NavLink>
          <NavLink to="/system" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Icons.Settings /> <span>System</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="status-indicator online">
            <span className="dot"></span> System Online
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="top-bar">
          <h1 className="page-title">{pageTitle}</h1>
          <div className="top-bar-actions">
            <button className="icon-btn">
              <span className="notification-dot"></span>
              Bell
            </button>
            <div className="user-avatar">AD</div>
          </div>
        </header>

        <div className="content-scroll">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/system" element={<System />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
