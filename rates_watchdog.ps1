# Rates auto-update loop — every 15 minutes
$py = "C:\Users\Mi Gaming\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
$script = "C:\Users\Mi Gaming\.openclaw\workspace\dashboards\gh-pages\auto_update.py"
$log = "C:\Users\Mi Gaming\.openclaw\workspace\memory\rates-watchdog.log"

function log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

log "Rates watchdog started (15 min)"

while ($true) {
    log "Running update..."
    try {
        $proc = Start-Process -FilePath $py -ArgumentList "`"$script`"" -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$env:TEMP\rates_stdout.txt" -RedirectStandardError "$env:TEMP\rates_stderr.txt"
        log "Exit code: $($proc.ExitCode)"
    } catch {
        log "ERROR: $_"
    }
    Start-Sleep -Seconds 900  # 15 minutes
}
