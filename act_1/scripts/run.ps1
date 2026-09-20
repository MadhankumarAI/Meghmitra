# Start the service and the TTS worker (two windows). Usage: .\scripts\run.ps1
$root = Split-Path $PSScriptRoot -Parent
$env:HF_HOME = Join-Path $root ".cache\hf"
$env:HF_HUB_OFFLINE = "1"
# The worker exits after a CUDA error so that it gets a fresh GPU context; this loop restarts it.
$worker = "`$host.UI.RawUI.WindowTitle='TTS worker'; while (`$true) { .\.venv-ml\Scripts\python scripts\tts_worker.py; Start-Sleep 3 }"
Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", $worker
Set-Location $root
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
