import { useEffect, useMemo, useState } from 'react';
import {
  listCrawlSources,
  runCrawlEtlSync,
  runCrawlSync,
  type CrawlSource,
} from '../services/api';
import { translations, type Lang } from '../i18n';

type CrawlRunMode = 'crawl' | 'etl';

type Props = {
  lang: Lang;
};

const FREE_DEFAULTS = ['yfinance', 'crawl4ai_company_pages', 'gleif', 'openownership'];
const HISTORY_STORAGE_KEY = 'crawl-dashboard-history';
const MAX_HISTORY_ITEMS = 12;

type RunStatus = 'success' | 'warning' | 'failed';

type RunRecord = {
  id: string;
  timestamp: string;
  mode: CrawlRunMode;
  status: RunStatus;
  parallel: boolean;
  dryRun: boolean;
  sources: string[];
  durationSeconds: number;
  totalErrors: number;
  totals: {
    companies: number;
    persons: number;
    relationships: number;
    publishedCompanies: number;
    publishedPersons: number;
    publishedRelationships: number;
  };
  quality?: {
    companiesAccepted: number;
    personsAccepted: number;
    relationshipsAccepted: number;
    companiesRejected: number;
    personsRejected: number;
    relationshipsRejected: number;
  };
  loaded?: {
    companies: number;
    persons: number;
    relationships: number;
  };
  perSource: Array<{
    source: string;
    companies: number;
    persons: number;
    relationships: number;
    errors: number;
  }>;
};

const readHistory = (): RunRecord[] => {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RunRecord[]) : [];
  } catch {
    return [];
  }
};

const toNum = (value: unknown): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) {
      return asNumber;
    }
  }
  return 0;
};

const asArray = (value: unknown): Array<Record<string, unknown>> => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object');
};

const extractQuality = (rawQuality: Record<string, unknown>): RunRecord['quality'] => {
  const companiesRejected =
    toNum(rawQuality.companies_rejected_missing_id) + toNum(rawQuality.companies_rejected_missing_name);
  const personsRejected =
    toNum(rawQuality.persons_rejected_missing_id) + toNum(rawQuality.persons_rejected_missing_name);
  const relationshipsRejected =
    toNum(rawQuality.relationships_rejected_missing_field) +
    toNum(rawQuality.relationships_rejected_invalid_type) +
    toNum(rawQuality.relationships_rejected_dangling);

  return {
    companiesAccepted: toNum(rawQuality.companies_accepted),
    personsAccepted: toNum(rawQuality.persons_accepted),
    relationshipsAccepted: toNum(rawQuality.relationships_accepted),
    companiesRejected,
    personsRejected,
    relationshipsRejected,
  };
};

