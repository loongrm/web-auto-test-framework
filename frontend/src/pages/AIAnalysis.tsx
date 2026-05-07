import { useState } from 'react'
import {
    Card, Tabs, Form, Input, Button, Alert, Spin, Tag, Space, Select,
    Descriptions, List, Typography,
} from 'antd'
import { BulbOutlined, CodeOutlined, ToolOutlined } from '@ant-design/icons'
import { analyzeFailure, generateCases, healLocator } from '../api'

const { TextArea } = Input
const { Text, Paragraph } = Typography

// 失败分析
function FailureAnalyzer() {
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<Record<string, unknown> | null>(null)
    const [form] = Form.useForm()

    const handle = async (values: { error_log: string; test_code?: string; test_case_name?: string }) => {
        setLoading(true)
        setResult(null)
        try {
            const r = await analyzeFailure(values)
            setResult(r as unknown as Record<string, unknown>)
        } finally {
            setLoading(false)
        }
    }

    const typeColor: Record<string, string> = {
        element_not_found: 'orange', timeout: 'red', assertion_error: 'volcano',
        network_error: 'blue', environment_issue: 'purple',
        application_bug: 'magenta', test_data_issue: 'gold', unknown: 'default',
    }

    return (
        <div>
            <Form form={form} layout="vertical" onFinish={handle}>
                <Form.Item name="error_log" label="错误日志"
                    rules={[{ required: true, message: '请输入错误日志' }]}>
                    <TextArea rows={6} placeholder="粘贴 pytest 错误输出或 traceback..." />
                </Form.Item>
                <Form.Item name="test_code" label="测试代码（可选）">
                    <TextArea rows={4} placeholder="粘贴相关的测试代码..." />
                </Form.Item>
                <Form.Item name="test_case_name" label="用例名称（可选）">
                    <Input placeholder="如: test_login_success" />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} icon={<BulbOutlined />}>
                    AI 分析失败原因
                </Button>
            </Form>

            {loading && <Spin style={{ margin: 24 }} tip="AI 分析中..." />}

            {result && (
                <Card style={{ marginTop: 24 }} title="分析结果">
                    {!result['available'] ? (
                        <Alert type="warning" message="AI 服务不可用，请配置 OPENAI_API_KEY" />
                    ) : (
                        <Descriptions bordered size="small" column={1}>
                            <Descriptions.Item label="失败类型">
                                <Tag color={typeColor[String(result['failure_type'])] || 'default'}>
                                    {String(result['failure_type'])}
                                </Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="根本原因">{String(result['root_cause'])}</Descriptions.Item>
                            <Descriptions.Item label="修复建议">
                                <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                                    {String(result['suggestion'])}
                                </Paragraph>
                            </Descriptions.Item>
                            <Descriptions.Item label="置信度">
                                {Math.round(Number(result['confidence']) * 100)}%
                            </Descriptions.Item>
                            <Descriptions.Item label="是否 Flaky">
                                <Tag color={result['is_flaky'] ? 'orange' : 'green'}>
                                    {result['is_flaky'] ? `是 - ${result['flaky_reason']}` : '否'}
                                </Tag>
                            </Descriptions.Item>
                        </Descriptions>
                    )}
                </Card>
            )}
        </div>
    )
}

