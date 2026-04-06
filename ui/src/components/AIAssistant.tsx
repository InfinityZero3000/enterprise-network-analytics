import { useEffect, useState } from 'react';
import { askAi } from '../services/api';
import { translations, type Lang } from '../i18n';

type Props = {
  lang: Lang;
  pageContext?: string;
  compact?: boolean;
  seedPrompt?: string;
  autoSendSeed?: boolean;
  onSeedConsumed?: () => void;
};

export default function AIAssistant({
  lang,
  pageContext,
  compact = false,
  seedPrompt,
  autoSendSeed = false,
  onSeedConsumed,
}: Props) {
  const t = translations[lang];
  const [query, setQuery] = useState('');
  const [chatLog, setChatLog] = useState<{role: 'user' | 'ai', content: string}[]>([
    { role: 'ai', content: t.aiWelcome }
  ]);
  const [loading, setLoading] = useState(false);
  const [lastSeed, setLastSeed] = useState('');

  const sanitizeAiText = (text: string): string => {
    return text
      // Bold/italic markdown markers
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      // Bullet markers that start with '* '
      .replace(/^\s*\*\s+/gm, '')
      // Any remaining lone asterisks
      .replace(/\*/g, '')
      .trim();
  };

  useEffect(() => {
    if (chatLog.length === 1 && chatLog[0].role === 'ai') {
      setChatLog([{ role: 'ai', content: t.aiWelcome }]);
    }
  }, [lang]);

  const sendQuestion = async (question: string) => {
    const currentQ = question.trim();
    if (!currentQ) return;
    setQuery('');
    setChatLog(prev => [...prev, { role: 'user', content: currentQ }]);
    setLoading(true);

    try {
      const res = await askAi(currentQ, pageContext);
      const cleaned = sanitizeAiText(res.answer || 'Completed.');
      setChatLog(prev => [...prev, { role: 'ai', content: cleaned }]);
    } catch (e) {
      setChatLog(prev => [...prev, { role: 'ai', content: t.aiConnectionError }]);
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = async () => {
    await sendQuestion(query);
  };

  useEffect(() => {
    if (!seedPrompt || !seedPrompt.trim()) {
      return;
    }
    if (seedPrompt === lastSeed) {
      return;
    }
    setLastSeed(seedPrompt);
    if (autoSendSeed) {
      void sendQuestion(seedPrompt);
    } else {
      setQuery(seedPrompt);
    }
    onSeedConsumed?.();
  }, [seedPrompt, autoSendSeed, lastSeed, onSeedConsumed]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-lg)', background: 'var(--bg-surface)', overflow: 'hidden' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-light)', background: 'var(--bg-surface-elevated)', fontWeight: 600 }}>
        {compact ? t.quickChat : t.aiTitle}
      </div>

      {pageContext && (
        <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-light)', background: 'rgba(59, 130, 246, 0.08)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{t.contextNow}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{pageContext}</div>
        </div>
      )}
      
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
               {t.aiThinking}
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
          placeholder={compact ? t.askAboutView : t.aiPlaceholder}
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
          {t.aiSend}
        </button>
      </div>
    </div>
  );
}
