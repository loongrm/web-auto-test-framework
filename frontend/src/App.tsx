import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import TestRunner from './pages/TestRunner'
import AIAnalysis from './pages/AIAnalysis'
import ReportDetail from './pages/ReportDetail'
import ReportSummary from './pages/ReportSummary'

export default function App() {
    return (
        <AppLayout>
            <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/runner" element={<TestRunner />} />
                <Route path="/ai" element={<AIAnalysis />} />
                <Route path="/reports/:runId" element={<ReportDetail />} />
                <Route path="/reports/:runId/summary" element={<ReportSummary />} />
            </Routes>
        </AppLayout>
    )
}