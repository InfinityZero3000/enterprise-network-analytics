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

export type InvestigationReportRequest = {
  entity_name: string;
  entity_id?: string;
  alert_type: string;
  evidence?: string;
};

export type InvestigationReportResponse = {
  entity_name: string;
  alert_type: string;
  report: string;
  signals: {
    subgraph_nodes: number;
    subgraph_links: number;
    blast_radius: {
      source: string;
      impacted_nodes: number;
      impacted_sample: string[];
      medium_risk_hits: number;
      high_risk_hits: number;
      risk_ratio: number;
    };
    shortest_risk_path: {
      start: string;
      target: string | null;
      hops: number | null;
      nodes: string[];
      edges: string[];
    };
  };
};

export const getInvestigationReport = async (
  payload: InvestigationReportRequest,
): Promise<InvestigationReportResponse> => {
  const response = await apiClient.post('/ai/investigation/report', payload);
  return response.data as InvestigationReportResponse;
};

export type InvestigationGraph = {
  nodes: Array<{
    id: string;
    name: string;
    group: number;
    risk?: number;
    labels?: string[];
  }>;
  links: Array<{
    source: string;
    target: string;
    label: string;
    weight?: number;
  }>;
};

export const getInvestigationSubgraph = async (
  entityName: string,
  alertType: string,
  maxHops = 2,
  entityId?: string,
): Promise<InvestigationGraph> => {
  const response = await apiClient.get('/graph/investigation/subgraph', {
    params: {
      entity_name: entityName,
      entity_id: entityId,
      alert_type: alertType,
      max_hops: maxHops,
    },
  });
  return response.data as InvestigationGraph;
};

export type RiskPathResult = {
  start: string;
  target: string | null;
  hops: number | null;
  nodes: string[];
  edges: string[];
};

export const getShortestRiskPath = async (entityName: string, entityId?: string): Promise<RiskPathResult> => {
  const response = await apiClient.get('/graph/investigation/shortest-risk-path', {
    params: {
      entity_name: entityName,
      entity_id: entityId,
    },
  });
  return response.data as RiskPathResult;
};

export type BlastRadiusResult = {
  source: string;
  impacted_nodes: number;
  impacted_sample: string[];
  medium_risk_hits: number;
  high_risk_hits: number;
  risk_ratio: number;
};

export const getBlastRadius = async (entityName: string, entityId?: string): Promise<BlastRadiusResult> => {
  const response = await apiClient.get('/graph/investigation/blast-radius', {
    params: {
      entity_name: entityName,
      entity_id: entityId,
    },
  });
  return response.data as BlastRadiusResult;
};

export type CaseStatus = 'NEW' | 'INVESTIGATING' | 'FALSE_POSITIVE' | 'CONFIRMED_FRAUD';

export type InvestigationCase = {
  case_id: string;
  entity_id: string;
  entity_name: string;
  alert_type: string;
  status: CaseStatus;
  note: string;
  created_at: string;
  updated_at: string;
  snapshots: Array<{
    snapshot_id: string;
    note: string;
    graph_node_count: number;
    graph_link_count: number;
    image_data_url?: string | null;
    created_at: string;
  }>;
};

export const createInvestigationCase = async (payload: {
  entity_id: string;
  entity_name: string;
  alert_type: string;
  note?: string;
}): Promise<InvestigationCase> => {
  const response = await apiClient.post('/analytics/cases', payload);
  return response.data as InvestigationCase;
};

export const updateInvestigationCaseStatus = async (
  caseId: string,
  status: CaseStatus,
): Promise<InvestigationCase> => {
  const response = await apiClient.patch(`/analytics/cases/${caseId}/status`, { status });
  return response.data as InvestigationCase;
};

export const saveInvestigationSnapshot = async (
  caseId: string,
  payload: {
    note: string;
    graph_node_count: number;
    graph_link_count: number;
    image_data_url?: string;
  },
) => {
  const response = await apiClient.post(`/analytics/cases/${caseId}/snapshots`, payload);
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
