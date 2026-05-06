import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Card, Row, Col, Statistic, Table, Tag, Spin, Alert,
    Progress, Button, Space, Tooltip,
} from 'antd'
import {
    CheckCircleOutlined, CloseCircleOutlined,
    MinusCircleOutlined, FileSearchOutlined, RobotOutlined,
} from '@ant-design/icons'
import {
    LineChart, Line, XAxis, YAxis, Tooltip as RTooltip,
    ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { getDashboard, type DashboardData, type TestRunSummary } from '../api'

export default function Dashboard() {
    const navigate = useNavigate()
    const [data, setData] = useState<DashboardData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const load = async () => {
        try {
            const d = await getDashboard()
            setData(d)
            setError('')
        } catch {
            setError('无法连接后端服务，请确认 uvicorn backend.main:app --reload 已启动')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        load()
        const t = setInterval(load, 15000)
        return () => clearInterval(t)
    }, [])

    const statusTag = (s: string) => {
        const map: Record<string, [string, string]> = {
            success: ['success', '通过'],
            failed: ['error', '失败'],
            running: ['processing', '运行中'],
        }
        const [color, label] = map[s] || ['default', s]
        return <Tag color={color}>{label}</Tag>
    }

    const columns = [
        { title: 'ID', dataIndex: 'id', width: 55 },
        { title: '名称', dataIndex: 'name', ellipsis: true },
        { title: '模块', dataIndex: 'module', width: 70 },
        { title: '状态', dataIndex: 'status', width: 88, render: statusTag },
        {
            title: '通过率', dataIndex: 'pass_rate', width: 110,
            render: (v: number) => <Progress percent={v} size="small" steps={10} />,
        },
        { title: '总数', dataIndex: 'total', width: 55 },
        {
            title: '通过', dataIndex: 'passed', width: 55,
            render: (v: number) => <span style={{ color: '#52c41a' }}>{v}</span>
        },
        {
            title: '失败', dataIndex: 'failed', width: 55,
            render: (v: number) => <span style={{ color: v ? '#f5222d' : '#333' }}>{v}</span>
        },
        {
            title: '耗时(s)', dataIndex: 'duration', width: 75,
            render: (v: number) => v?.toFixed(1)
        },
        {
            title: '开始时间', dataIndex: 'start_time', width: 160,
            render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-'
        },
        {
            title: '操作', key: 'action', width: 120,
            render: (_: unknown, row: TestRunSummary) => (
                <Space>
                    <Tooltip title="查看失败详情">
                        <Button
                            size="small" icon={<FileSearchOutlined />}
                            disabled={row.failed === 0}
                            onClick={() => navigate(`/reports/${row.id}`)}
                        />
                    </Tooltip>
                    <Tooltip title="AI 执行摘要">
                        <Button
                            size="small" icon={<RobotOutlined />}
                            onClick={() => navigate(`/reports/${row.id}/summary`)}
                        />
                    </Tooltip>
                </Space>
            ),
        },
    ]

    if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
    if (error) return <Alert type="error" message={error} style={{ margin: 24 }} />
    if (!data) return null

    const { stats, trend, recent_runs } = data

    return (
        <div>
            <Row gutter={16} style={{ marginBottom: 24 }}>
                {[
                    {
                        title: '综合通过率', value: stats.pass_rate, suffix: '%',
                        color: stats.pass_rate >= 80 ? '#52c41a' : '#f5222d'
                    },
                    { title: '通过', value: stats.passed, icon: <CheckCircleOutlined />, color: '#52c41a' },
                    {
                        title: '失败', value: stats.failed, icon: <CloseCircleOutlined />,
                        color: stats.failed ? '#f5222d' : '#333'
                    },
                    { title: '跳过', value: stats.skipped, icon: <MinusCircleOutlined /> },
                ].map((item) => (
                    <Col span={6} key={item.title}>
                        <Card>
                            <Statistic
                                title={item.title}
                                value={item.value}
                                suffix={item.suffix}
                                prefix={item.icon}
                                valueStyle={{ color: item.color }}
                            />
                        </Card>
                    </Col>
                ))}
            </Row>

            <Card title="执行趋势（通过率）" style={{ marginBottom: 24 }}>
                {trend.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                        暂无趋势数据，执行测试后将在此显示
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={220}>
                        <LineChart data={trend}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                            <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                            <RTooltip formatter={(v: number) => [`${v}%`, '通过率']} />
                            <Line
                                type="monotone" dataKey="passRate"
                                stroke="#1890ff" strokeWidth={2} dot={{ r: 4 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </Card>

            <Card title={`最近执行记录（${recent_runs.length} 条）`}>
                <Table
                    dataSource={recent_runs}
                    columns={columns}
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 8, showSizeChanger: false }}
                />
            </Card>
        </div>
    )
}