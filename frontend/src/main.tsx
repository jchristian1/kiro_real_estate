import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './shared/contexts/ThemeContext'
import { PlatformAdminApp } from './apps/platform-admin/PlatformAdminApp'
import { AgentApp } from './apps/agent/AgentApp'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* Agent app at /agent/* */}
          <Route path="/agent/*" element={<AgentApp />} />
          {/* Platform admin at / (catch-all) */}
          <Route path="/*" element={<PlatformAdminApp />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
)
