import { useState } from 'react'
import {
  Card, Form, Input, Button, Alert, Tag, Space,
  Divider, Typography, Descriptions, List, Empty, Progress,
} from 'antd'
import { BulbOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { analyzeFailure } from '../api'

const { TextArea } = Input
const { Text, Paragraph } = Typography

// 失败类型 → 中文标签
const failureTypeLabel: Record<string, string> = {
  element_not_found: '元素定位失败',
  timeout: '等待超时',
  assertion_failed: '断言失败',
  network_error: '网络错误',
  auth_error: '认证错误',
  data_error: '数据错误',
  env_error: '环境配置错误',
  unknown: '未分类',
}

interface AnalysisResult {
  available: boolean
  failure_type: string
  root_cause: string
  suggestion: string
  confidence: number
  is_flaky: boolean
  retrieved_cases: Array<{
    id: string
    score: number
    failure_type: string
    test_name: string
    suggestion: string
  }>
  retrieval_used: boolean
  llm_backend: string
}

export default function AIAnalysis() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  const handleAnalyze = async (values: { error_log: string; test_case_name?: string; test_code?: string }) => {
    setLoading(true)
    setResult(null)
    try {
      const r = await analyzeFailure({
        error_log: values.error_log,
        test_case_name: values.test_case_name || '',
        test_code: values.test_code || '',
      })
      setResult(r as unknown as AnalysisResult)
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Card
        title={<Space><RobotOutlined style={{ color: '#722ed1' }} />AI 失败根因分析（RAG 增强）</Space>}
        style={{ marginBottom: 24 }}
      >
        <Form form={form} layout="vertical" onFinish={handleAnalyze}>
          <Form.Item
            name="error_log"
            label="错误日志"
            rules={[{ required: true, message: '请粘贴错误日志' }]}
          >
            <TextArea rows={6} placeholder="粘贴 pytest 错误堆栈 / 失败信息..." />
          </Form.Item>

          <Form.Item name="test_case_name" label="用例名称（可选）">
            <Input placeholder="如: test_login_success" />
          </Form.Item>

          <Form.Item name="test_code" label="测试代码（可选）">
            <TextArea rows={4} placeholder="粘贴相关测试代码，有助于提升分析准确度..." />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" icon={<BulbOutlined />} htmlType="submit" loading={loading}>
              {loading ? '分析中...' : 'AI 分析失败原因'}
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {result && (
        <Card title="分析结果">
          {/* 降级提示 */}
          {result.llm_backend === 'rule_fallback' && (
            <Alert
              type="info"
              showIcon
              message="当前由规则引擎给出（LLM 不可用）"
              description="未配置可用的 OPENAI_API_KEY 或调用失败，已自动降级到本地规则分析，结果仅供参考。"
              style={{ marginBottom: 16 }}
            />
          )}

          <Descriptions bordered column={1} size="middle">
            <Descriptions.Item label="失败类型">
              <Tag color="blue">{failureTypeLabel[result.failure_type] || result.failure_type}</Tag>
              {result.is_flaky && <Tag color="orange">疑似偶发</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="根本原因">
              <Paragraph style={{ margin: 0 }}>{result.root_cause}</Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="修复建议">
              <Paragraph style={{ margin: 0 }}>{result.suggestion}</Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              <Progress
                percent={Math.round(result.confidence * 100)}
                size="small"
                status={result.confidence >= 0.6 ? 'success' : 'normal'}
                style={{ maxWidth: 240 }}
              />
            </Descriptions.Item>
          </Descriptions>

          {/* RAG 检索透明展示 */}
          <Divider orientation="left">
            <Space>
              <ThunderboltOutlined style={{ color: '#13c2c2' }} />
              检索增强（RAG）
            </Space>
          </Divider>

          {result.retrieval_used && result.retrieved_cases.length > 0 ? (
            <>
              <Text type="secondary" style={{ fontSize: 13 }}>
                本次分析参考了知识库中 {result.retrieved_cases.length} 条历史相似案例：
              </Text>
              <List
                size="small"
                style={{ marginTop: 8 }}
                dataSource={result.retrieved_cases}
                renderItem={(c) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }} size={2}>
                      <Space>
                        <Tag color="cyan">相似度 {(c.score * 100).toFixed(0)}%</Tag>
                        <Text strong style={{ fontSize: 13 }}>{c.test_name || c.id}</Text>
                        <Tag>{failureTypeLabel[c.failure_type] || c.failure_type}</Tag>
                      </Space>
                      {c.suggestion && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          历史建议: {c.suggestion}
                        </Text>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            </>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="知识库中暂无相似历史案例（首次遇到此类失败）"
            />
          )}
        </Card>
      )}
    </div>
  )
}
