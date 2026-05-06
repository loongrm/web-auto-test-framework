import { Layout, Menu, Typography, Badge } from 'antd'
import {
    DashboardOutlined,
    PlayCircleOutlined,
    RobotOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'

const { Header, Sider, Content } = Layout
const { Title } = Typography

export default function AppLayout({ children }: { children: ReactNode }) {
    const navigate = useNavigate()
    const { pathname } = useLocation()

    const menuItems = [
        { key: '/dashboard', icon: <DashboardOutlined />, label: '测试看板' },
        { key: '/runner', icon: <PlayCircleOutlined />, label: '执行测试' },
        { key: '/ai', icon: <RobotOutlined />, label: 'AI 分析' },
    ]

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sider theme="dark" width={200}>
                <div style={{ padding: '16px', textAlign: 'center' }}>
                    <Title level={5} style={{ color: '#fff', margin: 0 }}>
                        🧪 测试平台
                    </Title>
                </div>
                <Menu
                    theme="dark"
                    mode="inline"
                    selectedKeys={[pathname]}
                    items={menuItems}
                    onClick={({ key }) => navigate(key)}
                />
            </Sider>
            <Layout>
                <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
                    <Title level={4} style={{ margin: '16px 0' }}>企业级自动化测试平台</Title>
                </Header>
                <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
                    {children}
                </Content>
            </Layout>
        </Layout>
    )
}