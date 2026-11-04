import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ImportPage from './pages/ImportPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ImportPage />} />
        <Route path="/dashboard/:repoId" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}
