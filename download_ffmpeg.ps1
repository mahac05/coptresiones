# download_ffmpeg.ps1 — загрузка FFmpeg в resources/ffmpeg/
$ErrorActionPreference = "Stop"

$ffmpegDir = Join-Path $PSScriptRoot "resources\ffmpeg"
$tempDir   = Join-Path $env:TEMP "ffmpeg_dl"
$zipFile   = Join-Path $tempDir "ffmpeg.zip"
$url       = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

# Проверка: уже есть?
if (Test-Path (Join-Path $ffmpegDir "ffmpeg.exe")) {
    & (Join-Path $ffmpegDir "ffmpeg.exe") -version 2>&1 | Select-Object -First 1
    Write-Host "FFmpeg уже установлен. Перезаписать? (y/N)" -ForegroundColor Yellow
    $r = Read-Host
    if ($r -notin @("y","Y")) { exit 0 }
}

# Подготовка
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Path $tempDir  -Force | Out-Null
New-Item -ItemType Directory -Path $ffmpegDir -Force | Out-Null

# Скачивание
Write-Host "Скачивание FFmpeg (~100 MB)..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $zipFile -UseBasicParsing

# Распаковка
Write-Host "Распаковка..." -ForegroundColor Cyan
Expand-Archive -Path $zipFile -DestinationPath $tempDir -Force

# Копирование exe
$binDir = Get-ChildItem $tempDir -Recurse -Directory | Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
if (-not $binDir) { Write-Host "Ошибка: папка bin не найдена" -ForegroundColor Red; exit 1 }

Copy-Item (Join-Path $binDir.FullName "ffmpeg.exe")  $ffmpegDir -Force
Copy-Item (Join-Path $binDir.FullName "ffprobe.exe") $ffmpegDir -Force

# Очистка
Remove-Item $tempDir -Recurse -Force

# Результат
Write-Host ""
& (Join-Path $ffmpegDir "ffmpeg.exe") -version 2>&1 | Select-Object -First 1
$size = [math]::Round((Get-Item (Join-Path $ffmpegDir "ffmpeg.exe")).Length / 1MB, 1)
Write-Host "Готово! FFmpeg ($size MB) -> $ffmpegDir" -ForegroundColor Green
