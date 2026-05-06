import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import TestRunner from './pages/TestRunner'
import AIAnalysis from './pages/AIAnalysis'

export default function App() {
    return (
        <AppLayout>
            <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/runner" element={<TestRunner />} />
                <Route path="/ai" element={<AIAnalysis />} />
            </Routes>
        </AppLayout>
    )
}