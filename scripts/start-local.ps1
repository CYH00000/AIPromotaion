$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath '.env')) {
  Copy-Item -LiteralPath '.env.example' -Destination '.env'
  throw 'Created .env from .env.example. Set PostgreSQL and administrator passwords, then run this script again.'
}

$envLines = Get-Content -LiteralPath '.env'
$adminPasswordLine = $envLines | Where-Object { $_ -match '^ADMIN_PASSWORD=' } | Select-Object -First 1
if (-not $adminPasswordLine -or $adminPasswordLine -match 'replace-with') {
  throw 'Set ADMIN_PASSWORD to a unique value of at least 16 characters in .env.'
}
$adminPassword = $adminPasswordLine.Substring('ADMIN_PASSWORD='.Length)
if ($adminPassword.Length -lt 16) {
  throw 'ADMIN_PASSWORD must be at least 16 characters.'
}

$uvCommand = Get-Command 'uv' -ErrorAction SilentlyContinue
if ($uvCommand) {
  $UvPath = $uvCommand.Source
} else {
  $localUv = Join-Path $ProjectRoot '.tools\uv.exe'
  if (Test-Path -LiteralPath $localUv) {
    $UvPath = $localUv
  } else {
    throw 'Install uv and ensure it is available on PATH.'
  }
}

docker compose -f compose.dev.yml up -d --wait postgres
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to become healthy.' }

& $UvPath sync --locked --no-install-project
if ($LASTEXITCODE -ne 0) { throw 'Python dependency sync failed.' }

& $UvPath run --env-file .env python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }

Push-Location (Join-Path $ProjectRoot 'webui')
try {
  npm ci
  if ($LASTEXITCODE -ne 0) { throw 'WebUI dependency installation failed.' }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'WebUI production build failed.' }
} finally {
  Pop-Location
}

Write-Host 'MVP is available at http://127.0.0.1:8080. Press Ctrl+C to stop the API.'
& $UvPath run --env-file .env uvicorn api.main:app --host 127.0.0.1 --port 8080
