import { Routes, Route, NavLink } from 'react-router-dom'
import Overview from './pages/Overview'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Logs from './pages/Logs'
import System from './pages/System'

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Outreach Agent</h1>
        <nav>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/leads">Leads</NavLink>
          <NavLink to="/logs">Logs</NavLink>
          <NavLink to="/system">System</NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/leads/:id" element={<LeadDetail />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/system" element={<System />} />
        </Routes>
      </main>
    </div>
  )
}
