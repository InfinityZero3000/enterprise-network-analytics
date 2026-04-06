import { useEffect, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import {
  createInvestigationCase,
  getBlastRadius,
  getFraudAlerts,
  getInvestigationReport,
  getInvestigationSubgraph,
  getShortestRiskPath,
  saveInvestigationSnapshot,
  type BlastRadiusResult,
  type InvestigationCase,
  type InvestigationGraph,
  type RiskPathResult,
  updateInvestigationCaseStatus,
} from '../services/api';
import { getAlertDescription, translations, type Lang } from '../i18n';

type FraudAlert = {
  entity_id: string;
  entity_name: string;
  alert_type: string;
  level: number | string;
  description: string;
};

type Props = {
  lang: Lang;
  onSummaryChange?: (summary: { count: number; topTypes: string[] }) => void;
  onInvestigate?: (entityName: string, alertType: string) => void;
  onAskAiPrompt?: (prompt: string) => void;
  onImportSnapshotToChat?: (prompt: string) => void;
};

export default function AlertsRisk({
  lang,
  onSummaryChange,
  onInvestigate,
  onAskAiPrompt,
  onImportSnapshotToChat,
}: Props) {
  const t = translations[lang];
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<FraudAlert | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const [reportText, setReportText] = useState('');
  const [subgraph, setSubgraph] = useState<InvestigationGraph | null>(null);
  const [riskPath, setRiskPath] = useState<RiskPathResult | null>(null);
  const [blastRadius, setBlastRadius] = useState<BlastRadiusResult | null>(null);
  const [activeCase, setActiveCase] = useState<InvestigationCase | null>(null);
  const [snapshotNote, setSnapshotNote] = useState('');
  const [latestSnapshotImage, setLatestSnapshotImage] = useState<string | null>(null);
  const [miniGraphWidth, setMiniGraphWidth] = useState(380);
  const miniGraphWrapRef = useRef<HTMLDivElement | null>(null);

  const caseStatuses: Array<InvestigationCase['status']> = [
    'NEW',
    'INVESTIGATING',
    'FALSE_POSITIVE',
    'CONFIRMED_FRAUD',
  ];

  const promptChips = selectedAlert
    ? [
        `Find ultimate beneficial owners for ${selectedAlert.entity_name}`,
        `Check sanctions and suspicious links for ${selectedAlert.entity_name}`,
        `Analyze address-sharing and shell-company indicators for ${selectedAlert.entity_name}`,
      ]
    : [];

  const fetchAlerts = () => {
    setLoading(true);
    getFraudAlerts()
      .then(data => {
        setAlerts(data);
        if (onSummaryChange) {
          const counts = new Map<string, number>();
          data.forEach((a: FraudAlert) => {
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

  const openInvestigationPanel = async (alert: FraudAlert) => {
    setSelectedAlert(alert);
    setPanelLoading(true);

    try {
      const createdCase = await createInvestigationCase({
        entity_id: alert.entity_id,
        entity_name: alert.entity_name,
        alert_type: alert.alert_type,
      });
      setActiveCase(createdCase);
      setLatestSnapshotImage(createdCase.snapshots?.[0]?.image_data_url || null);

      const [subgraphRes, pathRes, blastRes] = await Promise.all([
        getInvestigationSubgraph(alert.entity_name, alert.alert_type, 2, alert.entity_id),
        getShortestRiskPath(alert.entity_name, alert.entity_id),
        getBlastRadius(alert.entity_name, alert.entity_id),
      ]);

      const normalizedSubgraph = (subgraphRes.nodes?.length || 0) > 0
        ? subgraphRes
        : {
            nodes: [
              {
                id: alert.entity_id,
                name: alert.entity_name,
                group: 1,
                risk: 0,
                labels: ['AlertEntity'],
              },
            ],
            links: [],
          };

      const reportRes = await getInvestigationReport({
        entity_name: alert.entity_name,
        entity_id: alert.entity_id,
        alert_type: alert.alert_type,
        evidence: alert.description,
        with_signals: false,
        subgraph_nodes: normalizedSubgraph.nodes.length,
        subgraph_links: normalizedSubgraph.links.length,
        blast_impacted_nodes: blastRes?.impacted_nodes || 0,
        blast_high_risk_hits: blastRes?.high_risk_hits || 0,
        risk_path_hops: pathRes?.hops ?? null,
        risk_path_target: pathRes?.target ?? null,
      });

      setReportText(reportRes.report);
      setSubgraph(normalizedSubgraph);
      setRiskPath(pathRes);
      setBlastRadius(blastRes);
    } catch (err) {
      console.error('Failed to load investigation context', err);
      setReportText(t.investigationReportFailed);
      setSubgraph({ nodes: [], links: [] });
      setRiskPath(null);
      setBlastRadius(null);
    } finally {
      setPanelLoading(false);
    }
  };

  const updateCaseStatus = async (status: InvestigationCase['status']) => {
    if (!activeCase) {
      return;
    }
    const updated = await updateInvestigationCaseStatus(activeCase.case_id, status);
    setActiveCase(updated);
  };

  const saveSnapshot = async () => {
    if (!activeCase || !snapshotNote.trim()) {
      return;
    }
    const canvas = miniGraphWrapRef.current?.querySelector('canvas');
    const imageDataUrl = canvas ? canvas.toDataURL('image/png') : undefined;

    const response = await saveInvestigationSnapshot(activeCase.case_id, {
      note: snapshotNote,
      graph_node_count: subgraph?.nodes.length || 0,
      graph_link_count: subgraph?.links.length || 0,
      image_data_url: imageDataUrl,
    });

    if (response?.snapshot) {
      const snapshot = response.snapshot;
      setActiveCase((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          updated_at: snapshot.created_at,
          snapshots: [snapshot, ...(prev.snapshots || [])],
        };
      });
      if (snapshot.image_data_url) {
        setLatestSnapshotImage(snapshot.image_data_url);
      }
    }
    setSnapshotNote('');
  };

  const importSnapshotContextToChat = () => {
    if (!selectedAlert) {
      return;
    }

    const inferChecklistByAlertType = (alertType: string) => {
      const key = alertType.toUpperCase();
      if (key.includes('MASS_REGISTRATION')) {
        return 'Check shared registered addresses, nominee patterns, and synchronized registration dates.';
      }
      if (key.includes('CIRCULAR_OWNERSHIP')) {
        return 'Verify ownership loops, repeated intermediaries, and percentage stacking across hops.';
      }
      if (key.includes('PEP')) {
        return 'Verify PEP linkage quality, role recency, and transaction exposure through connected entities.';
      }
      if (key.includes('SHELL')) {
        return 'Check low-activity shell indicators: dormant status, nominee directors, and pass-through transactions.';
      }
      return 'Validate beneficial ownership, related directors, and exposure to sanctioned/high-risk counterparts.';
    };

    const latestSnapshot = activeCase?.snapshots?.[0];
    const nodesCount = subgraph?.nodes.length || 0;
    const linksCount = subgraph?.links.length || 0;
    const impactedCount = blastRadius?.impacted_nodes || 0;
    const highRiskNeighbors = blastRadius?.high_risk_hits || 0;
    const riskPathHops = riskPath?.hops;
    const hasGraphSignal =
      nodesCount > 1 ||
      linksCount > 0 ||
      impactedCount > 0 ||
      (riskPathHops != null && riskPathHops >= 1);

    const graphExtractionLine = hasGraphSignal
      ? `Graph extraction status: resolved local topology with ${nodesCount} nodes and ${linksCount} links.`
      : `Graph extraction status: low-confidence topology (algorithm could not resolve neighboring nodes for entity_id ${selectedAlert.entity_id}). Use entity-centric evidence and report narrative for triage.`;

    const localEntityHints = (subgraph?.nodes || [])
      .slice(0, 8)
      .map((n) => n.name)
      .filter(Boolean);

    const hintLine = localEntityHints.length > 0
      ? `Known local entities: ${localEntityHints.join(', ')}.`
      : `Known local entities: ${selectedAlert.entity_name} (seed only).`;

    const prompt = [
      `Analyze this investigation snapshot for ${selectedAlert.entity_name} (${selectedAlert.alert_type}).`,
      `Case ID: ${activeCase?.case_id || 'N/A'}, status: ${activeCase?.status || 'N/A'}, created_at: ${activeCase?.created_at || 'N/A'}, snapshots: ${activeCase?.snapshots?.length || 0}.`,
      `Entity profile: id ${selectedAlert.entity_id}, severity ${selectedAlert.level}, alert evidence: ${selectedAlert.description || 'N/A'}.`,
      graphExtractionLine,
      `Graph context: ${nodesCount} nodes, ${linksCount} links.`,
      hintLine,
      `Risk signals: shortest path ${riskPathHops ?? 'N/A'} hops to ${riskPath?.target || 'N/A'}, blast radius ${impactedCount} impacted and ${highRiskNeighbors} high-risk neighbors.`,
      `AI report summary: ${reportText || 'No report text available.'}`,
      `Snapshot note: ${latestSnapshot?.note || snapshotNote || 'No note provided yet.'}`,
      `Snapshot image attached in case store: ${latestSnapshot?.image_data_url ? 'yes' : 'no'}.`,
      `Priority checks for this alert type: ${inferChecklistByAlertType(selectedAlert.alert_type)}`,
      'Please summarize top risks, confidence level, and next 3 investigation actions. Explicitly state uncertainty when graph topology is sparse.',
    ].join(' ');
    onImportSnapshotToChat?.(prompt);
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  useEffect(() => {
    const el = miniGraphWrapRef.current;
    if (!el) {
      return;
    }

    const updateWidth = () => {
      const nextWidth = Math.max(240, Math.floor(el.clientWidth));
      setMiniGraphWidth(nextWidth);
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);

    return () => observer.disconnect();
  }, [selectedAlert]);

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
        <div style={{
          display: 'grid',
          gridTemplateColumns: selectedAlert ? '1fr minmax(320px, 430px)' : '1fr',
          gap: '1rem',
          alignItems: 'start',
          maxHeight: selectedAlert ? 'calc(100vh - 210px)' : undefined,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem', overflowY: selectedAlert ? 'auto' : undefined, paddingRight: selectedAlert ? '0.25rem' : undefined }}>
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
                <button 
                  onClick={() => openInvestigationPanel(a)}
                  style={{ padding: '0.5rem 1rem', background: 'var(--bg-base)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', cursor: 'pointer' }}
                >
                  {t.investigate}
                </button>
              </div>
            </div>
          ))}
          </div>

          {selectedAlert && (
            <div className="card" style={{ position: 'sticky', top: '0.8rem', maxHeight: 'calc(100vh - 230px)', overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
                <div style={{ fontWeight: 700 }}>{selectedAlert.entity_name}</div>
                <button
                  className="mini-action"
                  onClick={() => setSelectedAlert(null)}
                >
                  {t.close}
                </button>
              </div>

              <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.8rem' }}>
                {selectedAlert.alert_type} • {selectedAlert.entity_id}
              </div>

              {panelLoading ? (
                <div style={{ color: 'var(--text-secondary)' }}>{t.aiThinking}</div>
              ) : (
                <>
                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '0.7rem', marginBottom: '0.7rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.4rem' }}>{t.investigationReportTitle}</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>{reportText}</div>
                  </div>

                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '0.7rem', marginBottom: '0.7rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{t.investigationMiniGraphTitle}</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                      Nodes: {subgraph?.nodes.length || 0} | Links: {subgraph?.links.length || 0}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: '0.35rem' }}>
                      {t.investigationMiniGraphVisual}
                    </div>
                    <div
                      ref={miniGraphWrapRef}
                      style={{
                        marginTop: '0.45rem',
                        minHeight: 180,
                        border: '1px solid var(--border-light)',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-base)',
                        overflow: 'hidden',
                      }}
                    >
                      {(subgraph?.nodes?.length || 0) > 0 ? (
                        <ForceGraph2D
                          width={miniGraphWidth}
                          height={180}
                          graphData={{
                            nodes: (subgraph?.nodes || []).map((n) => ({
                              ...n,
                              val: 3,
                            })),
                            links: (subgraph?.links || []).map((l) => ({
                              ...l,
                              value: 1,
                            })),
                          }}
                          nodeRelSize={3}
                          cooldownTicks={50}
                          nodeColor={(n: any) => {
                            if (n.group === 1) return '#3b82f6';
                            if (n.group === 2) return '#94a3b8';
                            return '#ef4444';
                          }}
                          linkColor={() => 'rgba(148,163,184,0.5)'}
                          linkWidth={() => 1}
                          enableZoomInteraction={false}
                          enablePanInteraction={false}
                          backgroundColor={document.documentElement.getAttribute('data-theme') === 'light' ? '#ffffff' : '#0f1623'}
                          nodeCanvasObjectMode={() => 'after'}
                          nodeCanvasObject={(node: any, ctx, globalScale) => {
                            const label = String(node.name || '');
                            const fontSize = 9 / globalScale;
                            ctx.font = `${fontSize}px Sans-Serif`;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillStyle = document.documentElement.getAttribute('data-theme') === 'light'
                              ? 'rgba(15,23,42,0.8)'
                              : 'rgba(255,255,255,0.8)';
                            if (label && node.val >= 3) {
                              ctx.fillText(label, node.x || 0, (node.y || 0) + 7);
                            }
                          }}
                        />
                      ) : (
                        <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                          {t.investigationNoContext}
                        </div>
                      )}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '0.35rem' }}>
                      {(subgraph?.nodes || []).slice(0, 6).map((n) => n.name).join(', ') || t.investigationNoContext}
                    </div>
                    <button
                      style={{ marginTop: '0.6rem', padding: '0.45rem 0.65rem', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-base)', color: 'var(--text-primary)' }}
                      onClick={() => onInvestigate?.(selectedAlert.entity_name, selectedAlert.alert_type)}
                    >
                      {t.investigationOpenFocusedGraph}
                    </button>
                  </div>

                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '0.7rem', marginBottom: '0.7rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{t.investigationRiskSignals}</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.83rem', marginBottom: '0.3rem' }}>
                      {t.investigationShortestPathPrefix}: {riskPath?.hops != null ? `${riskPath.hops} hops to ${riskPath.target}` : t.investigationNoRiskPath}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.83rem' }}>
                      {t.investigationBlastRadiusPrefix}: {blastRadius?.impacted_nodes || 0} {t.investigationImpactedSuffix}, {blastRadius?.high_risk_hits || 0} {t.investigationHighRiskNeighborsSuffix}
                    </div>
                  </div>

                  {activeCase && (
                    <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '0.7rem', marginBottom: '0.7rem' }}>
                      <div style={{ fontWeight: 600, marginBottom: '0.4rem' }}>{t.investigationCaseWorkflow}</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: '0.45rem' }}>
                        {activeCase.case_id}
                      </div>
                      <select
                        value={activeCase.status}
                        onChange={(e) => updateCaseStatus(e.target.value as InvestigationCase['status'])}
                        style={{ width: '100%', padding: '0.45rem 0.6rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-surface)' }}
                      >
                        {caseStatuses.map((status) => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div style={{ border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '0.7rem', marginBottom: '0.7rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{t.investigationSnapshotNotes}</div>
                    <textarea
                      value={snapshotNote}
                      onChange={(e) => setSnapshotNote(e.target.value)}
                      rows={3}
                      placeholder={t.investigationSnapshotPlaceholder}
                      style={{ width: '100%', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-base)', color: 'var(--text-primary)', padding: '0.5rem' }}
                    />
                    <button
                      onClick={saveSnapshot}
                      style={{ marginTop: '0.55rem', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-base)', color: 'var(--text-primary)' }}
                    >
                      {t.investigationSaveSnapshot}
                    </button>
                    <button
                      onClick={importSnapshotContextToChat}
                      style={{ marginTop: '0.5rem', marginLeft: '0.45rem', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-surface)', color: 'var(--text-primary)' }}
                    >
                      {t.investigationImportSnapshotToChat}
                    </button>
                    {latestSnapshotImage && (
                      <div style={{ marginTop: '0.65rem' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.78rem', marginBottom: '0.35rem', color: 'var(--text-secondary)' }}>
                          {t.investigationLatestSnapshot}
                        </div>
                        <img
                          src={latestSnapshotImage}
                          alt="Investigation snapshot"
                          style={{ width: '100%', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)' }}
                        />
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {promptChips.map((chip) => (
                      <button
                        key={chip}
                        onClick={() => onAskAiPrompt?.(chip)}
                        style={{ padding: '0.35rem 0.55rem', borderRadius: '999px', border: '1px solid var(--border-light)', background: 'var(--bg-base)', color: 'var(--text-secondary)', fontSize: '0.75rem' }}
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
