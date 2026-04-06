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

const FREE_DEFAULTS = ['gleif', 'openownership', 'worldbank', 'vietnam_nbr'];

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

  useEffect(() => {
    let mounted = true;
    setLoadingSources(true);
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
          setLoadingSources(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [t.crawlFailedLoadSources]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

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
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t.crawlUnknownError;
      setStatusText(`${t.crawlEtlFailed}: ${message}`);
    } finally {
      setRunningMode(null);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'grid', gap: '1.25rem', paddingBottom: '2rem' }}>
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
