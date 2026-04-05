import axios from 'axios';

const getApiBaseUrl = () => {
  const url = localStorage.getItem('app-api-url') || 'http://localhost:8000';
  return `${url}/api/v1`;
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Update base URL dynamically when requests are made if it changed
apiClient.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

export const getFraudAlerts = async (limit?: number) => {
  const response = await apiClient.get('/analytics/fraud/alerts', {
    params: limit ? { limit } : {},
  });
  return response.data;
};

export const askAi = async (question: string, pageContext?: string) => {
  const response = await apiClient.post('/ai/ask', {
    question,
    page_context: pageContext,
  });
  return response.data;
};

export const getTopEntities = async () => {
  const response = await apiClient.get('/graph/top-entities');
  return response.data;
};

export const getGlobalStats = async () => {
  const response = await apiClient.get('/analytics/stats');
  return response.data;
};

export default apiClient;
