import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Lang } from '../i18n';
import { getAlertDescription, translations } from '../i18n';

type FraudAlert = {
  entity_id: string;
  entity_name: string;
  alert_type: string;
  level: number | string;
  description: string;
};

type EntityMix = {
  companies: number;
  persons: number;
  addresses: number;
};

type TopHub = {
  id: string;
  name: string;
  degree: number;
};

type CrawlHistoryRecord = {
  id: string;
  timestamp: string;
  mode: 'crawl' | 'etl';
  status: 'success' | 'warning' | 'failed';
  durationSeconds: number;
  totalErrors: number;
  sources: string[];
};

type Props = {
  lang: Lang;
  loading: boolean;
  updatedAt: string;
  totalEntities: number;
  totalRelationships: number;
  avgDegree: string;
  entityMix: EntityMix;
  topHubs: TopHub[];
  alertsPreview: FraudAlert[];
  onOpenGraph: () => void;
  onOpenAlerts: () => void;
  onOpenCrawl: () => void;
};

const HISTORY_STORAGE_KEY = 'crawl-dashboard-history';

const palette = ['#3b82f6', '#22d3ee', '#f59e0b'];

const clamp = (value: number, min = 0, max = 100): number => Math.max(min, Math.min(max, value));

const toRiskWeight = (level: number | string): number => {
  if (typeof level === 'number') {
    return level;
  }
  const normalized = String(level).toLowerCase();
  if (normalized.includes('critical') || normalized.includes('high')) return 3;
  if (normalized.includes('medium')) return 2;
  return 1;
};

const shortName = (value: string, max = 16): string => {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
};

