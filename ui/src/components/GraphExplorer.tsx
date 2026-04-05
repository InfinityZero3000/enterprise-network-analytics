import { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

// Generate some nice dummy graph data representing enterprise network
const generateData = () => {
  const nodes = [];
  const links = [];
  const NUM_NODES = 120;
  
  // Create Main hubs (Companies)
  for (let i = 0; i < 5; i++) {
    nodes.push({ id: `hub-${i}`, group: 1, name: `Corp Hub ${i}`, val: 8 });
  }

  // Create Sub nodes
  for (let i = 0; i < NUM_NODES; i++) {
    const isRisky = Math.random() > 0.9;
    nodes.push({ 
      id: i.toString(), 
      group: isRisky ? 3 : 2, // 3 is risk
      name: isRisky ? `Shell Corp ${i}` : `Entity ${i}`,
      val: Math.random() * 3 + 1
    });

    // Link to a hub
    links.push({
      source: i.toString(),
      target: `hub-${Math.floor(Math.random() * 5)}`,
      value: Math.random() > 0.5 ? 2 : 1
    });

    // Link to another random node
    if (Math.random() > 0.7) {
      links.push({
        source: i.toString(),
        target: Math.floor(Math.random() * i).toString(),
        value: 1
      });
    }
  }

  return { nodes, links };
};

export default function GraphExplorer() {
  const [data, setData] = useState<{nodes: any[], links: any[]}>({ nodes: [], links: [] });
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setData(generateData());
  }, []);

  useEffect(() => {
    // Responsive canvas
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    
    window.addEventListener('resize', updateDimensions);
    // slight delay to ensure layout is done
    setTimeout(updateDimensions, 100);
    
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const getNodeColor = (node: any) => {
    if (node.group === 1) return '#3b82f6'; // primary cyan/blue
    if (node.group === 3) return '#ef4444'; // danger red
    return '#64748b'; // secondary slate
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '1rem' }}>
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <button style={{ 
          padding: '0.5rem 1rem', 
          background: 'var(--bg-surface-hover)', 
          color: 'var(--text-primary)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-light)'
        }}>
          Apply Layout Physics
        </button>
        <button style={{ 
          padding: '0.5rem 1rem', 
          background: 'var(--accent-primary)', 
          color: 'white',
          borderRadius: 'var(--radius-md)',
          border: 'none',
          fontWeight: 600
        }}>
          Run PageRank
        </button>
        <div style={{ flex: 1 }}></div>
        <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#3b82f6' }}></span> Hub
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#64748b' }}></span> Standard
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }}></span> High Risk
          </span>
        </div>
      </div>

      <div className="card" ref={containerRef} style={{ flex: 1, padding: 0, overflow: 'hidden', position: 'relative' }}>
        {data.nodes.length > 0 && (
          <ForceGraph2D
            width={dimensions.width}
            height={dimensions.height}
            graphData={data}
            nodeColor={getNodeColor}
            nodeRelSize={4}
            linkColor={() => 'rgba(255,255,255,0.1)'}
            linkWidth={link => link.value}
            backgroundColor="#0f1623" // var(--bg-surface-elevated) literal
            nodeCanvasObjectMode={() => 'after'}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.name as string;
              const fontSize = 12 / globalScale;
              ctx.font = `${fontSize}px Inter, Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = node.group === 3 ? 'rgba(239, 68, 68, 0.8)' : 'rgba(255, 255, 255, 0.8)';
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
