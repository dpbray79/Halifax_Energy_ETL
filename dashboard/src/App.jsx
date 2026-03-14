import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Models from './pages/Models'
import Data from './pages/Data'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="models" element={<Models />} />
          <Route path="data" element={<Data />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
