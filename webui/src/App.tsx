import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { Sidebar } from '@/components/layout/Sidebar'
import { EnvironmentCheck, isEnvChecked } from '@/components/env/EnvironmentCheck'
import { LicenseDisclaimer, isLicenseAccepted } from '@/components/license/LicenseDisclaimer'
import { CollectorWorkspace } from '@/components/collector/CollectorWorkspace'
import { LoginScreen } from '@/components/collector/LoginScreen'
import { authApi } from '@/lib/collectorApi'

function App() {
  const [authChecked, setAuthChecked] = useState(false)
  const [username, setUsername] = useState('')
  // Initialize by checking localStorage if license has been accepted
  const [licenseAccepted, setLicenseAccepted] = useState(() => isLicenseAccepted())
  // Initialize by checking localStorage if env check has passed
  const [envChecked, setEnvChecked] = useState(() => isEnvChecked())
  // State for showing disclaimer manually
  const [showDisclaimer, setShowDisclaimer] = useState(false)

  useEffect(() => {
    let active = true
    authApi.me()
      .then((user) => { if (active) setUsername(user.username) })
      .catch(() => { if (active) setUsername('') })
      .finally(() => { if (active) setAuthChecked(true) })
    const onUnauthorized = () => setUsername('')
    window.addEventListener('collector:unauthorized', onUnauthorized)
    return () => {
      active = false
      window.removeEventListener('collector:unauthorized', onUnauthorized)
    }
  }, [])

  const handleEnvCheckComplete = () => {
    setEnvChecked(true)
  }

  const handleLicenseAccept = () => {
    setLicenseAccepted(true)
    setShowDisclaimer(false)
  }

  const handleShowDisclaimer = () => {
    setShowDisclaimer(true)
  }

  const handleAuthenticated = async () => {
    const user = await authApi.me()
    setUsername(user.username)
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } finally {
      setUsername('')
    }
  }

  if (!authChecked) {
    return <div className="flex min-h-screen items-center justify-center bg-cyber-bg-primary text-sm text-cyber-text-muted">正在检查登录状态…</div>
  }

  if (!username) return <LoginScreen onAuthenticated={() => { void handleAuthenticated() }} />

  return (
    <div className="flex flex-col h-screen cyber-grid overflow-hidden relative">
      {/* License Disclaimer Modal - Shows first or when triggered */}
      {(!licenseAccepted || showDisclaimer) && (
        <LicenseDisclaimer onAccept={handleLicenseAccept} />
      )}

      {/* Environment Check Modal - Shows after license accepted */}
      {licenseAccepted && !showDisclaimer && !envChecked && (
        <EnvironmentCheck onCheckComplete={handleEnvCheckComplete} />
      )}

      {/* Header Bar */}
      <Sidebar onShowDisclaimer={handleShowDisclaimer} />

      <CollectorWorkspace username={username} onLogout={handleLogout} />

      {/* Toast notifications - Theme-aware style */}
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'glass-panel font-mono text-cyber-text-primary',
          style: {
            fontFamily: 'JetBrains Mono, monospace',
          },
        }}
      />
    </div>
  )
}

export default App
