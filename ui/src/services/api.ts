import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getFraudAlerts = async () => {
  const response = await apiClient.get('/analytics/fraud/alerts');
  return response.data;
};

export const askAi = async (question: string) => {
  const response = await apiClient.post('/ai/ask', { question });
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