export default function ExecutiveDashboard({
  lang,
  loading,
  updatedAt,
  totalEntities,
  totalRelationships,
  avgDegree,
  entityMix,
  topHubs,
  alertsPreview,
  onOpenGraph,
  onOpenAlerts,
  onOpenCrawl,
}: Props) {
  const t = translations[lang];

  const entityCompositionData = useMemo(
    () => [
      { name: t.companies, value: entityMix.companies },
      { name: t.persons, value: entityMix.persons },
      { name: t.addresses, value: entityMix.addresses },
    ],
    [entityMix.addresses, entityMix.companies, entityMix.persons, t.addresses, t.companies, t.persons],
  );

  const topHubChartData = useMemo(
    () =>
      topHubs.slice(0, 6).map((hub) => ({
        name: shortName(hub.name, 22),
        degree: hub.degree,
      })),
    [topHubs],
  );

  const alertTypeData = useMemo(() => {
    const grouped = new Map<string, number>();
    for (const alert of alertsPreview) {
      grouped.set(alert.alert_type, (grouped.get(alert.alert_type) || 0) + toRiskWeight(alert.level));
    }
    return Array.from(grouped.entries())
      .map(([name, score]) => ({ name: shortName(name, 20), score }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);
  }, [alertsPreview]);

  const crawlTrendData = useMemo(() => {
    try {
      const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];

      return (parsed as CrawlHistoryRecord[])
        .slice(0, 8)
        .reverse()
        .map((item, index) => ({
          run: `${index + 1}`,
          duration: Number(item.durationSeconds || 0),
          errors: Number(item.totalErrors || 0),
          success: item.status === 'success' ? 100 : item.status === 'warning' ? 65 : 25,
        }));
    } catch {
      return [];
    }
  }, []);

  const riskIndex = useMemo(() => {
    if (alertsPreview.length === 0) return 0;
    const total = alertsPreview.reduce((sum, item) => sum + toRiskWeight(item.level), 0);
    return Number((total / alertsPreview.length).toFixed(2));
  }, [alertsPreview]);

  const relationshipDensity = useMemo(() => {
    if (totalEntities <= 1) return 0;
    const maxUndirectedEdges = (totalEntities * (totalEntities - 1)) / 2;
    return Number(((totalRelationships / maxUndirectedEdges) * 100).toFixed(4));
  }, [totalEntities, totalRelationships]);

  const profileScores = useMemo(() => {
    const maxHubDegree = topHubs[0]?.degree || 0;
    const avgDegreeNum = Number.parseFloat(avgDegree || '0') || 0;
    const totalMix = Math.max(1, entityMix.companies + entityMix.persons + entityMix.addresses);

    const fraudWeightSum = alertsPreview.reduce((sum, item) => sum + toRiskWeight(item.level), 0);
    const fraudSignal = alertsPreview.length > 0
      ? clamp((fraudWeightSum / (alertsPreview.length * 3)) * 100)
      : 15;

    const pepAlerts = alertsPreview.filter((item) => {
      const joined = `${item.alert_type} ${item.description}`.toLowerCase();
      return joined.includes('pep') || joined.includes('sanction') || joined.includes('trừng phạt');
    }).length;
    const pepExposure = alertsPreview.length > 0
      ? clamp((pepAlerts / alertsPreview.length) * 100)
      : 10;

    const ownershipConcentration = clamp((entityMix.companies / totalMix) * 100);
    const ownership = clamp(ownershipConcentration * 0.65 + Math.min(35, avgDegreeNum * 3.2));

    const topology = clamp(Math.min(70, avgDegreeNum * 8) + Math.min(30, maxHubDegree * 0.6));

    const recentRuns = crawlTrendData.length;
    const errorBurden = recentRuns > 0
      ? crawlTrendData.reduce((sum, x) => sum + x.errors, 0) / recentRuns
      : 0;
    const activity = recentRuns > 0
      ? clamp(Math.min(100, recentRuns * 12) + Math.min(30, errorBurden * 10))
      : 20;

    return {
      topology: Number(topology.toFixed(1)),
      ownership: Number(ownership.toFixed(1)),
      fraudSignal: Number(fraudSignal.toFixed(1)),
      pepExposure: Number(pepExposure.toFixed(1)),
      activity: Number(activity.toFixed(1)),
    };
  }, [alertsPreview, avgDegree, crawlTrendData, entityMix.addresses, entityMix.companies, entityMix.persons, topHubs]);

  const weightedRiskScore = useMemo(() => {
    const weighted =
      profileScores.fraudSignal * 0.35 +
      profileScores.pepExposure * 0.25 +
      profileScores.ownership * 0.2 +
      profileScores.topology * 0.15 +
      profileScores.activity * 0.05;
    return Number(weighted.toFixed(1));
  }, [profileScores]);

  const riskLevel = useMemo(() => {
    if (weightedRiskScore >= 75) return { key: 'critical', color: '#ef4444', tone: 'danger' };
    if (weightedRiskScore >= 50) return { key: 'high', color: '#f97316', tone: 'warning' };
    if (weightedRiskScore >= 25) return { key: 'medium', color: '#f59e0b', tone: 'warning' };
    return { key: 'low', color: '#22c55e', tone: 'success' };
  }, [weightedRiskScore]);

  const radarData = useMemo(
    () => [
      { axis: 'Topology', value: profileScores.topology },
      { axis: 'Ownership', value: profileScores.ownership },
      { axis: 'Fraud Signal', value: profileScores.fraudSignal },
      { axis: 'PEP Exposure', value: profileScores.pepExposure },
      { axis: 'Activity', value: profileScores.activity },
    ],
    [profileScores.activity, profileScores.fraudSignal, profileScores.ownership, profileScores.pepExposure, profileScores.topology],
  );

  const riskRows = useMemo(
    () => [
      { key: 'Fraud Signal', weight: 35, score: profileScores.fraudSignal, desc: t.riskFraudSignalDesc },
      { key: 'PEP Exposure', weight: 25, score: profileScores.pepExposure, desc: t.riskPepExposureDesc },
      { key: 'Ownership', weight: 20, score: profileScores.ownership, desc: t.riskOwnershipDesc },
      { key: 'Topology', weight: 15, score: profileScores.topology, desc: t.riskTopologyDesc },
      { key: 'Activity', weight: 5, score: profileScores.activity, desc: t.riskActivityDesc },
    ],
    [profileScores.activity, profileScores.fraudSignal, profileScores.ownership, profileScores.pepExposure, profileScores.topology, t.riskActivityDesc, t.riskFraudSignalDesc, t.riskOwnershipDesc, t.riskPepExposureDesc, t.riskTopologyDesc],
  );

  return (
    <div className="dashboard-grid">
      <div className="card dashboard-hero dashboard-pro-hero">
        <div>
          <div className="card-title" style={{ marginBottom: '0.35rem' }}>{t.dashboardProTitle}</div>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>{t.dashboardProSubtitle}</p>
        </div>
        <div className="dashboard-pro-hero-meta">
          <div className="dashboard-pro-chip">{loading ? t.syncing : t.liveReady}</div>
          <div className="dashboard-pro-chip muted">{t.updatedAt}: {updatedAt || '--:--:--'}</div>
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
          <div className="card-title">{t.dashboardRiskIndex}</div>
          <div className="kpi-value" style={{ color: 'var(--accent-danger)' }}>{riskIndex}</div>
          <div className="kpi-meta">{t.dashboardRiskIndexMeta}</div>
        </div>
      </div>

      <div className="dashboard-pro-matrix">
        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.entityComposition}</h3>
            <button className="mini-action" onClick={onOpenGraph}>{t.openGraph}</button>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie data={entityCompositionData} dataKey="value" nameKey="name" innerRadius={76} outerRadius={110} paddingAngle={4}>
                  {entityCompositionData.map((entry, index) => (
                    <Cell key={entry.name} fill={palette[index % palette.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => Number(value ?? 0).toLocaleString()} />
                <Legend iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.topHubs}</h3>
            <button className="mini-action" onClick={onOpenGraph}>{t.exploreNetwork}</button>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={topHubChartData} layout="vertical" margin={{ left: 10, right: 20, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis type="number" stroke="var(--text-secondary)" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={140} stroke="var(--text-secondary)" tick={{ fontSize: 12 }} interval={0} />
                <Tooltip cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }} />
                <Bar dataKey="degree" fill="#3b82f6" radius={[0, 6, 6, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.dashboardRiskProfile}</h3>
            <button className="mini-action" onClick={onOpenAlerts}>{t.openAlerts}</button>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={alertTypeData} margin={{ left: 10, right: 10, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis dataKey="name" stroke="var(--text-secondary)" tick={{ fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={56} />
                <YAxis stroke="var(--text-secondary)" tick={{ fontSize: 12 }} />
                <Tooltip cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }} />
                <Bar dataKey="score" fill="#ef4444" radius={[6, 6, 0, 0]} barSize={32} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.dashboardPipelineTrend}</h3>
            <button className="mini-action" onClick={onOpenCrawl}>{t.navCrawl}</button>
          </div>
          <div className="chart-wrap">
            {crawlTrendData.length === 0 && <div className="empty-line">{t.dashboardNoPipelineData}</div>}
            {crawlTrendData.length > 0 && (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={crawlTrendData} margin={{ left: 0, right: 10, top: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="durationFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.7} />
                      <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="run" stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="duration" stroke="#22d3ee" fill="url(#durationFill)" strokeWidth={2} name={t.dashboardPipelineDuration} />
                  <Area type="monotone" dataKey="errors" stroke="#f59e0b" fillOpacity={0} strokeWidth={2} name={t.dashboardPipelineErrors} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="dashboard-pro-foot">
        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.dashboardIntelligenceBrief}</h3>
          </div>
          <div className="dashboard-insight-grid">
            <div className="dashboard-insight-item">
              <div className="dashboard-insight-label">{t.dashboardDensityLabel}</div>
              <div className="dashboard-insight-value">{relationshipDensity}%</div>
              <div className="dashboard-insight-sub">{t.dashboardDensityMeta}</div>
            </div>
            <div className="dashboard-insight-item">
              <div className="dashboard-insight-label">{t.dashboardTopHubLabel}</div>
              <div className="dashboard-insight-value">{topHubs[0]?.name || '--'}</div>
              <div className="dashboard-insight-sub">{topHubs[0] ? `${topHubs[0].degree} ${t.links}` : t.noHubData}</div>
            </div>
            <div className="dashboard-insight-item">
              <div className="dashboard-insight-label">{t.dashboardHotAlertLabel}</div>
              <div className="dashboard-insight-value">{alertsPreview[0]?.alert_type || '--'}</div>
              <div className="dashboard-insight-sub">{alertsPreview[0] ? alertsPreview[0].entity_name : t.noAlertPreview}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.riskFeed}</h3>
            <button className="mini-action" onClick={onOpenAlerts}>{t.runInvestigations}</button>
          </div>
          <div className="alerts-preview">
            {alertsPreview.length === 0 && <div className="empty-line">{t.noAlertPreview}</div>}
            {alertsPreview.map((alert, i) => (
              <div key={`${alert.entity_id}-${i}`} className="alert-row">
                <div>
                  <div className="alert-title">{alert.alert_type}: {alert.entity_name}</div>
                  <div className="alert-desc">{getAlertDescription(alert.description, lang)}</div>
                </div>
                <span className={`level-chip ${typeof alert.level === 'number' ? `level-${alert.level}` : String(alert.level).toLowerCase()}`}>
                  {String(alert.level).toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="dashboard-risk-scoring">
        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.riskScoringEngineTitle}</h3>
            <span className={`crawl-status-chip ${riskLevel.tone}`}>{t[`riskLevel${riskLevel.key[0].toUpperCase()}${riskLevel.key.slice(1)}` as keyof typeof t]}</span>
          </div>
          <p className="risk-scoring-subtitle">{t.riskScoringEngineSubtitle}</p>

          <div className="risk-score-badge" style={{ borderColor: `${riskLevel.color}55` }}>
            <div className="risk-score-label">{t.riskScoreLabel}</div>
            <div className="risk-score-value" style={{ color: riskLevel.color }}>{weightedRiskScore}</div>
            <div className="risk-score-meta">{t.riskScoreMeta}</div>
          </div>

          <div className="risk-scoring-table-wrap">
            <table className="risk-scoring-table">
              <thead>
                <tr>
                  <th>{t.riskDimensionHeader}</th>
                  <th>{t.riskWeightHeader}</th>
                  <th>{t.riskCurrentScoreHeader}</th>
                  <th>{t.riskDescriptionHeader}</th>
                </tr>
              </thead>
              <tbody>
                {riskRows.map((row) => (
                  <tr key={row.key}>
                    <td>{row.key}</td>
                    <td>{row.weight}%</td>
                    <td>{row.score}</td>
                    <td>{row.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="risk-level-grid">
            <div className="risk-level-box danger">
              <div>{t.riskDangerZone}</div>
              <strong>CRITICAL (&gt;=75)</strong>
            </div>
            <div className="risk-level-box warning">
              <div>{t.riskWarningZone}</div>
              <strong>MEDIUM/HIGH (25-74)</strong>
            </div>
            <div className="risk-level-box success">
              <div>{t.riskSafeZone}</div>
              <strong>LOW (&lt;25)</strong>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <h3 style={{ margin: 0 }}>{t.riskRadarTitle}</h3>
            <button className="mini-action" onClick={onOpenAlerts}>{t.openAlerts}</button>
          </div>

          <div className="chart-wrap" style={{ minHeight: 360 }}>
            <ResponsiveContainer width="100%" height={340}>
              <RadarChart data={radarData} outerRadius="72%">
                <PolarGrid stroke="var(--border-light)" />
                <PolarAngleAxis dataKey="axis" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 100]} tickCount={6} tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Radar
                  name={t.riskRadarSeriesLabel}
                  dataKey="value"
                  stroke="#ef4444"
                  fill="#ef4444"
                  fillOpacity={0.2}
                  strokeWidth={2.6}
                />
                <Tooltip formatter={(value) => `${Number(value ?? 0).toFixed(1)}/100`} />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <p className="risk-scoring-subtitle" style={{ marginTop: '0.4rem' }}>
            {t.riskRadarFootnote}
          </p>
        </div>
      </div>
    </div>
  );
}
