# Public HTTPS address for the Meta webhook, via ngrok's free static domain: the address never changes.
#   https://<NGROK_DOMAIN>/whatsapp/webhook   <- paste once into Meta > WhatsApp > Configuration > Webhook
# Needs NGROK_AUTH_TOKEN and NGROK_DOMAIN in .env (free account at https://dashboard.ngrok.com).
# Set ADMIN_API_KEY in .env first: the tunnel exposes the whole service (the /dev simulator refuses tunnel traffic).
$root = Split-Path $PSScriptRoot -Parent
$envVars = @{}
Get-Content (Join-Path $root ".env") | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $envVars[$Matches[1]] = $Matches[2] }
}
$token = $envVars["NGROK_AUTH_TOKEN"]
if (-not $token -or -not $envVars["NGROK_DOMAIN"]) { throw "Set NGROK_AUTH_TOKEN and NGROK_DOMAIN in .env" }
# --authtoken wins over any older ngrok.yml on this machine (one from another account broke this once).
& (Join-Path $root "tools\ngrok.exe") http 8000 --authtoken $token --url ("https://" + $envVars["NGROK_DOMAIN"]) --log stdout