const parseRunRecord = (
  mode: CrawlRunMode,
  payload: { sources: string[]; parallel: boolean; dryRun: boolean },
  result: unknown,
): RunRecord => {
  const obj = result && typeof result === 'object' ? (result as Record<string, unknown>) : {};
  const durationSeconds = toNum(obj.duration_s || obj.duration_seconds || obj.duration);

  const perSource = asArray(obj.per_source).map((item) => ({
    source: String(item.source || item.name || 'unknown'),
    companies: toNum(item.total_companies || item.companies),
    persons: toNum(item.total_persons || item.persons),
    relationships: toNum(item.total_relationships || item.relationships),
    errors: toNum(item.total_errors || item.errors),
  }));

  const crawled = obj.crawled && typeof obj.crawled === 'object' ? (obj.crawled as Record<string, unknown>) : {};
  const loaded = obj.loaded && typeof obj.loaded === 'object' ? (obj.loaded as Record<string, unknown>) : {};
  const qualityRaw = obj.quality && typeof obj.quality === 'object' ? (obj.quality as Record<string, unknown>) : null;

  const totalErrors =
    mode === 'etl'
      ? toNum(crawled.errors)
      : toNum(obj.total_errors || obj.errors) + perSource.reduce((sum, s) => sum + s.errors, 0);

  const etlSuccess = Boolean(obj.success);
  const status: RunStatus =
    mode === 'etl'
      ? etlSuccess
        ? totalErrors > 0
          ? 'warning'
          : 'success'
        : 'failed'
      : totalErrors > 0
        ? 'warning'
        : 'success';

  const sourcesFromResult = Array.isArray(obj.effective_sources)
    ? obj.effective_sources.map((x) => String(x))
    : [];
  const sources = sourcesFromResult.length > 0 ? sourcesFromResult : payload.sources;

  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
    mode,
    status,
    parallel: payload.parallel,
    dryRun: payload.dryRun,
    sources,
    durationSeconds,
    totalErrors,
    totals: {
      companies: mode === 'etl' ? toNum(crawled.companies) : toNum(obj.total_companies),
      persons: mode === 'etl' ? toNum(crawled.persons) : toNum(obj.total_persons),
      relationships: mode === 'etl' ? toNum(crawled.relationships) : toNum(obj.total_relationships),
      publishedCompanies: toNum(obj.published_companies),
      publishedPersons: toNum(obj.published_persons),
      publishedRelationships: toNum(obj.published_relationships),
    },
    quality: qualityRaw ? extractQuality(qualityRaw) : undefined,
    loaded:
      mode === 'etl'
        ? {
            companies: toNum(loaded.companies),
            persons: toNum(loaded.persons),
            relationships: toNum(loaded.relationships),
          }
        : undefined,
    perSource,
  };
};

