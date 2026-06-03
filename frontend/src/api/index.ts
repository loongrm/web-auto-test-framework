import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// 类型定义
export interface RunRequest {
    module: string
    markers?: string
    env: string
    trigger?: string
}

export interface RunResponse {
    task_id: string
    run_id?: number
    status: string
    message: string
}

export interface TaskStatus {
    task_id: string
    status: string
    returncode?: number
    stdout?: string
    stderr?: string
    run_id?: number
    passed?: number
    failed?: number
    total?: number
}

export interface TestRunSummary {
    id: number
    name: string
    module: string
    env: string
    status: string
    start_time: string
    end_time?: string
    duration: number
    total: number
    passed: number
    failed: number
    skipped: number
    pass_rate: number
}

export interface DashboardData {
    stats: {
        total: number
        passed: number
        failed: number
        skipped: number
        pass_rate: number
    }
    trend: TrendPoint[]
    recent_runs: TestRunSummary[]
}

export interface TrendPoint {
    date: string
    passRate: number
    total: number
    passed: number
    failed: number
}

export interface FailedCase {
    id: number
    name: string
    module: string
    status: string
    duration: number
    error_message?: string
    screenshot_path?: string
    ai_analysis?: string
}

export interface AIAnalysisResult {
    root_cause: string
    failure_type: string
    suggestion: string
    confidence: number
    is_flaky: boolean
    flaky_reason: string
    available: boolean
}

export interface AISummary {
    run_id: number
    summary: string
    key_issues: string[]
    recommendations: string[]
    risk_level: string
    available: boolean
    cached: boolean
}

// 测试执行
export const runTests = (params: RunRequest): Promise<RunResponse> =>
    api.post<RunResponse>('/runner/run', params).then(res => res.data)

export const getTaskStatus = (taskId: string): Promise<TaskStatus> =>
    api.get<TaskStatus>(`/runner/status/${taskId}`).then(res => res.data)

// 报告数据
export const getDashboard = (): Promise<DashboardData> =>
    api.get<DashboardData>('/reports/dashboard').then(res => res.data)

export const getRuns = (limit = 20): Promise<{ runs: TestRunSummary[] }> =>
    api.get(`/reports/runs?limit=${limit}`).then(res => res.data)

export const getRunDetail = (runId: number): Promise<TestRunSummary> =>
    api.get<TestRunSummary>(`/reports/runs/${runId}`).then(res => res.data)

export const getFailedCases = (runId: number): Promise<FailedCase[]> =>
    api.get<FailedCase[]>(`/reports/runs/${runId}/failed-cases`).then(res => res.data)

export const getAISummary = (runId: number): Promise<AISummary> =>
    api.get<AISummary>(`/reports/runs/${runId}/ai-summary`).then(res => res.data)

export const getAIAnalysisHistory = (runId: number): Promise<AIAnalysisResult[]> =>
    api.get<AIAnalysisResult[]>(`/ai/history/${runId}`).then(res => res.data)

// AI功能
export const analyzeFailure = (data: {
    error_log: string
    test_code?: string
    test_case_name?: string
    run_id?: number
    case_id?: number
}): Promise<AIAnalysisResult> =>
    api.post<AIAnalysisResult>('/ai/analyze-failure-json', data).then(res => res.data)

export const getAIStatus = (): Promise<{ analyzer: boolean; generator: boolean; healer: boolean }> =>
    api.get('/ai/status').then(res => res.data)