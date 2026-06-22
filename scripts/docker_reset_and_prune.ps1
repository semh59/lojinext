<#
Docker ve disk temizliği otomasyon skripti
- Docker Desktop servisini durdurur
- WSL engine’i kapatır
- (opsiyonel) yerel model ve HF cache siler
- Servisi ve Docker Desktop’ı yeniden başlatır
- Docker daemon ayağa kalkana kadar bekler (120 sn)
- docker system prune -a --volumes ile kullanılmayan imaj/ağ/volume temizliği yapar
#>

$ErrorActionPreference = 'Stop'

function Stop-Docker {
    Write-Host "[1/6] Docker servis durduruluyor..."
    Stop-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    Stop-Process -Name "com.docker.backend" -ErrorAction SilentlyContinue
    Stop-Service -Name com.docker.service -ErrorAction SilentlyContinue
}

function Shutdown-WSL {
    Write-Host "[2/6] WSL engine kapatılıyor..."
    wsl --shutdown | Out-Null
}

function Clean-Cache {
    Write-Host "[3/6] HF cache ve büyük model dosyası temizleniyor..."
    $hf = Join-Path $env:USERPROFILE ".cache\huggingface"
    if (Test-Path $hf) { Remove-Item $hf -Recurse -Force -ErrorAction SilentlyContinue }
    $modelDir = "D:\PROJECT\LOJINEXT\models"
    if (Test-Path $modelDir) {
        Get-ChildItem -Path $modelDir -Filter "*.gguf" -File -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Start-Docker {
    Write-Host "[4/6] Docker servisi ve Desktop başlatılıyor..."
    Start-Service com.docker.service -ErrorAction Stop
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" | Out-Null
}

function Wait-Daemon {
    Write-Host "[5/6] Docker daemon bekleniyor (120 sn)..."
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        $info = & docker info 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Host "  ✅ Docker hazır"; return }
        Start-Sleep -Seconds 5
    }
    throw "Docker daemon 120 sn içinde başlamadı."
}

function Prune-All {
    Write-Host "[6/6] docker system prune -a --volumes çalıştırılıyor..."
    docker system prune -a --volumes -f
}

Stop-Docker
Shutdown-WSL
Clean-Cache
Start-Docker
Wait-Daemon
Prune-All

Write-Host "Temizlik tamamlandı."
