# Run the daily live forecast automatically, so the console is never stale.
#
#   .\scripts\schedule_daily.ps1                 register (07:30 every day)
#   .\scripts\schedule_daily.ps1 -Deploy         ...and publish to Vercel each day
#   .\scripts\schedule_daily.ps1 -Remove         unregister
#
# Why a Windows task and not the cloud: imdpune.gov.in (real-time rainfall) is reachable from this
# laptop but not from the server, and the data lives on D:. The task simply runs daily_live.sh.
param([switch]$Deploy, [switch]$Remove, [string]$At = "07:30")

$ErrorActionPreference = "Stop"
$name = "Mungaru daily forecast"
$root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  "unregistered: $name"
  return
}

$bash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $bash)) { throw "Git Bash not found at $bash" }
$args = "scripts/daily_live.sh" + $(if ($Deploy) { " --deploy" } else { "" })

$action = New-ScheduledTaskAction -Execute $bash -Argument "-lc `"cd '$root' && $args >> D:/Morphy/daily_live.log 2>&1`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# IMD publishes the previous day's grid in the morning; skip if the laptop is off, catch up when it wakes
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
"registered: $name, daily at $At" + $(if ($Deploy) { " (with deploy)" } else { "" })
"log: D:/Morphy/daily_live.log   ·   remove with: .\scripts\schedule_daily.ps1 -Remove"
