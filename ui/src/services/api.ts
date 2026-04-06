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

export const updateAiSettings = async (settings: any) => {
  const response = await apiClient.post('/ai/settings', settings);
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

export type CrawlSource = {
  id: string;
  name: string;
  url: string;
  license: string;
  data: string[];
  requires_api_key: boolean;
  env_var: string | null;
};

export type CrawlSourcesResponse = {
  sources: CrawlSource[];
};

export const listCrawlSources = async (): Promise<CrawlSourcesResponse> => {
  const response = await apiClient.get('/crawl/sources');
  return response.data as CrawlSourcesResponse;
};

export type CrawlRunPayload = {
  sources: string[];
  parallel: boolean;
  source_options?: Record<string, Record<string, unknown>>;
};

export type CrawlEtlRunPayload = {
  sources: string[];
  parallel: boolean;
  dry_run: boolean;
  source_options?: Record<string, Record<string, unknown>>;
};

export const runCrawlSync = async (payload: CrawlRunPayload) => {
  const response = await apiClient.post('/crawl/run/sync', payload);
  return response.data;
};

export const runCrawlEtlSync = async (payload: CrawlEtlRunPayload) => {
  const response = await apiClient.post('/crawl/etl/run/sync', payload);
  return response.data;
};

export default apiClient;
