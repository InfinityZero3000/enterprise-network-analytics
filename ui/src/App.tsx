import { useState, useEffect, useRef } from 'react'
import { getGlobalStats, getFraudAlerts } from './services/api'
import GraphExplorer from './components/GraphExplorer'
import AlertsRisk from './components/AlertsRisk'
import AIAssistant from './components/AIAssistant'
import CrawlManager from './components/CrawlManager'
import Settings from './components/Settings'
import { translations, type Lang, getAlertDescription } from './i18n'
import './App.css'

type GraphNode = {
  id: string
  name: string
  group: number
}

type GraphLink = {
  source: string
  target: string
}

type FraudAlert = {
  entity_id: string
  entity_name: string
  alert_type: string
  level: number | string
  description: string
}

const DEFAULT_API_ROOT = 'http://localhost:8000';

const resolveApiRoot = () => {
  const raw = (localStorage.getItem('app-api-url') || '').trim();
  if (!raw) {
    return DEFAULT_API_ROOT;
  }
  return raw.replace(/\/+$/, '');
};

function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem('app-theme');
    return stored === 'light' ? 'light' : 'dark';
  });
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem('app-lang');
    return stored === 'vi' ? 'vi' : 'en';
  });
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState({ total_nodes: 0, total_rels: 0 });
  const [loading, setLoading] = useState(true);
  const [entityMix, setEntityMix] = useState({ companies: 0, persons: 0, addresses: 0 });
  const [topHubs, setTopHubs] = useState<Array<{ id: string; name: string; degree: number }>>([]);
  const [alertsPreview, setAlertsPreview] = useState<FraudAlert[]>([]);
  const [updatedAt, setUpdatedAt] = useState('');
  const [isQuickChatOpen, setIsQuickChatOpen] = useState(false);
  const [initialGraphSearch, setInitialGraphSearch] = useState('');
  const [investigationSeed, setInvestigationSeed] = useState<{ entityName: string; alertType: string } | null>(null);
  const [quickAiPrompt, setQuickAiPrompt] = useState('');
  const [quickAiAutoSend, setQuickAiAutoSend] = useState(false);
  const [quickChatWidth, setQuickChatWidth] = useState<number>(() => {
    const stored = localStorage.getItem('quick-chat-width');
    const parsed = stored ? Number(stored) : 420;
    return Number.isFinite(parsed) ? parsed : 420;
  });
  const [graphSummary, setGraphSummary] = useState<{ nodes: number; links: number; hubs: string[] }>({ nodes: 0, links: 0, hubs: [] });
  const [alertsSummary, setAlertsSummary] = useState<{ count: number; topTypes: string[] }>({ count: 0, topTypes: [] });
  const [graphFrameContext, setGraphFrameContext] = useState('');
  const resizingRef = useRef(false);

  useEffect(() => {
    const loadDashboard = async () => {
      setLoading(true);

      const fetchDashboardWithRoot = async (root: string) => {
        const [statsResult, networkResult, alertsResult] = await Promise.allSettled([
          getGlobalStats(),
          fetch(`${root}/api/v1/graph/network?limit=220`).then(res => res.json()),
          getFraudAlerts(8),
        ]);
        return { statsResult, networkResult, alertsResult };
      };

      const configuredRoot = resolveApiRoot();
      let { statsResult, networkResult, alertsResult } = await fetchDashboardWithRoot(configuredRoot);

      const allFailed =
        statsResult.status === 'rejected' &&
        networkResult.status === 'rejected' &&
        alertsResult.status === 'rejected';

      if (allFailed && configuredRoot !== DEFAULT_API_ROOT) {
        ({ statsResult, networkResult, alertsResult } = await fetchDashboardWithRoot(DEFAULT_API_ROOT));
      }

      if (statsResult.status === 'fulfilled') {
        setStats(statsResult.value);
      }

      if (networkResult.status === 'fulfilled' && networkResult.value?.nodes && networkResult.value?.links) {
        const nodes = networkResult.value.nodes as GraphNode[];
        const links = networkResult.value.links as GraphLink[];

        const companies = nodes.filter(n => n.group === 1).length;
        const persons = nodes.filter(n => n.group === 2).length;
        const addresses = nodes.filter(n => n.group === 3).length;
        setEntityMix({ companies, persons, addresses });

        const degreeMap = new Map<string, number>();
        for (const l of links) {
          const source = String(l.source);
          const target = String(l.target);
          degreeMap.set(source, (degreeMap.get(source) || 0) + 1);
          degreeMap.set(target, (degreeMap.get(target) || 0) + 1);
        }

        const hubs = nodes
          .map(node => ({
            id: node.id,
            name: node.name,
            degree: degreeMap.get(String(node.id)) || 0,
          }))
          .sort((a, b) => b.degree - a.degree)
          .slice(0, 6);

        setTopHubs(hubs);
      }

      if (alertsResult.status === 'fulfilled' && Array.isArray(alertsResult.value)) {
        setAlertsPreview(alertsResult.value.slice(0, 6));
      } else {
        setAlertsPreview([]);
      }

      setUpdatedAt(new Date().toLocaleTimeString(lang === 'vi' ? 'vi-VN' : 'en-US'));
      setLoading(false);
    };

    loadDashboard();
  }, [lang]);

  useEffect(() => {
    localStorage.setItem('app-lang', lang);
  }, [lang]);

  useEffect(() => {
    localStorage.setItem('app-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('quick-chat-width', String(quickChatWidth));
  }, [quickChatWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!resizingRef.current) return;
      const maxWidth = Math.min(760, window.innerWidth - 80);
      const minWidth = 320;
      const nextWidth = window.innerWidth - e.clientX;
      setQuickChatWidth(Math.max(minWidth, Math.min(maxWidth, nextWidth)));
    };

    const onMouseUp = () => {
      resizingRef.current = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const t = translations[lang];

  const totalEntities = stats.total_nodes || 0;
  const totalRelationships = stats.total_rels || 0;
  const avgDegree = totalEntities > 0 ? ((2 * totalRelationships) / totalEntities).toFixed(2) : '0.00';
  const riskCount = alertsPreview.length;
  const mixTotal = entityMix.companies + entityMix.persons + entityMix.addresses;
  const getMixPct = (value: number) => (mixTotal > 0 ? Math.round((value / mixTotal) * 100) : 0);

  const dashboardContext = `Dashboard snapshot: ${totalEntities.toLocaleString()} entities, ${totalRelationships.toLocaleString()} relationships, average degree ${avgDegree}, ${riskCount} priority alerts.`;
  const graphContext = `Graph view snapshot: ${graphSummary.nodes.toLocaleString()} nodes and ${graphSummary.links.toLocaleString()} links rendered. Top visible hubs: ${graphSummary.hubs.length > 0 ? graphSummary.hubs.join(', ') : 'not available yet'}.${graphFrameContext ? ` ${graphFrameContext}` : ''}`;
  const alertsContext = `Alerts view snapshot: ${alertsSummary.count} active alerts. Top alert types: ${alertsSummary.topTypes.length > 0 ? alertsSummary.topTypes.join(', ') : 'not available yet'}.`;
  const investigationPromptContext = quickAiPrompt ? `Suggested investigation question: ${quickAiPrompt}` : '';

  const currentPageContext =
    activeTab === 'graph'
      ? graphContext
      : activeTab === 'alerts'
        ? `${alertsContext}${investigationPromptContext ? ` ${investigationPromptContext}` : ''}`
        : activeTab === 'dashboard'
          ? dashboardContext
          : 'Settings view. Ask for system configuration guidance.';

  const startResizeQuickChat = () => {
    resizingRef.current = true;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          {t.appName}
        </div>
        
        <nav className="sidebar-nav">
          <a href="#" className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
            {t.navDashboard}
          </a>
          <a href="#" className={`nav-item ${activeTab === 'graph' ? 'active' : ''}`} onClick={() => setActiveTab('graph')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            {t.navGraph}
          </a>
          <a href="#" className={`nav-item ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
            {t.navAlerts}
          </a>
          <a href="#" className={`nav-item ${activeTab === 'crawl' ? 'active' : ''}`} onClick={() => setActiveTab('crawl')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-3.1-6.8"></path><path d="M21 3v6h-6"></path><path d="M12 7v5l3 3"></path></svg>
            {t.navCrawl}
          </a>
          <a href="#" className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            {t.navSettings}
          </a>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="header">
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
            {activeTab === 'dashboard' && t.tabDashboard}
            {activeTab === 'graph' && t.tabGraph}
            {activeTab === 'alerts' && t.tabAlerts}
            {activeTab === 'crawl' && t.tabCrawl}
            {activeTab === 'settings' && t.tabSettings}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-md)',
                padding: '0.45rem 0.75rem',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontWeight: 700,
                fontSize: '0.78rem'
              }}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-secondary)' }}><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-secondary)' }}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
              )}
              {theme.toUpperCase()}
            </button>
            <button
              onClick={() => setLang(lang === 'en' ? 'vi' : 'en')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-md)',
                padding: '0.45rem 0.75rem',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontWeight: 700,
                fontSize: '0.78rem'
              }}
              aria-label="Toggle language"
            >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-secondary)' }}>
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="2" y1="12" x2="22" y2="12"></line>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                </svg>
              {lang.toUpperCase()}
            </button>
            <div style={{ padding: '0.5rem 1rem', background: 'var(--bg-base)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.status}: </span>
              <span style={{ fontSize: '0.875rem', color: 'var(--accent-success)', fontWeight: 500 }}>{t.healthy}</span>
            </div>
          </div>
        </header>

        <div className="page-content">
          {activeTab === 'dashboard' && (
            <div className="dashboard-grid">
              <div className="card dashboard-hero">
                <div>
                  <div className="card-title" style={{ marginBottom: '0.4rem' }}>{t.heroTitle}</div>
                  <p style={{ color: 'var(--text-secondary)', margin: 0 }}>{t.heroSubtitle}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: 'var(--accent-success)', fontWeight: 600 }}>{loading ? t.syncing : t.liveReady}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{t.updatedAt}: {updatedAt || '--:--:--'}</div>
                </div>
              </div>

              <div className="kpi-grid">
                <div className="card kpi-card">
                  <div className="card-title">{t.totalEntities}</div>
                  <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>{totalEntities.toLocaleString()}</div>
                  <div className="kpi-meta">{t.entitiesMeta}</div>
                </div>
                <div className="card kpi-card">
                  <div className="card-title">{t.totalRelationships}</div>
                  <div className="kpi-value" style={{ color: '#22d3ee' }}>{totalRelationships.toLocaleString()}</div>
                  <div className="kpi-meta">{t.relMeta}</div>
                </div>
                <div className="card kpi-card">
                  <div className="card-title">{t.avgDegree}</div>
                  <div className="kpi-value" style={{ color: 'var(--accent-warning)' }}>{avgDegree}</div>
                  <div className="kpi-meta">{t.degreeMeta}</div>
                </div>
                <div className="card kpi-card">
                  <div className="card-title">{t.priorityAlerts}</div>
                  <div className="kpi-value" style={{ color: 'var(--accent-danger)' }}>{riskCount}</div>
                  <div className="kpi-meta">{t.alertsMeta}</div>
                </div>
              </div>

              <div className="dashboard-main-panels">
                <div className="card">
                  <div className="panel-header">
                    <h3 style={{ margin: 0 }}>{t.entityComposition}</h3>
                    <button className="mini-action" onClick={() => setActiveTab('graph')}>{t.openGraph}</button>
                  </div>
                  <div style={{ display: 'grid', gap: '0.85rem', marginTop: '1rem' }}>
                    <div>
                      <div className="mix-row"><span>{t.companies}</span><span>{entityMix.companies.toLocaleString()} ({getMixPct(entityMix.companies)}%)</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${getMixPct(entityMix.companies)}%`, background: 'var(--accent-primary)' }} /></div>
                    </div>
                    <div>
                      <div className="mix-row"><span>{t.persons}</span><span>{entityMix.persons.toLocaleString()} ({getMixPct(entityMix.persons)}%)</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${getMixPct(entityMix.persons)}%`, background: '#22d3ee' }} /></div>
                    </div>
                    <div>
                      <div className="mix-row"><span>{t.addresses}</span><span>{entityMix.addresses.toLocaleString()} ({getMixPct(entityMix.addresses)}%)</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${getMixPct(entityMix.addresses)}%`, background: 'var(--accent-warning)' }} /></div>
                    </div>
                  </div>

                  <div style={{ marginTop: '1.4rem' }}>
                    <h4 style={{ marginBottom: '0.7rem' }}>{t.topHubs}</h4>
                    <div className="hub-list">
                      {topHubs.length === 0 && <div className="empty-line">{t.noHubData}</div>}
                      {topHubs.map((hub, idx) => (
                        <div key={hub.id} className="hub-row">
                          <div className="hub-rank">#{idx + 1}</div>
                          <div className="hub-name">{hub.name}</div>
                          <div className="hub-degree">{hub.degree} {t.links}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="panel-header">
                    <h3 style={{ margin: 0 }}>{t.riskFeed}</h3>
                    <button className="mini-action" onClick={() => setActiveTab('alerts')}>{t.openAlerts}</button>
                  </div>
                  <div className="alerts-preview">
                    {alertsPreview.length === 0 && (
                      <div className="empty-line">{t.noAlertPreview}</div>
                    )}
                    {alertsPreview.map((alert, i) => (
                      <div key={`${alert.entity_id}-${i}`} className="alert-row">
                        <div>
                          <div className="alert-title">{alert.alert_type}: {alert.entity_name}</div>
                          <div className="alert-desc">{getAlertDescription(alert.description, lang)}</div>
                        </div>
                        <span className={`level-chip ${typeof alert.level === 'number' ? `level-${alert.level}` : String(alert.level).toLowerCase()}`}>{String(alert.level).toUpperCase()}</span>
                      </div>
                    ))}
                  </div>

                  <div className="quick-actions">
                    <button className="quick-btn" onClick={() => setActiveTab('graph')}>{t.exploreNetwork}</button>
                    <button className="quick-btn alt" onClick={() => setActiveTab('alerts')}>{t.runInvestigations}</button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'graph' && (
            <GraphExplorer
              key={theme}
              lang={lang}
              initialSearch={initialGraphSearch}
              investigationSeed={investigationSeed}
              onSummaryChange={setGraphSummary}
              onFrameContextChange={setGraphFrameContext}
              onExportFocusToAi={(prompt) => {
                setQuickAiPrompt(prompt);
                setQuickAiAutoSend(true);
                setIsQuickChatOpen(true);
              }}
            />
          )}

          {activeTab === 'alerts' && (
            <AlertsRisk 
              lang={lang} 
              onSummaryChange={setAlertsSummary} 
              onInvestigate={(entityName, alertType) => {
                setInitialGraphSearch(entityName);
                setInvestigationSeed({ entityName, alertType });
                setActiveTab('graph');
              }}
              onAskAiPrompt={(prompt) => {
                setQuickAiPrompt(prompt);
                setQuickAiAutoSend(false);
                setIsQuickChatOpen(true);
              }}
              onImportSnapshotToChat={(prompt) => {
                setQuickAiPrompt(prompt);
                setQuickAiAutoSend(true);
                setIsQuickChatOpen(true);
              }}
            />
          )}

          {activeTab === 'crawl' && (
            <CrawlManager lang={lang} />
          )}

          {activeTab === 'settings' && (
            <Settings lang={lang} />
          )}
        </div>
      </main>

      <button className="quick-chat-fab" onClick={() => setIsQuickChatOpen(true)} aria-label={t.openQuickChat}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>

      <div
        className={`quick-chat-drawer ${isQuickChatOpen ? 'open' : ''}`}
        style={{ width: `${Math.min(quickChatWidth, window.innerWidth)}px` }}
      >
        <div
          className="quick-chat-resizer"
          onMouseDown={startResizeQuickChat}
          title="Drag to resize"
        />
        <div className="quick-chat-topbar">
          <div style={{ fontWeight: 700 }}>{t.quickChat}</div>
          <button className="mini-action" onClick={() => setIsQuickChatOpen(false)}>{t.close}</button>
        </div>
        <div className="quick-chat-body">
          <AIAssistant
            lang={lang}
            pageContext={currentPageContext}
            compact
            seedPrompt={quickAiPrompt}
            autoSendSeed={quickAiAutoSend}
            onSeedConsumed={() => {
              setQuickAiPrompt('');
              setQuickAiAutoSend(false);
            }}
          />
        </div>
      </div>
    </div>
  )
}

export default App
