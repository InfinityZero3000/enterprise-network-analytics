import { useState, useEffect } from 'react'
import { getGlobalStats } from './services/api'
import GraphExplorer from './components/GraphExplorer'
import AlertsRisk from './components/AlertsRisk'
import AIAssistant from './components/AIAssistant'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState({ total_nodes: 0, total_rels: 0 });

  useEffect(() => {
    getGlobalStats()
      .then(data => setStats(data))
      .catch(e => console.error("Failed fetching stats", e));
  }, []);

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          Analytics
        </div>
        
        <nav className="sidebar-nav">
          <a href="#" className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
            Dashboard
          </a>
          <a href="#" className={`nav-item ${activeTab === 'graph' ? 'active' : ''}`} onClick={() => setActiveTab('graph')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            Graph Explorer
          </a>
          <a href="#" className={`nav-item ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
            Alerts & Risk
          </a>
          <a href="#" className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Settings
          </a>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="header">
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
            {activeTab === 'dashboard' && 'Platform Overview'}
            {activeTab === 'graph' && 'Graph Visualization'}
            {activeTab === 'alerts' && 'Risk & Alerts'}
            {activeTab === 'settings' && 'System Settings'}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '0.5rem 1rem', background: 'var(--bg-base)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Status: </span>
              <span style={{ fontSize: '0.875rem', color: 'var(--accent-success)', fontWeight: 500 }}>Healthy</span>
            </div>
            <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--accent-primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
              A
            </div>
          </div>
        </header>

        <div className="page-content">
          {activeTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
                <div className="card">
                  <div className="card-title">Total Entities</div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-primary)' }}>{stats.total_nodes.toLocaleString()}</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--accent-success)', marginTop: '0.5rem' }}>Updated Live</div>
                </div>
                <div className="card">
                  <div className="card-title">Relationships</div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-secondary)' }}>{stats.total_rels.toLocaleString()}</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--accent-success)', marginTop: '0.5rem' }}>Updated Live</div>
                </div>
                <div className="card">
                  <div className="card-title">High Risk Nodes</div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-danger)' }}>124</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--accent-warning)', marginTop: '0.5rem' }}>Needs attention</div>
                </div>
                <div className="card">
                  <div className="card-title">API Requests Limit</div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>84%</div>
                  <div style={{ width: '100%', height: '6px', background: 'var(--bg-base)', borderRadius: '3px', marginTop: '1rem', overflow: 'hidden' }}>
                    <div style={{ width: '84%', height: '100%', background: 'var(--accent-primary)' }}></div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: '1.5rem', minHeight: '500px' }}>
                <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: 'var(--text-muted)' }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '1rem' }}><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
                  <p>System Architecture & Data Pipelines View</p>
                </div>
                <div>
                  <AIAssistant />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'graph' && (
            <GraphExplorer />
          )}

          {activeTab === 'alerts' && (
            <AlertsRisk />
          )}
        </div>
      </main>
    </div>
  )
}

export default App
