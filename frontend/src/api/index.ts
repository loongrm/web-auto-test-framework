import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ─── 测试执行 ────────────────────────────────────────────
export const runTests = (params: {
    module: string
    markers?: string
    env: string
}) => api.post('/runner/run', params).then(r => r.data)

export const getTaskStatus = (taskId: string) =>
    api.get(`/runner/status/${taskId}`).then(r => r.data)

// ─── 报告数据 ────────────────────────────────────────────
export const getDashboard = () =>
    api.get('/reports/dashboard').then(r => r.data)

export const getRuns = (limit = 20) =>
    api.get(`/reports/runs?limit=${limit}`).then(r => r.data)

// ─── AI 功能 ─────────────────────────────────────────────
export const analyzeFailure = (data: {
    error_log: string
    test_code?: string
    test_case_name?: string
}) => api.post('/ai/analyze-failure-json', data).then(r => r.data)

export const generateCases = (data: {
    user_story: string
    case_type: 'ui' | 'api'
}) => api.post('/ai/generate-cases', data).then(r => r.data)

export const healLocator = (data: {
    broken_selector: string
    page_html: string
    element_purpose?: string
}) => api.post('/ai/heal-locator', data).then(r => r.data)

export const getAIStatus = () =>
    api.get('/ai/status').then(r => r.data)