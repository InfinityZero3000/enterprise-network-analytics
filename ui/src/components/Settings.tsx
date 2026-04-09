import { useState, useEffect } from 'react';
import { translations, type Lang } from '../i18n';
import { getResolvedApiRoot, updateAiSettings } from '../services/api';

interface SettingsProps {
  lang: Lang;
}

export default function Settings({ lang }: SettingsProps) {
  const t = translations[lang];

  const [apiUrl, setApiUrl] = useState(() => localStorage.getItem('app-api-url') || getResolvedApiRoot());
  const [nodeRepulsion, setNodeRepulsion] = useState(() => Number(localStorage.getItem('app-graph-repulsion')) || 150);
  const [linkDistance, setLinkDistance] = useState(() => Number(localStorage.getItem('app-graph-link-dist')) || 30);
  const [geminiApiKey, setGeminiApiKey] = useState(() => localStorage.getItem('app-ai-gemini-key') || '');
  const [geminiModel, setGeminiModel] = useState(() => localStorage.getItem('app-ai-gemini-model') || 'gemini-2.5-flash');
  const [groqApiKey, setGroqApiKey] = useState(() => localStorage.getItem('app-ai-groq-key') || '');
  const [groqModel, setGroqModel] = useState(() => localStorage.getItem('app-ai-groq-model') || 'llama-3.3-70b-versatile');
  const [openrouterApiKey, setOpenrouterApiKey] = useState(() => localStorage.getItem('app-ai-openrouter-key') || '');
  const [openrouterModel, setOpenrouterModel] = useState(() => localStorage.getItem('app-ai-openrouter-model') || 'openai/gpt-4o-mini');
  const [openaiApiKey, setOpenaiApiKey] = useState(() => localStorage.getItem('app-ai-openai-key') || '');
  const [isSaved, setIsSaved] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    localStorage.setItem('app-graph-repulsion', nodeRepulsion.toString());
    localStorage.setItem('app-graph-link-dist', linkDistance.toString());
    window.dispatchEvent(new Event('app-settings-changed'));
  }, [nodeRepulsion, linkDistance]);

  const handleSave = async () => {
    setSaveMessage('');
    setSaveError(false);

    localStorage.setItem('app-api-url', apiUrl);
    localStorage.setItem('app-graph-repulsion', nodeRepulsion.toString());
    localStorage.setItem('app-graph-link-dist', linkDistance.toString());
    localStorage.setItem('app-ai-gemini-key', geminiApiKey);
    localStorage.setItem('app-ai-gemini-model', geminiModel);
    localStorage.setItem('app-ai-groq-key', groqApiKey);
    localStorage.setItem('app-ai-groq-model', groqModel);
    localStorage.setItem('app-ai-openrouter-key', openrouterApiKey);
    localStorage.setItem('app-ai-openrouter-model', openrouterModel);
    localStorage.setItem('app-ai-openai-key', openaiApiKey);
    
    try {
      const response = await updateAiSettings({
        gemini_api_key: geminiApiKey,
        gemini_model: geminiModel,
        groq_api_key: groqApiKey,
        groq_model: groqModel,
        openrouter_api_key: openrouterApiKey,
        openrouter_model: openrouterModel,
        openai_api_key: openaiApiKey
      });

      const groqStatus = response?.groq_validation;
      if (groqApiKey.trim() && groqStatus && groqStatus.ok === false) {
        setSaveError(true);
        setSaveMessage(`Groq key không hợp lệ hoặc bị từ chối: ${groqStatus.error || 'unknown error'}`);
      } else {
        setSaveError(false);
        setSaveMessage(response?.message || t.settingsSaved);
      }
    } catch (e) {
      console.error("Failed to sync AI keys to backend", e);
      setSaveError(true);
      setSaveMessage('Không đồng bộ được AI settings lên backend. Kiểm tra API URL hoặc trạng thái backend.');
    }
    
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
    
    // Dispatch an event so other components (like GraphExplorer) can update if needed
    window.dispatchEvent(new Event('app-settings-changed'));
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', display: 'grid', gap: '1.5rem', paddingBottom: '2rem' }}>
      
      {/* API Configuration */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: '1rem' }}>{t.apiConfig}</div>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.apiUrl}</label>
          <input 
            type="text" 
            value={apiUrl}
            onChange={e => setApiUrl(e.target.value)}
            style={{
              width: '100%',
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-light)',
              background: 'var(--bg-base)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem'
            }}
          />
        </div>
      </div>

      {/* Graph Force Configuration */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: '1rem' }}>{t.graphConfig}</div>
        
        <div style={{ display: 'grid', gap: '1.5rem' }}>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
              {t.nodeRepulsion} <span>{nodeRepulsion}</span>
            </label>
            <input 
              type="range" 
              min="50" 
              max="1000" 
              step="10"
              value={nodeRepulsion}
              onChange={e => setNodeRepulsion(Number(e.target.value))}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
              {t.linkDistance} <span>{linkDistance} px</span>
            </label>
            <input 
              type="range" 
              min="10" 
              max="200" 
              step="5"
              value={linkDistance}
              onChange={e => setLinkDistance(Number(e.target.value))}
              style={{ width: '100%', cursor: 'pointer' }}
            />
          </div>
        </div>
      </div>

      {/* AI LLM Configuration */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: '1rem' }}>{t.aiConfig}</div>
        <div style={{ display: 'grid', gap: '1rem' }}>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.geminiApiKey}</label>
            <input
              type="password"
              value={geminiApiKey}
              onChange={e => setGeminiApiKey(e.target.value)}
              placeholder="AIza..."
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.geminiModel}</label>
            <input
              type="text"
              value={geminiModel}
              onChange={e => setGeminiModel(e.target.value)}
              placeholder="gemini-2.5-flash"
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.groqApiKey}</label>
            <input
              type="password"
              value={groqApiKey}
              onChange={e => setGroqApiKey(e.target.value)}
              placeholder="gsk_..."
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.groqModel}</label>
            <input
              type="text"
              value={groqModel}
              onChange={e => setGroqModel(e.target.value)}
              placeholder="llama-3.3-70b-versatile"
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.openaiApiKey}</label>
            <input
              type="password"
              value={openaiApiKey}
              onChange={e => setOpenaiApiKey(e.target.value)}
              placeholder="sk-..."
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.openrouterApiKey}</label>
            <input
              type="password"
              value={openrouterApiKey}
              onChange={e => setOpenrouterApiKey(e.target.value)}
              placeholder="sk-or-v1-..."
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{t.openrouterModel}</label>
            <input
              type="text"
              value={openrouterModel}
              onChange={e => setOpenrouterModel(e.target.value)}
              placeholder="openai/gpt-4o-mini"
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-light)',
                background: 'var(--bg-base)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem'
              }}
            />
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', paddingTop: '1rem' }}>
        <button 
          onClick={handleSave}
          style={{
            padding: '0.75rem 1.5rem',
            background: 'var(--accent-primary)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontWeight: 600,
            fontSize: '0.9rem'
          }}
        >
          {t.saveSettings}
        </button>

        {isSaved && (
          <span style={{ color: saveError ? 'var(--accent-danger)' : 'var(--accent-success)', fontSize: '0.9rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"></path></svg>
            {saveMessage || t.settingsSaved}
          </span>
        )}
      </div>

    </div>
  );
}