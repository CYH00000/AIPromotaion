import { useCallback, useEffect, useState } from 'react'
import { LogIn, ShieldOff } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  accountsApi,
  apiErrorMessage,
  type AccountInfo,
  type PlatformId,
} from '@/lib/collectorApi'

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function statusVariant(account: AccountInfo): 'running' | 'success' | 'idle' {
  if (account.login_state === 'running') return 'running'
  if (account.configured) return 'success'
  return 'idle'
}

function statusLabel(account: AccountInfo) {
  if (account.login_state === 'running') return '登录中'
  if (account.login_state === 'failed') return '登录失败'
  if (account.configured) return '已登录过'
  return '未配置'
}

export function AccountsPanel() {
  const [accounts, setAccounts] = useState<AccountInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [pendingPlatform, setPendingPlatform] = useState<PlatformId | null>(null)
  const [confirming, setConfirming] = useState<AccountInfo | null>(null)

  const refresh = useCallback(async () => {
    try {
      setAccounts(await accountsApi.list())
    } catch (error) {
      toast.error(apiErrorMessage(error))
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    void refresh().finally(() => setLoading(false))
  }, [refresh])

  const anyRunning = accounts.some((account) => account.login_state === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const timer = window.setInterval(() => {
      void refresh()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [anyRunning, refresh])

  const startLogin = async (platform: PlatformId) => {
    setPendingPlatform(platform)
    try {
      await accountsApi.login(platform)
      toast.success('已启动登录，请在弹出的浏览器中完成扫码')
      await refresh()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setPendingPlatform(null)
    }
  }

  const confirmUnbind = async () => {
    if (!confirming) return
    setPendingPlatform(confirming.platform)
    try {
      await accountsApi.unbind(confirming.platform)
      toast.success(`已解绑 ${confirming.label}`)
      setConfirming(null)
      await refresh()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setPendingPlatform(null)
    }
  }

  return (
    <section className="space-y-4">
      <Card className="p-4 text-xs leading-5 text-cyber-text-muted">
        登录态保存在本机 browser_data 配置目录。状态只表示本地配置存在，实际有效性由任务运行时的平台检查确认。
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {accounts.map((account) => (
          <Card key={account.platform} className="flex flex-col gap-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-lg font-semibold text-cyber-text-primary">{account.label}</p>
                <p className="mt-1 text-xs text-cyber-text-muted">
                  {account.platform === 'dy' ? '抖音' : '小红书'} · 扫码登录 ·{' '}
                  {account.profile_mode === 'cdp' ? 'CDP 模式' : '标准模式'}
                </p>
              </div>
              <Badge variant={statusVariant(account)}>{statusLabel(account)}</Badge>
            </div>
            <div className="text-xs text-cyber-text-secondary">
              <p>最近登录：{formatDate(account.last_login_at)}</p>
              {account.login_error && <p className="mt-1 text-red-300">{account.login_error}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={pendingPlatform === account.platform || account.login_state === 'running'}
                onClick={() => void startLogin(account.platform)}
              >
                <LogIn />{account.configured ? '验证登录态' : '登录'}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={!account.configured || pendingPlatform === account.platform}
                onClick={() => setConfirming(account)}
              >
                <ShieldOff />解绑
              </Button>
            </div>
          </Card>
        ))}
        {!accounts.length && (
          <p className="text-sm text-cyber-text-muted">
            {loading ? '正在读取账号状态…' : '没有可管理的平台。'}
          </p>
        )}
      </div>
      <Dialog open={confirming !== null} onOpenChange={(open) => { if (!open) setConfirming(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>解绑 {confirming?.label}</DialogTitle>
            <DialogDescription>
              这会删除本机的平台登录配置，之后需要重新扫码登录。已采集的数据不受影响。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(null)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => void confirmUnbind()}
              disabled={pendingPlatform !== null}
            >
              确认解绑
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
