import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    Card, Button, Alert, Spin, Tag, Space, Typography,
    List, Divider, Row, Col, Statistic, Tooltip,
} from 'antd'
import {
    ArrowLeftOutlined, RobotOutlined, ReloadOutlined,
    WarningOutlined, BulbOutlined, CheckCircleOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons'
import { getAISummary, getRunDetail, type AISummary, type TestRunSummary } from '../api'

const { Title, Paragraph, Text } = Typography

const riskColor: Record<string, string> = {
    high: 'red', medium: 'orange', low: 'green', unknown: 'default',
}
const riskLabel: Record<string, string> = {
    high: '⚠️ 高风险', medium: '⚡ 中等风险', low: '✅ 低风险', unknown: '未知',
}

export default function ReportSummary() {
    const { runId } = useParams<{ runId: string }>()
    const navigate = useNavigate()
    const [run, setRun] = useState<TestRunSummary | null>(null)
    const [summary, setSummary] = useState<AISummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [regenerating, setRegenerating] = useState(false)

    const fetchSummary = async (forceRegenerate = false) => {
        if (!runId) return
        const id = parseInt(runId)
        if (forceRegenerate) {
            setRegenerating(true)
            setSummary(null)
        }
        try {
            const [r, s] = await Promise.all([
                getRunDetail(id),
                getAISummary(id),
            ])
            setRun(r)
            setSummary(s)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
            setRegenerating(false)
        }
    }

    // 强制重新生成：清除数据库缓存后再请求
    const handleRegenerate = async () => {
        if (!runId) return
        setRegenerating(true)
        setSummary(null)
        try {
            // 调用清除缓存接口，然后重新拉取
            await fetch(`/api/reports/runs/${runId}/ai-summary/clear`, { method: 'POST' })
        } catch {
            // 即使接口不存在也继续
        }
        await fetchSummary(false)
    }

    useEffect(() => { fetchSummary() }, [runId])

    if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />

    return (
        <div>
            {/* 顶部操作栏 */}
            <Space style={{ marginBottom: 16 }}>
                <Button
                    icon={<ArrowLeftOutlined />}
                    onClick={() => navigate(`/reports/${runId}`)}
                >
                    返回失败详情
                </Button>
                <Tooltip title="清除缓存并重新调用 AI 生成摘要">
                    <Button
                        icon={<ReloadOutlined />}
                        loading={regenerating}
                        onClick={handleRegenerate}
                    >
                        重新生成摘要
                    </Button>
                </Tooltip>
                {summary?.cached && (
                    <Tag
                        icon={<ThunderboltOutlined />}
                        color="default"
                        style={{ cursor: 'default' }}
                    >
                        来自缓存（点击"重新生成"获取最新）
                    </Tag>
                )}
            </Space>

            {/* 运行基本数据 */}
            {run && (
                <Row gutter={16} style={{ marginBottom: 24 }}>
                    {[
                        {
                            title: '通过率',
                            value: run.pass_rate,
                            suffix: '%',
                            color: run.pass_rate >= 80 ? '#52c41a' : '#f5222d',
                        },
                        { title: '通过', value: run.passed, color: '#52c41a' },
                        {
                            title: '失败',
                            value: run.failed,
                            color: run.failed ? '#f5222d' : '#333',
                        },
                        { title: '耗时(s)', value: run.duration?.toFixed(1) },
                    ].map(item => (
                        <Col span={6} key={item.title}>
                            <Card size="small">
                                <Statistic
                                    title={item.title}
                                    value={item.value as number}
                                    suffix={item.suffix}
                                    valueStyle={{ color: item.color }}
                                />
                            </Card>
                        </Col>
                    ))}
                </Row>
            )}

            {/* AI 摘要卡片 */}
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

                {!regenerating && !summary?.available && (
                    <Alert
                        type="warning"
                        message="AI 服务不可用"
                        description={
                            <div>
                                请在 <code>.env</code> 中配置 <code>OPENAI_API_KEY</code>，
                                然后重启后端服务并点击"重新生成摘要"。
                            </div>
                        }
                    />
                )}

                {!regenerating && summary?.available && (
                    <>
                        <Divider orientation="left">
                            <Space><BulbOutlined />总结</Space>
                        </Divider>
                        <Paragraph style={{ fontSize: 14, lineHeight: 1.8, color: '#333' }}>
                            {summary.summary || '（摘要内容为空，请点击重新生成）'}
                        </Paragraph>

                        <Divider orientation="left">风险评估</Divider>
                        <Space>
                            <Text>当前风险等级：</Text>
                            <Tag
                                color={riskColor[summary.risk_level] || 'default'}
                                style={{ fontSize: 14, padding: '2px 12px' }}
                            >
                                {riskLabel[summary.risk_level] || summary.risk_level}
                            </Tag>
                        </Space>

                        {summary.key_issues?.length > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space>
                                        <WarningOutlined style={{ color: '#f5222d' }} />
                                        关键问题
                                    </Space>
                                </Divider>
                                <List
                                    dataSource={summary.key_issues}
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

                        {summary.recommendations?.length > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space>
                                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                                        优化建议
                                    </Space>
                                </Divider>
                                <List
                                    dataSource={summary.recommendations}
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