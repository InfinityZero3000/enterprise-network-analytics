import { useState } from 'react';
import { askAi } from '../services/api';

export default function AIAssistant() {
  const [query, setQuery] = useState('');
  const [chatLog, setChatLog] = useState<{role: 'user' | 'ai', content: string}[]>([
    { role: 'ai', content: 'Xin chào, tôi là AI hỗ trợ phân tích mạng lưới doanh nghiệp. Bạn muốn truy vấn gì?' }
  ]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    if (!query.trim()) return;
    const currentQ = query;
    setQuery('');
    setChatLog(prev => [...prev, { role: 'user', content: currentQ }]);
    setLoading(true);

    try {
      const res = await askAi(currentQ);
      setChatLog(prev => [...prev, { role: 'ai', content: res.answer || 'Completed.' }]);
    } catch (e) {
      setChatLog(prev => [...prev, { role: 'ai', content: 'Lỗi kết nối đến AI service. (Demo mode)' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-lg)', background: 'var(--bg-surface)', overflow: 'hidden' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-light)', background: 'var(--bg-surface-elevated)', fontWeight: 600 }}>
        Enterprise GenAI Assistant
      </div>
      
      <div style={{ flex: 1, padding: '1rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {chatLog.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{ 
              maxWidth: '80%', 
              padding: '0.75rem 1rem', 
              borderRadius: 'var(--radius-md)', 
              background: msg.role === 'user' ? 'var(--accent-primary)' : 'var(--bg-base)',
              color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
              lineHeight: 1.5
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
             <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', background: 'var(--bg-base)', color: 'var(--text-muted)' }}>
               Agent is thinking...
             </div>
          </div>
        )}
      </div>

      <div style={{ padding: '1rem', borderTop: '1px solid var(--border-light)', display: 'flex', gap: '0.5rem' }}>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
          placeholder="Hỏi về sở hữu chéo, độ rủi ro..." 
          style={{ 
            flex: 1, 
            padding: '0.75rem', 
            borderRadius: 'var(--radius-sm)', 
            border: '1px solid var(--border-light)', 
            background: 'var(--bg-base)', 
            color: 'var(--text-primary)',
            outline: 'none'
          }} 
        />
        <button 
          onClick={handleAsk}
          style={{ padding: '0 1.5rem', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', fontWeight: 600 }}>
          Gửi
        </button>
      </div>
    </div>
  );
}
