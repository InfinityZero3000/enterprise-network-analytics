import { useState, useEffect } from 'react';
import { getFraudAlerts } from '../services/api';
import { getAlertDescription, translations, type Lang } from '../i18n';

type Props = {
  lang: Lang;
  onSummaryChange?: (summary: { count: number; topTypes: string[] }) => void;
};

export default function AlertsRisk({ lang, onSummaryChange }: Props) {
  const t = translations[lang];
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = () => {
    setLoading(true);
    getFraudAlerts()
      .then(data => {
        setAlerts(data);
        if (onSummaryChange) {
          const counts = new Map<string, number>();
          data.forEach((a: any) => {
            const key = String(a.alert_type || 'unknown');
            counts.set(key, (counts.get(key) || 0) + 1);
          });
          const topTypes = [...counts.entries()]
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([k]) => k);
          onSummaryChange({ count: data.length, topTypes });
        }
        setLoading(false);
      })
      .catch((e) => {
        console.log('Failed fetching live alerts, using mock data', e);
        setAlerts([
          { entity_id: 'C10492', entity_name: 'Shell Holding Corp', alert_type: 'SHELL_COMPANY', level: 3, description: 'No employees, high transaction mapping.' },
          { entity_id: 'P938', entity_name: 'John Doe', alert_type: 'PEP_EXPOSURE', level: 2, description: 'Direct relationship to PEP node.' },
          { entity_id: 'C9921', entity_name: 'Circular Logistics', alert_type: 'CIRCULAR_OWNERSHIP', level: 3, description: 'Detected 3-hop circular ownership chain.' }
        ]);
        onSummaryChange?.({ count: 3, topTypes: ['SHELL_COMPANY', 'PEP_EXPOSURE', 'CIRCULAR_OWNERSHIP'] });
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>{t.activeFraudAlerts}</h3>
        <button 
          onClick={fetchAlerts}
          disabled={loading}
          style={{ 
            padding: '0.5rem 1rem', 
            background: 'var(--accent-primary)', 
            color: 'white', 
            border: 'none', 
            borderRadius: 'var(--radius-md)',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.7 : 1
          }}>
          {loading ? t.runningRules : t.runRuleEngine}
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>{t.loadingRules}</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' }}>
          {alerts.map((a, i) => (
            <div key={i} style={{ 
              background: 'var(--bg-surface)', 
              border: `1px solid ${a.level === 3 || a.level === 'critical' || a.level === 'high' ? 'var(--accent-danger)' : 'var(--accent-warning)'}`,
              borderRadius: 'var(--radius-md)',
              padding: '1.5rem',
              display: 'flex',
              gap: '1.5rem',
              alignItems: 'center'
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: '50%',
                background: a.level === 3 || a.level === 'critical' || a.level === 'high' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: a.level === 3 || a.level === 'critical' || a.level === 'high' ? 'var(--accent-danger)' : 'var(--accent-warning)',
                fontWeight: 'bold', fontSize: '1.5rem'
              }}>!</div>
              <div style={{ flex: 1 }}>
                <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--text-primary)' }}>{a.alert_type}: {a.entity_name}</h4>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{getAlertDescription(a.description, lang)}</div>
              </div>
              <div>
                <button style={{ padding: '0.5rem 1rem', background: 'var(--bg-base)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)' }}>{t.investigate}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
