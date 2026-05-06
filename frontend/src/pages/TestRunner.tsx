import { useState, useEffect, useRef } from 'react'
import {
    Card, Form, Select, Button, Alert, Tag, Space, Divider, Typography,
    Radio, Input,
} from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { runTests, getTaskStatus } from '../api'

const { Text, Paragraph } = Typography

interface TaskResult {
    task_id: string
    run_id?: number
    status: string
    stdout?: string
    stderr?: string
    returncode?: number
    passed?: number
    failed?: number
    total?: number
}

export default function TestRunner() {
    const [form] = Form.useForm()
    const [loading, setLoading] = useState(false)
    const [task, setTask] = useState<TaskResult | null>(null)
    const [polling, setPolling] = useState(false)
    const pollRef = useRef<ReturnType<typeof setInterval>>()

    const stopPolling = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = undefined
        }
        setPolling(false)
    }

    const startPolling = (taskId: string) => {
        setPolling(true)
        pollRef.current = setInterval(async () => {
            const status = await getTaskStatus(taskId)
            setTask(prev => ({ ...prev!, ...status }))
            if (status.status !== 'running') {
                stopPolling()
                setLoading(false)
            }
        }, 2000)
    }

    useEffect(() => () => stopPolling(), [])

    const handleRun = async (values: any) => {
        setLoading(true)
        setTask(null)
        try {
            const result = await runTests(values)
            setTask(result)
            startPolling(result.task_id)
        } catch (e: any) {
            setTask({ task_id: '', status: 'error', stdout: e.message })
            setLoading(false)
        }
    }

    const statusColor: Record<string, string> = {
        accepted: 'blue', running: 'processing', success: 'success', failed: 'error',
    }

    return (
        <div>
            <Card title="🚀 触发测试执行" style={{ marginBottom: 24 }}>
                <Form
                    form={form}
                    layout="inline"
                    initialValues={{ module: 'all', env: 'dev' }}
                    onFinish={handleRun}
                >
                    <Form.Item name="module" label="测试模块">
                        <Select style={{ width: 140 }}>
                            <Select.Option value="all">全量测试</Select.Option>
                            <Select.Option value="ui">UI 测试</Select.Option>
                            <Select.Option value="api">API 测试</Select.Option>
                        </Select>
                    </Form.Item>
                    <Form.Item name="env" label="测试环境">
                        <Radio.Group>
                            <Radio.Button value="dev">Dev</Radio.Button>
                            <Radio.Button value="test">Test</Radio.Button>
                            <Radio.Button value="prod">Prod</Radio.Button>
                        </Radio.Group>
                    </Form.Item>
                    <Form.Item name="markers" label="标签过滤">
                        <Input placeholder="如: smoke 或 p0" style={{ width: 160 }} allowClear />
                    </Form.Item>
                    <Form.Item>
                        <Space>
                            <Button
                                type="primary"
                                icon={<PlayCircleOutlined />}
                                htmlType="submit"
                                loading={loading}
                            >
                                {loading ? '执行中...' : '开始执行'}
                            </Button>
                            {loading && (
                                <Button icon={<ReloadOutlined />} onClick={stopPolling}>
                                    停止轮询
                                </Button>
                            )}
                        </Space>
                    </Form.Item>
                </Form>
            </Card>

            {task && (
                <Card
                    title={
                        <Space>
                            <span>执行结果</span>
                            <Tag color={statusColor[task.status] || 'default'}>{task.status}</Tag>
                            {task.task_id && <Text type="secondary">任务ID: {task.task_id}</Text>}
                            {polling && <Tag color="blue">轮询中...</Tag>}
                        </Space>
                    }
                >
                    {task.status === 'success' && (
                        <Alert
                            type="success"
                            message={`✅ 测试完成 | 通过: ${task.passed ?? '-'} | 失败: ${task.failed ?? '-'} | 总数: ${task.total ?? '-'}`}
                            style={{ marginBottom: 16 }}
                        />
                    )}
                    {task.status === 'failed' && (
                        <Alert
                            type="error"
                            message={`❌ 存在失败用例 | 通过: ${task.passed ?? '-'} | 失败: ${task.failed ?? '-'} | 总数: ${task.total ?? '-'}`}
                            style={{ marginBottom: 16 }}
                        />
                    )}
                    {task.stdout && (
                        <>
                            <Divider orientation="left">stdout</Divider>
                            <Paragraph>
                                <pre style={{
                                    background: '#1a1a1a', color: '#00ff41', padding: 16,
                                    borderRadius: 6, fontSize: 12, maxHeight: 400, overflow: 'auto',
                                }}>
                                    {task.stdout}
                                </pre>
                            </Paragraph>
                        </>
                    )}
                    {task.stderr && task.stderr.trim() && (
                        <>
                            <Divider orientation="left">stderr</Divider>
                            <pre style={{
                                background: '#2d1b1b', color: '#ff6b6b', padding: 16,
                                borderRadius: 6, fontSize: 12, maxHeight: 200, overflow: 'auto',
                            }}>
                                {task.stderr}
                            </pre>
                        </>
                    )}
                </Card>
            )}
        </div>
    )
}