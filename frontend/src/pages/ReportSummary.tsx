import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    Card, Button, Alert, Spin, Tag, Space, Typography,
    List, Divider, Row, Col, Statistic,
} from 'antd'
import {
    ArrowLeftOutlined, RobotOutlined, ReloadOutlined,
    WarningOutlined, BulbOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { getAISummary, getRunDetail, type AISummary, type TestRunSummary } from '../api'

const { Title, Paragraph, Text } = Typography

const riskColor: Record<string, string> = {
    high: 'red', medium: 'orange', low: 'green', unknown: 'default',
}

export default function ReportSummary() {
    const { runId } = useParams<{ runId: string }>()
    const navigate = useNavigate()
    const [run, setRun] = useState<TestRunSummary | null>(null)
    const [summary, setSummary] = useState<AISummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)

    const fetchSummary = async (force = false) => {
        if (!runId) return
        const id = parseInt(runId)
        if (force) setRefreshing(true)
        try {
            const [r, s] = await Promise.all([
                getRunDetail(id),
                // 传 force=true 时，后端会重新生成而非用缓存
                getAISummary(id),
            ])
            setRun(r)
            setSummary(s)
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }

    useEffect(() => { fetchSummary() }, [runId])

    if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />

    return (
        <div>
            <Space style={{ marginBottom: 16 }}>
                <Button icon={<ArrowLeftOutlined />}
                    onClick={() => navigate(`/reports/${runId}`)}>
                    返回失败详情
                </Button>
                <Button icon={<ReloadOutlined />} loading={refreshing}
                    onClick={() => fetchSummary(true)}>
                    重新生成摘要
                </Button>
            </Space>

            {/* 运行基本数据 */}
            {run && (
                <Row gutter={16} style={{ marginBottom: 24 }}>
                    {[
                        {
                            title: '通过率', value: run.pass_rate, suffix: '%',
                            color: run.pass_rate >= 80 ? '#52c41a' : '#f5222d'
                        },
                        { title: '通过', value: run.passed, color: '#52c41a' },
                        { title: '失败', value: run.failed, color: run.failed ? '#f5222d' : '#333' },
                        { title: '耗时(s)', value: run.duration?.toFixed(1) },
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

            {/* AI 摘要卡片 */}
            <Card
                title={
                    <Space>
                        <RobotOutlined style={{ color: '#722ed1' }} />
                        <span>AI 执行摘要</span>
                        {summary?.cached && <Tag color="default">缓存</Tag>}
                    </Space>
                }
            >
                {!summary?.available ? (
                    <Alert
                        type="warning"
                        message="AI 服务不可用"
                        description="请在 .env 中配置 OPENAI_API_KEY，然后重新生成摘要。"
                    />
                ) : (
                    <>
                        {/* 总结 */}
                        <Divider orientation="left">
                            <Space><BulbOutlined />总结</Space>
                        </Divider>
                        <Paragraph style={{ fontSize: 14, lineHeight: 1.8, color: '#333' }}>
                            {summary.summary}
                        </Paragraph>

                        {/* 风险等级 */}
                        <Divider orientation="left">风险评估</Divider>
                        <Space>
                            <Text>当前风险等级：</Text>
                            <Tag color={riskColor[summary.risk_level] || 'default'} style={{ fontSize: 14 }}>
                                {summary.risk_level === 'high' ? '⚠️ 高风险' :
                                    summary.risk_level === 'medium' ? '⚡ 中等风险' : '✅ 低风险'}
                            </Tag>
                        </Space>

                        {/* 关键问题 */}
                        {summary.key_issues?.length > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space><WarningOutlined style={{ color: '#f5222d' }} />关键问题</Space>
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

                        {/* 优化建议 */}
                        {summary.recommendations?.length > 0 && (
                            <>
                                <Divider orientation="left">
                                    <Space><CheckCircleOutlined style={{ color: '#52c41a' }} />优化建议</Space>
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