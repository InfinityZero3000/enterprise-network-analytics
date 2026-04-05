import { useRef, useEffect, useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { translations, type Lang } from '../i18n';

type Props = {
  lang: Lang;
  onSummaryChange?: (summary: { nodes: number; links: number; hubs: string[] }) => void;
};

export default function GraphExplorer({ lang, onSummaryChange }: Props) {
  const t = translations[lang];
  const [data, setData] = useState<{nodes: any[], links: any[]}>({ nodes: [], links: [] });
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [search, setSearch] = useState('');
  const [minDegree, setMinDegree] = useState(0);
  const [freezeLayout, setFreezeLayout] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);

  const [repulsionStrength, setRepulsionStrength] = useState(() => Number(localStorage.getItem('app-graph-repulsion')) || 150);
  const [linkDistance, setLinkDistance] = useState(() => Number(localStorage.getItem('app-graph-link-dist')) || 30);

  const getId = (value: any): string => {
    if (typeof value === 'object' && value !== null) {
      return String(value.id ?? value.node_id ?? '');
    }
    return String(value ?? '');
  };

  const fetchGraphData = (type = 'default') => {
    const baseUrl = localStorage.getItem('app-api-url') || 'http://localhost:8000';
    let url = `${baseUrl}/api/v1/graph/network?limit=250`;
    if (type === 'pagerank') {
      url += "&order_by=pagerank";
    }

    fetch(url)
      .then(res => res.json())
      .then(json => {
        if (!json.nodes || !json.links) return;
        json.nodes.forEach((n: any) => { 
            if (!n.val) n.val = 3; 
            if (n.pagerank && n.pagerank > 0) {
               n.val = Math.max(3, n.pagerank * 50);
            }
        });
        json.links.forEach((l: any) => l.value = 1);

        if (onSummaryChange) {
          const sorted = [...json.nodes]
            .sort((a: any, b: any) => (b.val || 0) - (a.val || 0))
            .slice(0, 3)
            .map((n: any) => n.name);
          onSummaryChange({
            nodes: json.nodes.length,
            links: json.links.length,
            hubs: sorted
          });
        }
        setData(json);
      })
      .catch(err => console.error("Error fetching graph data:", err));
  };

  useEffect(() => {
    fetchGraphData();
  }, []);

  useEffect(() => {
    const handleSettingsChange = () => {
      setRepulsionStrength(Number(localStorage.getItem('app-graph-repulsion')) || 150);
      setLinkDistance(Number(localStorage.getItem('app-graph-link-dist')) || 30);
      fetchGraphData(); // refresh if API changed
    };

    window.addEventListener('app-settings-changed', handleSettingsChange);
    return () => window.removeEventListener('app-settings-changed', handleSettingsChange);
  }, []);

  useEffect(() => {
    if (fgRef.current && (data.nodes.length || data.links.length)) {
      fgRef.current.d3Force('charge').strength(-repulsionStrength).distanceMax(8000);
      fgRef.current.d3Force('link').distance(linkDistance);
      if (!freezeLayout && document.documentElement.getAttribute('data-theme')) {
        setTimeout(() => fgRef.current?.d3ReheatSimulation(), 50);
      }
    }
  }, [repulsionStrength, linkDistance, data, freezeLayout]);

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    
    window.addEventListener('resize', updateDimensions);
    setTimeout(updateDimensions, 100);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const neighborMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const l of data.links) {
      const source = getId((l as any).source);
      const target = getId((l as any).target);
      if (!source || !target) continue;
      if (!map.has(source)) map.set(source, new Set());
      if (!map.has(target)) map.set(target, new Set());
      map.get(source)!.add(target);
      map.get(target)!.add(source);
    }
    return map;
  }, [data]);

  const degreeMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const l of data.links) {
      const source = getId((l as any).source);
      const target = getId((l as any).target);
      map.set(source, (map.get(source) || 0) + 1);
      map.set(target, (map.get(target) || 0) + 1);
    }
    return map;
  }, [data]);

  const highlightedIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedNodeId) {
      ids.add(selectedNodeId);
      const neighbors = neighborMap.get(selectedNodeId);
      neighbors?.forEach((id) => ids.add(id));
    }

    const query = search.trim().toLowerCase();
    if (query) {
      for (const n of data.nodes) {
        const id = String(n.id);
        const name = String(n.name || '').toLowerCase();
        if (name.includes(query) || id.includes(query)) {
          ids.add(id);
          const neighbors = neighborMap.get(id);
          neighbors?.forEach((nid) => ids.add(nid));
        }
      }
    }
    return ids;
  }, [selectedNodeId, search, data.nodes, neighborMap]);

  const getNodeColor = (node: any) => {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const nodeId = getId(node.id ?? node);
    const isFocused = highlightedIds.has(nodeId);
    
    if (!isFocused && (selectedNodeId || search.trim())) {
      return isLight ? 'rgba(71,85,105,0.2)' : 'rgba(100,116,139,0.25)';
    }

    if (node.group === 1) return isFocused ? (isLight ? '#1d4ed8' : '#60a5fa') : (isLight ? '#2563eb' : '#3b82f6');
    if (node.group === 3) return isFocused ? (isLight ? '#b91c1c' : '#f87171') : (isLight ? '#dc2626' : '#ef4444');
    return isFocused ? (isLight ? '#475569' : '#cbd5e1') : (isLight ? '#94a3b8' : '#64748b');
  };

  const filteredData = useMemo(() => {
    const query = search.trim().toLowerCase();
    const visibleNodeIds = new Set<string>();

    for (const n of data.nodes) {
      const nodeId = String(n.id);
      const degree = degreeMap.get(nodeId) || 0;
      const inDegree = degree >= minDegree;

      if (query) {
        if (highlightedIds.has(nodeId)) {
          visibleNodeIds.add(nodeId);
        }
      } else if (inDegree) {
        visibleNodeIds.add(nodeId);
      }
    }

    const nodes = data.nodes.filter((n: any) => visibleNodeIds.has(String(n.id)));
    const links = data.links.filter((l: any) => {
      const source = getId(l.source);
      const target = getId(l.target);
      return visibleNodeIds.has(source) && visibleNodeIds.has(target);
    });

    return { nodes, links };
  }, [data, minDegree, search, degreeMap, highlightedIds]);

  useEffect(() => {
    if (!fgRef.current) return;
    if (freezeLayout) {
      for (const n of data.nodes) {
        if (typeof n.x === 'number' && typeof n.y === 'number') {
          n.fx = n.x;
          n.fy = n.y;
        }
      }
    } else {
      for (const n of data.nodes) {
        n.fx = undefined;
        n.fy = undefined;
      }
      setTimeout(() => fgRef.current?.d3ReheatSimulation(), 50);
    }
  }, [freezeLayout, data.nodes]);

  const handleZoomToFit = () => {
    if (!fgRef.current) return;
    fgRef.current.zoomToFit(500, 90);
  };

  const handleExpandGraph = () => {
    setRepulsionStrength(prev => {
      const newVal = prev >= 2000 ? (Number(localStorage.getItem('app-graph-repulsion')) || 150) : 3000;
      return newVal;
    });
    setLinkDistance(prev => {
      const newVal = prev >= 200 ? (Number(localStorage.getItem('app-graph-link-dist')) || 30) : 350;
      return newVal;
    });
    if (!freezeLayout) {
      setTimeout(() => fgRef.current?.d3ReheatSimulation(), 50);
    }
  };

  const clearFocus = () => {
    setSelectedNodeId(null);
    setSearch('');
    setMinDegree(0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr 1fr', gap: '0.7rem', alignItems: 'center' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t.graphSearchPlaceholder}
          style={{ width: '100%', padding: '0.6rem 0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', background: 'var(--bg-surface)', color: 'var(--text-primary)' }}
        />
        <select
          value={String(minDegree)}
          onChange={(e) => setMinDegree(Number(e.target.value))}
          style={{ width: '100%', padding: '0.6rem 0.6rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', background: 'var(--bg-surface)', color: 'var(--text-primary)' }}
        >
          <option value="0">{t.graphDegreeFilter}: 0+</option>
          <option value="2">{t.graphDegreeFilter}: 2+</option>
          <option value="5">{t.graphDegreeFilter}: 5+</option>
          <option value="10">{t.graphDegreeFilter}: 10+</option>
          <option value="20">{t.graphDegreeFilter}: 20+</option>
        </select>
        <button
          onClick={() => setFreezeLayout((v) => !v)}
          style={{ padding: '0.6rem 0.8rem', background: freezeLayout ? 'var(--accent-warning)' : 'var(--bg-surface-hover)', color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', cursor: 'pointer' }}
        >
          {freezeLayout ? t.graphUnfreeze : t.graphFreeze}
        </button>
        <button
          onClick={handleZoomToFit}
          style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-surface-hover)', color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', cursor: 'pointer' }}
        >
          {t.graphZoomFit}
        </button>
        <button
          onClick={handleExpandGraph}
          style={{ padding: '0.6rem 0.8rem', background: repulsionStrength >= 2000 ? 'var(--accent-primary)' : 'var(--bg-surface-hover)', color: repulsionStrength >= 2000 ? 'white' : 'var(--text-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', cursor: 'pointer' }}
        >
          {repulsionStrength >= 2000 ? t.graphCollapse : t.graphExpand}
        </button>
        <button
          onClick={clearFocus}
          style={{ padding: '0.6rem 0.8rem', background: 'var(--bg-surface-hover)', color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', cursor: 'pointer' }}
        >
          {t.graphClearFocus}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <button onClick={() => fetchGraphData('default')} style={{ padding: '0.5rem 1rem', background: 'var(--bg-surface-hover)', color: 'var(--text-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', cursor: 'pointer' }}>
          {t.graphApplyPhysics}
        </button>
        <button onClick={() => fetchGraphData('pagerank')} style={{ padding: '0.5rem 1rem', background: 'var(--accent-primary)', color: 'white', borderRadius: 'var(--radius-md)', border: 'none', fontWeight: 600, cursor: 'pointer' }}>
          {t.graphRunPagerank}
        </button>
        <div style={{ flex: 1 }}></div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
          {t.graphResultCount}: {filteredData.nodes.length} {t.graphNodes}, {filteredData.links.length} {t.graphLinks}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#3b82f6' }}></span> {t.graphHub}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#64748b' }}></span> {t.graphStandard}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }}></span> {t.graphHighRisk}
          </span>
        </div>
      </div>

      <div className="card" ref={containerRef} style={{ flex: 1, padding: 0, overflow: 'hidden', position: 'relative' }}>
        {data.nodes.length > 0 && (
          <ForceGraph2D
            ref={fgRef}
            d3AlphaDecay={freezeLayout ? 1 : 0.0228}
            d3VelocityDecay={freezeLayout ? 1 : 0.4}
            width={dimensions.width}
            height={dimensions.height}
            graphData={filteredData}
            nodeColor={getNodeColor}
            nodeRelSize={4}
            linkColor={(link: any) => {
              const source = getId(link.source);
              const target = getId(link.target);
              const linkedToFocus = highlightedIds.has(source) && highlightedIds.has(target);
              const isLight = document.documentElement.getAttribute('data-theme') === 'light';

              if (selectedNodeId || search.trim()) {
                return linkedToFocus ? (isLight ? 'rgba(37,99,235,0.45)' : 'rgba(96,165,250,0.45)') : (isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)');
              }
              return isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
            }}
            linkWidth={link => link.value}
            backgroundColor={document.documentElement.getAttribute('data-theme') === 'light' ? '#ffffff' : '#0f1623'}
            onNodeClick={(node: any) => setSelectedNodeId(String(node.id))}
            nodeCanvasObjectMode={() => 'after'}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.name as string;
              const fontSize = 12 / globalScale;
              ctx.font = `${fontSize}px Inter, Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              const isLight = document.documentElement.getAttribute('data-theme') === 'light';
              ctx.fillStyle = node.group === 3 ? (isLight ? 'rgba(220,38,38,0.9)' : 'rgba(239,68,68,0.8)') : (isLight ? 'rgba(15,23,42,0.8)' : 'rgba(255,255,255,0.8)');
              if (node.val > 4) {
                 ctx.fillText(label, node.x!, node.y! + 8);
              }
            }}
          />
        )}
      </div>
    </div>
  );
}