export default function CrawlManager({ lang }: Props) {
  const t = translations[lang];
  const [sources, setSources] = useState<CrawlSource[]>([]);
  const [selected, setSelected] = useState<string[]>(FREE_DEFAULTS);
  const [parallel, setParallel] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [loadingSources, setLoadingSources] = useState(true);
  const [runningMode, setRunningMode] = useState<CrawlRunMode | null>(null);
  const [statusText, setStatusText] = useState('');
  const [resultText, setResultText] = useState('');
  const [history, setHistory] = useState<RunRecord[]>(() => readHistory());

  useEffect(() => {
    let mounted = true;
    setLoadingSources(true);

    const watchdog = window.setTimeout(() => {
      if (!mounted) {
        return;
      }
      setLoadingSources(false);
      setStatusText(t.crawlFailedLoadSources);
    }, 15000);

    listCrawlSources()
      .then((res) => {
        if (!mounted) {
          return;
        }
        const list = Array.isArray(res.sources) ? res.sources : [];
        setSources(list);
        const validDefaults = FREE_DEFAULTS.filter((id) => list.some((s) => s.id === id));
        if (validDefaults.length > 0) {
          setSelected(validDefaults);
        }
      })
      .catch((err: unknown) => {
        console.error('Failed loading crawl sources', err);
        if (mounted) {
          setStatusText(t.crawlFailedLoadSources);
        }
      })
      .finally(() => {
        if (mounted) {
          window.clearTimeout(watchdog);
          setLoadingSources(false);
        }
      });

    return () => {
      mounted = false;
      window.clearTimeout(watchdog);
    };
  }, [t.crawlFailedLoadSources]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const latestRun = history[0] || null;
  const totalRuns = history.length;
  const successfulRuns = history.filter((r) => r.status === 'success').length;
  const warningRuns = history.filter((r) => r.status === 'warning').length;
  const failedRuns = history.filter((r) => r.status === 'failed').length;
  const successRate = totalRuns > 0 ? Math.round((successfulRuns / totalRuns) * 100) : 0;
  const avgDuration =
    totalRuns > 0
      ? history.reduce((sum, item) => sum + item.durationSeconds, 0) / totalRuns
      : 0;

  useEffect(() => {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY_ITEMS)));
  }, [history]);

  const toggleSource = (sourceId: string) => {
    setSelected((prev) => {
      if (prev.includes(sourceId)) {
        return prev.filter((s) => s !== sourceId);
      }
      return [...prev, sourceId];
    });
  };

  const ensureSources = (): boolean => {
    if (selected.length === 0) {
      setStatusText(t.crawlNeedSource);
      return false;
    }
    return true;
  };

  const runCrawl = async () => {
    if (!ensureSources()) {
      return;
    }

    setRunningMode('crawl');
    setStatusText(t.crawlRunning);
    setResultText('');

    try {
      const result = await runCrawlSync({
        sources: selected,
        parallel,
      });
      setStatusText(t.crawlRunSuccess);
      setResultText(JSON.stringify(result, null, 2));
      const record = parseRunRecord('crawl', { sources: selected, parallel, dryRun }, result);
      setHistory((prev) => [record, ...prev].slice(0, MAX_HISTORY_ITEMS));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t.crawlUnknownError;
      setStatusText(`${t.crawlRunFailed}: ${message}`);
    } finally {
      setRunningMode(null);
    }
  };

  const runEtl = async () => {
    if (!ensureSources()) {
      return;
    }

    setRunningMode('etl');
    setStatusText(t.crawlEtlRunning);
    setResultText('');

    try {
      const result = await runCrawlEtlSync({
        sources: selected,
        parallel,
        dry_run: dryRun,
      });
      setStatusText(dryRun ? t.crawlDryRunSuccess : t.crawlEtlSuccess);
      setResultText(JSON.stringify(result, null, 2));
      const record = parseRunRecord('etl', { sources: selected, parallel, dryRun }, result);
      setHistory((prev) => [record, ...prev].slice(0, MAX_HISTORY_ITEMS));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t.crawlUnknownError;
      setStatusText(`${t.crawlEtlFailed}: ${message}`);
    } finally {
      setRunningMode(null);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'grid', gap: '1.25rem', paddingBottom: '2rem' }}>
      <div className="crawl-dashboard-grid">
        <div className="card crawl-dashboard-hero">
          <div>
            <div className="card-title" style={{ marginBottom: '0.35rem' }}>{t.crawlDashboardTitle}</div>
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>{t.crawlDashboardSubtitle}</p>
          </div>
          <div className="crawl-pill-row">
            <span className="crawl-pill">{t.crawlKpiSuccessRate}: {successRate}%</span>
            <span className="crawl-pill">{t.crawlKpiAvgDuration}: {avgDuration.toFixed(1)}s</span>
          </div>
        </div>

        <div className="crawl-kpi-grid">
          <div className="card crawl-kpi-card">
            <div className="card-title">{t.crawlKpiRuns}</div>
            <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>{totalRuns}</div>
            <div className="kpi-meta">{t.crawlKpiRunsMeta}</div>
          </div>
          <div className="card crawl-kpi-card">
            <div className="card-title">{t.crawlKpiSuccess}</div>
            <div className="kpi-value" style={{ color: 'var(--accent-success)' }}>{successfulRuns}</div>
            <div className="kpi-meta">{t.crawlKpiSuccessMeta}</div>
          </div>
          <div className="card crawl-kpi-card">
            <div className="card-title">{t.crawlKpiWarnings}</div>
            <div className="kpi-value" style={{ color: 'var(--accent-warning)' }}>{warningRuns}</div>
            <div className="kpi-meta">{t.crawlKpiWarningsMeta}</div>
          </div>
          <div className="card crawl-kpi-card">
            <div className="card-title">{t.crawlKpiFailures}</div>
            <div className="kpi-value" style={{ color: 'var(--accent-danger)' }}>{failedRuns}</div>
            <div className="kpi-meta">{t.crawlKpiFailuresMeta}</div>
          </div>
        </div>

        <div className="crawl-dashboard-main">
          <div className="card">
            <div className="panel-header">
              <h3 style={{ margin: 0 }}>{t.crawlLatestRun}</h3>
              {latestRun && (
                <span className={`crawl-status-chip ${latestRun.status}`}>{t[`crawlStatus${latestRun.status[0].toUpperCase()}${latestRun.status.slice(1)}` as keyof typeof t]}</span>
              )}
            </div>

            {!latestRun && <div className="empty-line">{t.crawlNoHistory}</div>}

            {latestRun && (
              <div className="crawl-latest-body">
                <div className="crawl-latest-meta">
                  <div><strong>{t.crawlModeLabel}</strong>: {latestRun.mode.toUpperCase()}</div>
                  <div><strong>{t.crawlSourcesLabel}</strong>: {latestRun.sources.join(', ')}</div>
                  <div><strong>{t.crawlDurationLabel}</strong>: {latestRun.durationSeconds.toFixed(2)}s</div>
                  <div><strong>{t.crawlTimestampLabel}</strong>: {new Date(latestRun.timestamp).toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US')}</div>
                </div>

                <div className="crawl-stage-grid">
                  <div className="crawl-stage-box">
                    <div className="crawl-stage-name">{t.crawlStageCrawled}</div>
                    <div className="crawl-stage-value">
                      {latestRun.totals.companies.toLocaleString()} / {latestRun.totals.persons.toLocaleString()} / {latestRun.totals.relationships.toLocaleString()}
                    </div>
                  </div>
                  <div className="crawl-stage-box">
                    <div className="crawl-stage-name">{t.crawlStagePublished}</div>
                    <div className="crawl-stage-value">
                      {latestRun.totals.publishedCompanies.toLocaleString()} / {latestRun.totals.publishedPersons.toLocaleString()} / {latestRun.totals.publishedRelationships.toLocaleString()}
                    </div>
                  </div>
                  <div className="crawl-stage-box">
                    <div className="crawl-stage-name">{t.crawlStageLoaded}</div>
                    <div className="crawl-stage-value">
                      {latestRun.loaded
                        ? `${latestRun.loaded.companies.toLocaleString()} / ${latestRun.loaded.persons.toLocaleString()} / ${latestRun.loaded.relationships.toLocaleString()}`
                        : t.crawlStageNotAvailable}
                    </div>
                  </div>
                </div>

                {!!latestRun.quality && (
                  <div className="crawl-quality-grid">
                    <div>
                      <div className="mix-row"><span>{t.companies}</span><span>{latestRun.quality.companiesAccepted} / {latestRun.quality.companiesRejected}</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${Math.max(4, Math.round((latestRun.quality.companiesAccepted / Math.max(1, latestRun.quality.companiesAccepted + latestRun.quality.companiesRejected)) * 100))}%`, background: 'var(--accent-success)' }} /></div>
                    </div>
                    <div>
                      <div className="mix-row"><span>{t.persons}</span><span>{latestRun.quality.personsAccepted} / {latestRun.quality.personsRejected}</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${Math.max(4, Math.round((latestRun.quality.personsAccepted / Math.max(1, latestRun.quality.personsAccepted + latestRun.quality.personsRejected)) * 100))}%`, background: '#22d3ee' }} /></div>
                    </div>
                    <div>
                      <div className="mix-row"><span>{t.graphLinks}</span><span>{latestRun.quality.relationshipsAccepted} / {latestRun.quality.relationshipsRejected}</span></div>
                      <div className="mix-track"><div className="mix-fill" style={{ width: `${Math.max(4, Math.round((latestRun.quality.relationshipsAccepted / Math.max(1, latestRun.quality.relationshipsAccepted + latestRun.quality.relationshipsRejected)) * 100))}%`, background: 'var(--accent-warning)' }} /></div>
                    </div>
                  </div>
                )}

                {latestRun.perSource.length > 0 && (
                  <div className="crawl-source-table">
                    <div className="crawl-source-header">
                      <span>{t.crawlSourceHeader}</span>
                      <span>{t.crawlEntityHeader}</span>
                      <span>{t.crawlErrorsHeader}</span>
                    </div>
                    {latestRun.perSource.map((row) => (
                      <div key={`${latestRun.id}-${row.source}`} className="crawl-source-row">
                        <span>{row.source}</span>
                        <span>{row.companies}/{row.persons}/{row.relationships}</span>
                        <span>{row.errors}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <div className="panel-header">
              <h3 style={{ margin: 0 }}>{t.crawlRunHistory}</h3>
            </div>
            {history.length === 0 && <div className="empty-line">{t.crawlNoHistory}</div>}
            {history.length > 0 && (
              <div className="crawl-history-list">
                {history.map((item) => (
                  <div key={item.id} className="crawl-history-row">
                    <div>
                      <div className="crawl-history-title">{item.mode.toUpperCase()} • {item.sources.join(', ')}</div>
                      <div className="crawl-history-meta">{new Date(item.timestamp).toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US')}</div>
                    </div>
                    <div className="crawl-history-right">
                      <div>{item.durationSeconds.toFixed(2)}s</div>
                      <span className={`crawl-status-chip ${item.status}`}>{t[`crawlStatus${item.status[0].toUpperCase()}${item.status.slice(1)}` as keyof typeof t]}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: '0.4rem' }}>{t.crawlTitle}</div>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>{t.crawlSubtitle}</p>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: '0.8rem' }}>{t.crawlSources}</div>
        {loadingSources ? (
          <div style={{ color: 'var(--text-muted)' }}>{t.crawlLoadingSources}</div>
        ) : (
          <div style={{ display: 'grid', gap: '0.7rem' }}>
            {sources.map((s) => (
              <label
                key={s.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '20px 1fr auto',
                  gap: '0.6rem',
                  alignItems: 'center',
                  border: '1px solid var(--border-light)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.7rem 0.8rem',
                  background: 'var(--bg-row-muted)',
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedSet.has(s.id)}
                  onChange={() => toggleSource(s.id)}
                />
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.name}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                    {s.id} | {s.license}
                  </div>
                </div>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.5rem',
                    borderRadius: '999px',
                    border: '1px solid var(--border-light)',
                    background: s.requires_api_key ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.14)',
                    color: s.requires_api_key ? '#fcd34d' : '#6ee7b7',
                  }}
                >
                  {s.requires_api_key ? t.crawlNeedsKey : t.crawlFreeSource}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: '0.8rem' }}>{t.crawlRunOptions}</div>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
            <input type="checkbox" checked={parallel} onChange={(e) => setParallel(e.target.checked)} />
            {t.crawlParallel}
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
            {t.crawlDryRun}
          </label>
        </div>

        <div style={{ display: 'flex', gap: '0.7rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          <button
            onClick={runCrawl}
            disabled={runningMode !== null || loadingSources}
            style={{
              padding: '0.6rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-light)',
              background: 'var(--bg-base)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              opacity: runningMode !== null ? 0.7 : 1,
            }}
          >
            {runningMode === 'crawl' ? t.crawlRunning : t.crawlRunOnly}
          </button>

          <button
            onClick={runEtl}
            disabled={runningMode !== null || loadingSources}
            style={{
              padding: '0.6rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--accent-primary)',
              color: 'white',
              fontWeight: 700,
              opacity: runningMode !== null ? 0.7 : 1,
            }}
          >
            {runningMode === 'etl' ? t.crawlEtlRunning : t.crawlRunEtl}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: '0.6rem' }}>{t.crawlStatus}</div>
        <div style={{ color: 'var(--text-primary)', marginBottom: '0.8rem' }}>{statusText || t.crawlIdle}</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.45rem' }}>{t.crawlLastReport}</div>
        <pre
          style={{
            margin: 0,
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-base)',
            color: 'var(--text-secondary)',
            fontSize: '0.8rem',
            padding: '0.8rem',
            maxHeight: '280px',
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {resultText || t.crawlNoReport}
        </pre>
      </div>
    </div>
  );
}
