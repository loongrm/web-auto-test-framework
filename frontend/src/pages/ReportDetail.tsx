import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    Card, Table, Tag, Button, Drawer, Descriptions, Alert, Spin,
    Space, Typography, Collapse, Image, Divider, Empty, Tooltip,
} from 'antd'
import {
    ArrowLeftOutlined, BulbOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
    getRunDetail, getFailedCases, analyzeFailure,
    type TestRunSummary, type FailedCase, type AIAnalysisResult,
} from '../api'

const { Text, Paragraph } = Typography
const { Panel } = Collapse

export default function ReportDetail() {
    const { runId } = useParams<{ runId: string }>()
    const navigate = useNavigate()
    const [run, setRun] = useState<TestRunSummary | null>(null)
    const [cases, setCases] = useState<FailedCase[]>([])
    const [loading, setLoading] = useState(true)
    const [drawerOpen, setDrawerOpen] = useState(false)
    const [selected, setSelected] = useState<FailedCase | null>(null)
    const [aiResult, setAiResult] = useState<AIAnalysisResult | null>(null)
    const [aiLoading, setAiLoading] = useState(false)

    useEffect(() => {
        if (!runId) return
        const id = parseInt(runId)
        Promise.all([getRunDetail(id), getFailedCases(id)])
            .then(([r, c]) => { setRun(r); setCases(c) })
            .finally(() => setLoading(false))
    }, [runId])

    const openDrawer = (record: FailedCase) => {
        setSelected(record)
        setAiResult(null)
        setDrawerOpen(true)
        // 如果已有缓存的AI分析
        if (record.ai_analysis) {
            try {
                setAiResult(JSON.parse(record.ai_analysis))
            } catch { /* ignore */ }
        }
    }

    const doAIAnalyze = async () => {
        if (!selected) return
        setAiLoading(true)
        try {
            const r = await analyzeFailure({
                error_log: selected.error_message || '',
                test_case_name: selected.name,
                run_id: run?.id,
                case_id: selected.id,
            })
            setAiResult(r)
        } finally {
            setAiLoading(false)
        }
    }

    const typeColor: Record<string, string> = {
        element_not_found: 'orange', timeout: 'red', assertion_error: 'volcano',
        network_error: 'blue', environment_issue: 'purple',
        application_bug: 'magenta', test_data_issue: 'gold', unknown: 'default',
    }

    const columns = [
        { title: '#', dataIndex: 'id', width: 55 },
        {
            title: '用例名称', dataIndex: 'name', ellipsis: true,
            render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
        },
        { title: '模块', dataIndex: 'module', width: 80 },
        {
            title: '状态', dataIndex: 'status', width: 80,
            render: (s: string) => (
                <Tag color={s === 'failed' ? 'error' : s === 'passed' ? 'success' : 'default'}>{s}</Tag>
            ),
        },
        {
            title: '耗时(s)', dataIndex: 'duration', width: 80,
            render: (v: number) => v?.toFixed(2),
        },
        {
            title: '错误摘要', dataIndex: 'error_message', ellipsis: true,
            render: (v: string) => v ? (
                <Text type="danger" style={{ fontSize: 12 }}>{v?.substring(0, 80)}...</Text>
            ) : '-',
        },
        {
            title: 'AI分析', dataIndex: 'ai_analysis', width: 80,
            render: (v: string) => v ? <Tag color="purple">已分析</Tag> : <Tag>未分析</Tag>,
        },
        {
            title: '操作', key: 'action', width: 80,
            render: (_: unknown, row: FailedCase) => (
                <Button size="small" type="link" onClick={() => openDrawer(row)}>
                    详情
                </Button>
            ),
        },
    ]

    if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />

    return (
        <div>
            {/* 顶部导航 */}
            <Space style={{ marginBottom: 16 }}>
                <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/dashboard')}>
                    返回看板
                </Button>
                <Button
                    type="primary" icon={<BulbOutlined />}
                    onClick={() => navigate(`/reports/${runId}/summary`)}
                >
                    AI 执行摘要
                </Button>
            </Space>

            {/* 运行信息 */}
            {run && (
                <Card style={{ marginBottom: 16 }}>
                    <Descriptions size="small" column={4} bordered>
                        <Descriptions.Item label="运行ID">{run.id}</Descriptions.Item>
                        <Descriptions.Item label="模块">{run.module}</Descriptions.Item>
                        <Descriptions.Item label="环境">
                            <Tag color="blue">{run.env}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="状态">
                            <Tag color={run.status === 'success' ? 'success' : 'error'}>{run.status}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="通过率">{run.pass_rate}%</Descriptions.Item>
                        <Descriptions.Item label="总数">{run.total}</Descriptions.Item>
                        <Descriptions.Item label="通过">
                            <Text style={{ color: '#52c41a' }}>{run.passed}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="失败">
                            <Text style={{ color: '#f5222d' }}>{run.failed}</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label="开始时间" span={2}>
                            {run.start_time ? new Date(run.start_time).toLocaleString('zh-CN') : '-'}
                        </Descriptions.Item>
                        <Descriptions.Item label="耗时(s)" span={2}>
                            {run.duration?.toFixed(1)}
                        </Descriptions.Item>
                    </Descriptions>
                </Card>
            )}

            {/* 失败用例表 */}
            <Card
                title={
                    <Space>
                        <ExclamationCircleOutlined style={{ color: '#f5222d' }} />
                        <span>失败用例列表（{cases.length} 条）</span>
                    </Space>
                }
            >
                {cases.length === 0 ? (
                    <Empty description="没有失败用例，或尚未解析 Allure 结果" />
                ) : (
                    <Table
                        dataSource={cases}
                        columns={columns}
                        rowKey="id"
                        size="small"
                        pagination={{ pageSize: 15 }}
                    />
                )}
            </Card>

            {/* 失败详情 Drawer */}
            <Drawer
                title={
                    <Space>
                        <Tag color="error">FAILED</Tag>
                        <Text style={{ fontSize: 13 }}>{selected?.name}</Text>
                    </Space>
                }
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                width={680}
                extra={
                    <Button
                        type="primary" icon={<BulbOutlined />}
                        loading={aiLoading} onClick={doAIAnalyze}
                    >
                        AI 分析
                    </Button>
                }
            >
                {selected && (
                    <>
                        {/* 截图 */}
                        {selected.screenshot_path && (
                            <>
                                <Divider orientation="left">失败截图</Divider>
                                <Image
                                    src={`/screenshots/${selected.screenshot_path.split('/').pop()}`}
                                    alt="失败截图"
                                    style={{ maxWidth: '100%', borderRadius: 6 }}
                                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                                />
                            </>
                        )}

                        {/* 错误日志 */}
                        <Divider orientation="left">错误日志</Divider>
                        <pre style={{
                            background: '#1a1a1a', color: '#ff6b6b', padding: 12,
                            borderRadius: 6, fontSize: 12, maxHeight: 240, overflow: 'auto',
                            whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                        }}>
                            {selected.error_message || '（无错误信息）'}
                        </pre>

                        {/* AI 分析结果 */}
                        {aiLoading && <Spin tip="AI 分析中..." style={{ display: 'block', margin: '24px auto' }} />}

                        {aiResult && (
                            <>
                                <Divider orientation="left">AI 分析结果</Divider>
                                {!aiResult.available ? (
                                    <Alert type="warning" message="AI 服务不可用，请配置 OPENAI_API_KEY" />
                                ) : (
                                    <Descriptions bordered size="small" column={1}>
                                        <Descriptions.Item label="失败类型">
                                            <Tag color={typeColor[aiResult.failure_type] || 'default'}>
                                                {aiResult.failure_type}
                                            </Tag>
                                        </Descriptions.Item>
                                        <Descriptions.Item label="根本原因">
                                            {aiResult.root_cause}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="修复建议">
                                            <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 13 }}>
                                                {aiResult.suggestion}
                                            </Paragraph>
                                        </Descriptions.Item>
                                        <Descriptions.Item label="置信度">
                                            {Math.round(aiResult.confidence * 100)}%
                                        </Descriptions.Item>
                                        <Descriptions.Item label="是否 Flaky">
                                            <Tag color={aiResult.is_flaky ? 'orange' : 'green'}>
                                                {aiResult.is_flaky ? `是 — ${aiResult.flaky_reason}` : '否'}
                                            </Tag>
                                        </Descriptions.Item>
                                    </Descriptions>
                                )}
                            </>
                        )}
                    </>
                )}
            </Drawer>
        </div>
    )
}