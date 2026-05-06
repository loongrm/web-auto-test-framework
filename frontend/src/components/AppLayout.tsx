import { Layout, Menu, Typography, Badge } from 'antd'
import {
    DashboardOutlined,
    PlayCircleOutlined,
    RobotOutlined,
    FileTextOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'

const { Sider, Content, Header } = Layout
const { Title } = Typography

export default function AppLayout({ children }: { children: ReactNode }) {
    const navigate = useNavigate()
    const { pathname } = useLocation()

    // 高亮报告详情页时选中 dashboard
    const selectedKey = pathname.startsWith('/reports') ? '/dashboard' : pathname

    const menuItems = [
        { key: '/dashboard', icon: <DashboardOutlined />, label: '测试看板' },
        { key: '/runner', icon: <PlayCircleOutlined />, label: '执行测试' },
        { key: '/ai', icon: <RobotOutlined />, label: 'AI 分析' },
    ]

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sider
                theme="dark"
                width={210}
                style={{ boxShadow: '2px 0 8px rgba(0,0,0,0.15)' }}
            >
                <div style={{
                    padding: '20px 16px 16px',
                    borderBottom: '1px solid rgba(255,255,255,0.08)',
                    marginBottom: 8,
                }}>
                    <div style={{ fontSize: 22, textAlign: 'center' }}>🧪</div>
                    <div style={{
                        color: '#fff',
                        fontSize: 13,
                        textAlign: 'center',
                        fontWeight: 600,
                        letterSpacing: 1,
                        marginTop: 4,
                    }}>
                        AutoTest Platform
                    </div>
                </div>
                <Menu
                    theme="dark"
                    mode="inline"
                    selectedKeys={[selectedKey]}
                    items={menuItems}
                    onClick={({ key }) => navigate(key)}
                    style={{ borderRight: 0 }}
                />
            </Sider>
            <Layout>
                <Header style={{
                    background: '#fff',
                    padding: '0 24px',
                    borderBottom: '1px solid #f0f0f0',
                    display: 'flex',
                    alignItems: 'center',
                }}>
                    <Title level={5} style={{ margin: 0, color: '#1a1a2e' }}>
                        企业级 AI 增强自动化测试平台
                    </Title>
                </Header>
                <Content style={{
                    margin: 24,
                    padding: 24,
                    background: '#fff',
                    borderRadius: 8,
                    minHeight: 'calc(100vh - 112px)',
                }}>
                    {children}
                </Content>
            </Layout>
        </Layout>
    )
}