// 用例生成
function CaseGenerator() {
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<{
        available: boolean; cases?: unknown[]; yaml?: string; count?: number; type?: string
    } | null>(null)
    const [form] = Form.useForm()

    const handle = async (values: { user_story: string; case_type: 'ui' | 'api' }) => {
        setLoading(true)
        setResult(null)
        try {
            const r = await generateCases(values)
            setResult(r)
        } finally {
            setLoading(false)
        }
    }

    const priorityColor: Record<string, string> = { P0: 'red', P1: 'orange', P2: 'blue' }

    return (
        <div>
            <Form form={form} layout="vertical" onFinish={handle}
                initialValues={{ case_type: 'ui' }}>
                <Form.Item name="user_story" label="用户故事 / 功能描述"
                    rules={[{ required: true, message: '请输入用户故事' }]}>
                    <TextArea rows={5} placeholder={
                        `例：用户可以通过用户名密码登录系统。\n登录成功后跳转到主页，显示欢迎信息。\n连续3次失败后锁定账号5分钟。`
                    } />
                </Form.Item>
                <Form.Item name="case_type" label="用例类型">
                    <Select style={{ width: 160 }}>
                        <Select.Option value="ui">UI 测试用例</Select.Option>
                        <Select.Option value="api">API 测试用例</Select.Option>
                    </Select>
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} icon={<CodeOutlined />}>
                    AI 生成测试用例
                </Button>
            </Form>

            {loading && <Spin style={{ margin: 24 }} tip="AI 生成中..." />}

            {result && (
                <Card style={{ marginTop: 24 }} title={`生成结果（${result.count ?? 0} 条）`}>
                    {!result.available ? (
                        <Alert type="warning" message="AI 服务不可用，请配置 OPENAI_API_KEY" />
                    ) : result.cases ? (
                        <List
                            dataSource={result.cases as Record<string, unknown>[]}
                            renderItem={(item) => (
                                <List.Item>
                                    <List.Item.Meta
                                        title={
                                            <Space>
                                                <Tag color={priorityColor[String(item['priority'])] || 'default'}>
                                                    {String(item['priority'])}
                                                </Tag>
                                                <Text strong>{String(item['id'])}</Text>
                                                <span>{String(item['title'])}</span>
                                            </Space>
                                        }
                                        description={
                                            <div>
                                                <div><Text type="secondary">前置: </Text>{String(item['precondition'])}</div>
                                                <div>
                                                    <Text type="secondary">步骤: </Text>
                                                    {(item['steps'] as string[] || []).join(' → ')}
                                                </div>
                                                <div><Text type="secondary">预期: </Text>{String(item['expected'])}</div>
                                            </div>
                                        }
                                    />
                                </List.Item>
                            )}
                        />
                    ) : (
                        <pre style={{ background: '#f6f8fa', padding: 16, borderRadius: 6, fontSize: 12 }}>
                            {result.yaml}
                        </pre>
                    )}
                </Card>
            )}
        </div>
    )
}

// 定位器修复
function LocatorHealer() {
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<{
        broken_selector: string; alternatives: string[]; available: boolean
    } | null>(null)
    const [form] = Form.useForm()

    const handle = async (values: {
        broken_selector: string; page_html: string; element_purpose?: string
    }) => {
        setLoading(true)
        setResult(null)
        try {
            const r = await healLocator(values)
            setResult(r)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <Form form={form} layout="vertical" onFinish={handle}>
                <Form.Item name="broken_selector" label="失效的选择器"
                    rules={[{ required: true }]}>
                    <Input placeholder='如: #login-btn 或 .btn-primary' />
                </Form.Item>
                <Form.Item name="element_purpose" label="元素用途">
                    <Input placeholder='如: 登录按钮' />
                </Form.Item>
                <Form.Item name="page_html" label="页面 HTML 片段"
                    rules={[{ required: true }]}>
                    <TextArea rows={8} placeholder='粘贴页面 HTML...' />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} icon={<ToolOutlined />}>
                    AI 修复选择器
                </Button>
            </Form>

            {loading && <Spin style={{ margin: 24 }} tip="AI 分析中..." />}

            {result && (
                <Card style={{ marginTop: 24 }} title="替代选择器建议">
                    {!result.available ? (
                        <Alert type="warning" message="AI 服务不可用" />
                    ) : (
                        <>
                            <Alert type="info"
                                message={`失效选择器: ${result.broken_selector}`}
                                style={{ marginBottom: 16 }} />
                            <List
                                dataSource={result.alternatives || []}
                                renderItem={(sel: string, idx: number) => (
                                    <List.Item>
                                        <Tag color="blue">#{idx + 1}</Tag>
                                        <Text code copyable>{sel}</Text>
                                    </List.Item>
                                )}
                            />
                        </>
                    )}
                </Card>
            )}
        </div>
    )
}

// 主页面
export default function AIAnalysis() {
    const tabs = [
        { key: 'analyze', label: '失败根因分析', icon: <BulbOutlined />, children: <FailureAnalyzer /> },
        { key: 'generate', label: '用例生成', icon: <CodeOutlined />, children: <CaseGenerator /> },
        { key: 'heal', label: '选择器修复', icon: <ToolOutlined />, children: <LocatorHealer /> },
    ]
    return (
        <Card title="AI智能辅助">
            <Tabs items={tabs} />
        </Card>
    )
}