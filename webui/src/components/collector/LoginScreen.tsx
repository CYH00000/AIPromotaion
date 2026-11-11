import { useState } from 'react'
import { LockKeyhole } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { authApi, apiErrorMessage } from '@/lib/collectorApi'

interface LoginScreenProps {
  onAuthenticated: () => void
}

export function LoginScreen({ onAuthenticated }: LoginScreenProps) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const csrf = await authApi.csrf()
      await authApi.login(username, password, csrf)
      onAuthenticated()
    } catch (cause) {
      setError(apiErrorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-cyber-bg-primary px-5 py-10">
      <section className="w-full max-w-md rounded-xl border border-cyber-border-DEFAULT bg-cyber-bg-secondary p-7 shadow-cyber-card">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-cyber-neon-cyan/40 bg-cyber-neon-cyan/10 text-cyber-neon-cyan">
            <LockKeyhole size={20} />
          </span>
          <div>
            <h1 className="text-xl font-semibold text-cyber-text-primary">评论采集工作台</h1>
            <p className="mt-1 text-sm text-cyber-text-muted">单管理员登录</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-5">
          <label className="block space-y-2 text-sm text-cyber-text-secondary">
            用户名
            <Input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <label className="block space-y-2 text-sm text-cyber-text-secondary">
            密码
            <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
          <Button className="w-full" type="submit" disabled={busy}>
            {busy ? '正在登录…' : '登录'}
          </Button>
        </form>
        <p className="mt-5 text-xs leading-5 text-cyber-text-muted">本地初始管理员密码保存在项目根目录的 .env 文件中。请勿将该文件提交到 Git。</p>
      </section>
    </main>
  )
}
