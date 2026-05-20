import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    Card, Button, Alert, Spin, Tag, Space, Typography,
    List, Divider, Row, Col, Statistic, Tooltip,
} from 'antd'
import {
    ArrowLeftOutlined, RobotOutlined, ReloadOutlined,
    WarningOutlined, BulbOutlined, CheckCircleOutlined,
    ThunderboltOutlined, DollarOutlined,
} from '@ant-design/icons'
import { getAISummary, getRunDetail, type AISummary, type TestRunSummary } from '../api'

const { Paragraph, Text } = Typography

const riskColor: Record<string, string> = {
    high: 'red', medium: 'orange', low: 'green', unknown: 'default',
}
const riskLabel: Record<string, string> = {
    high: '⚠️ 高风险', medium: '⚡ 中等风险', low: '✅ 低风险', unknown: '未评估',
}

const billingUrl = 'https://platform.openai.com/settings/billing'

export default function ReportSummary() {
    const { runId } = useParams<{ runId: string }>()
    const navigate = useNavigate()
    const [run, setRun] = useState<TestRunSummary | null>(null)
    const [summary, setSummary] = useState<AISummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [regenerating, setRegenerating] = useState(false)

    const fetchSummary = async (forceNew = false) => {
        if (!runId) return
        const id = parseInt(runId)
        if (forceNew) {
            setRegenerating(true)
            setSummary(null)
            try {
                await fetch(`/api/reports/runs/${id}/ai-summary/clear`, { method: 'POST' })
            } catch {
                // ignore
            }
        }
        try {
            const [r, s] = await Promise.all([getRunDetail(id), getAISummary(id)])
            setRun(r)
            setSummary(s)
        } catch {
            // ignore
        } finally {
            setLoading(false)
            setRegenerating(false)
        }
    }

    useEffect(() => { fetchSummary() }, [runId])

    if (loading) {
        return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
    }

    const summaryText = summary?.summary ?? ''
    const isQuotaError = summaryText.includes('429') || summaryText.includes('quota') || summaryText.includes('insufficient')
    const isNoContent = summaryText.trim() === ''
    const isAvailable = summary?.available === true

    const QuotaDescription = (
        <div>
            <p style={{ margin: '8px 0' }}>
                当前 OpenAI 账户没有可用余额（HTTP 429 insufficient_quota），AI 功能暂时不可用。
            </p>
            <p style={{ margin: '8px 0' }}>
                解决方法：前往{' '}
                <a href={billingUrl} target="_blank" rel="noreferrer" style={{ color: '#1890ff' }}>
                    platform.openai.com/settings/billing
                </a>
                {' '}充值最低 $5，充值后点击「重新生成摘要」即可。
            </p>
        </div>
    )

    const KeyDescription = (
        <span>
            请在 <code>.env</code> 中配置 <code>OPENAI_API_KEY</code>，
            然后重启后端并点击「重新生成摘要」。
        </span>
    )

    return (
        <div>
            <Space style={{ marginBottom: 16 }} wrap>
                <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/reports/${runId}`)}>
                    返回失败详情
                </Button>
                <Tooltip title="清除缓存并重新调用 AI 生成">
                    <Button icon={<ReloadOutlined />} loading={regenerating} onClick={() => fetchSummary(true)}>
                        重新生成摘要
                    </Button>
                </Tooltip>
                {summary?.cached && (
                    <Tag icon={<ThunderboltOutlined />} color="default">来自缓存</Tag>
                )}
            </Space>

            {run && (
                <Row gutter={16} style={{ marginBottom: 24 }}>
                    {[
                        { title: '通过率', value: run.pass_rate, suffix: '%', color: run.pass_rate >= 80 ? '#52c41a' : '#f5222d' },
                        { title: '通过', value: run.passed, color: '#52c41a' },
                        { title: '失败', value: run.failed, color: run.failed ? '#f5222d' : '#333' },
                        { title: '耗时(s)', value: Number(run.duration?.toFixed(1)) },
                    ].map(item => (
                        <Col span={6} key={item.title}>
                            <Card size="small">
                                <Statistic
                                    title={item.title}
                                    value={item.value}
                                    suffix={item.suffix}
                                    valueStyle={{ color: item.color }}
                                />
                            </Card>
                        </Col>
                    ))}
                </Row>
            )}

            <Card
                title={
                    <Space>
                        <RobotOutlined style={{ color: '#722ed1' }} />
                        <span>AI 执行摘要</span>
                        {regenerating && <Tag color="processing">生成中...</Tag>}
                    </Space>
                }
            >
                {regenerating && (
                    <div style={{ textAlign: 'center', padding: 48 }}>
                        <Spin tip="AI 正在分析测试结果，请稍候..." size="large" />
                    </div>
                )}

                {!regenerating && isQuotaError && (
                    <Alert
                        type="warning"
                        icon={<DollarOutlined />}
                        message="OpenAI 账户余额不足"
                        description={QuotaDescription}
                    />
                )}

                {!regenerating && !isQuotaError && !isAvailable && (
                    <Alert
                        type="warning"
                        message="AI 服务不可用"
                        description={KeyDescription}
                    />
                )}

                {!regenerating && isAvailable && !isQuotaError && isNoContent && (
                    <Alert
                        type="info"
                        message="摘要内容为空"
                        description="AI 生成摘要失败或内容为空，请点击「重新生成摘要」重试。"
                    />
                )}

                {!regenerating && isAvailable && !isQuotaError && !isNoContent && (
                    <>
                        <Divider orientation="left">
                            <Space><BulbOutlined />总结</Space>
                        </Divider>
                        <Paragraph style={{ fontSize: 14, lineHeight: 1.8, color: '#333' }}>
                            {summaryText}
                        </Paragraph>

                        <Divider orientation="left">风险评估</Divider>
                        <Space>
                            <Text>当前风险等级：</Text>
                            <Tag
                                color={riskColor[summary?.risk_level ?? 'unknown'] ?? 'default'}
                                style={{ fontSize: 14, padding: '2px 12px' }}
                            >
                                {riskLabel[summary?.risk_level ?? 'unknown'] ?? '未评估'}
                            </Tag>
                        </Space>

                        {(summary?.key_issues?.length ?? 0) > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space>
                                        <WarningOutlined style={{ color: '#f5222d' }} />
                                        关键问题
                                    </Space>
                                </Divider>
                                <List
                                    dataSource={summary?.key_issues ?? []}
                                    renderItem={(issue: string, idx: number) => (
                                        <List.Item>
                                            <Space align="start">
                                                <Tag color="error">{idx + 1}</Tag>
                                                <Text>{issue}</Text>
                                            </Space>
                                        </List.Item>
                                    )}
                                />
                            </>
                        )}

                        {(summary?.recommendations?.length ?? 0) > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space>
                                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                                        优化建议
                                    </Space>
                                </Divider>
                                <List
                                    dataSource={summary?.recommendations ?? []}
                                    renderItem={(rec: string, idx: number) => (
                                        <List.Item>
                                            <Space align="start">
                                                <Tag color="green">{idx + 1}</Tag>
                                                <Text>{rec}</Text>
                                            </Space>
                                        </List.Item>
                                    )}
                                />
                            </>
                        )}
                    </>
                )}
            </Card>
        </div>
    )
}