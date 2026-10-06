<#
.SYNOPSIS
    Deploys NanoVox Insights on this machine, and updates it. Run it again to
    redeploy.

.DESCRIPTION
    One process serves the whole application: the API and the built frontend on
    a single port. There is no web server to configure, no CORS to get right and
    no second origin, because there is only one.

    This is the script that makes the app reachable from another machine - a
    laptop on the company VPN, say. It opens the inbound port itself, and the
    verification at the end answers on a real interface rather than only on
    loopback, because a deployment reachable from nowhere used to pass every
    check here. `scripts\start.bat` is development mode:
    two servers (Vite on 5173, uvicorn on 8000), each bound to 127.0.0.1 by
    default, and the frontend's `.env` points at an absolute
    `http://127.0.0.1:8000/api/v1`. Run that on a VM and it works perfectly,
    from inside the VM, to the VM. Nothing outside it can reach 127.0.0.1, and
    even if it could, the browser on the *other* machine would still try to
    call its own localhost for the API, not the VM's. This script exists to
    not have either problem: one origin, bound to every interface, with the
    firewall opened for it.

    Every step is idempotent. Running this after a `git pull` is the update
    path - it reinstalls what changed, rebuilds the frontend, migrates the
    database and restarts the service.

.PARAMETER Port
    Port to listen on. Default 8000.

.PARAMETER BindAddress
    Address to bind. Defaults to 0.0.0.0 so other machines can reach it; use
    127.0.0.1 to keep it local to this host (for example, fronting it with the
    Cloudflare Tunnel in scripts\cloudflared, where the tunnel should be the
    only way in).

.PARAMETER NoService
    Set up everything but do not register or start the scheduled task. Useful
    for a first run you want to watch in the foreground.

.EXAMPLE
    .\scripts\deploy.ps1

.EXAMPLE
    .\scripts\deploy.ps1 -Port 8080 -BindAddress 127.0.0.1
#>
[CmdletBinding()]
param(
    [int]    $Port = 8000,
    [string] $BindAddress = '0.0.0.0',
    [switch] $NoService
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root 'Code\Backend'
$Frontend = Join-Path $Root 'Code\Frontend'
$Python   = Join-Path $Backend '.venv\Scripts\python.exe'
$TaskName = 'NanoVoxInsights'
$FirewallRule = 'NanoVox Insights'

function Step([string] $Message) { Write-Host "`n=== $Message" -ForegroundColor Cyan }
function Note([string] $Message) { Write-Host "    $Message" -ForegroundColor DarkGray }

# Native tools signal failure through the exit code, which PowerShell does not
# treat as terminating. Without this, a failed install would be reported as a
# successful deployment.
function Invoke-Checked([string] $What, [scriptblock] $Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE." }
}

# --- 1. Prerequisites ------------------------------------------------------
Step 'Checking prerequisites'

# Checked first, before several minutes of installing and building: registering
# a task that runs as SYSTEM needs elevation, and discovering that at the end
# would waste the whole run.
if (-not $NoService) {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this from an elevated PowerShell (Run as Administrator), or pass -NoService to set everything up without registering the startup task.'
    }
    Note 'Running elevated'
}

$pythonExe = $null
foreach ($candidate in @('3.12', '3.11', '3.10')) {
    # The launcher reports a missing version on stderr and a non-zero exit; both
    # are expected while probing, so they must not stop the script.
    $found = & { $ErrorActionPreference = 'SilentlyContinue'; py "-$candidate" -c 'import sys; print(sys.executable)' 2>$null }
    if ($LASTEXITCODE -eq 0 -and $found) { $pythonExe = $found; Note "Python $candidate at $found"; break }
}
if (-not $pythonExe) {
    throw 'No Python 3.10-3.12 found. Install one from python.org (tick "Add to PATH" and "py launcher"), then re-run.'
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js was not found on PATH. Install Node 20+ from nodejs.org, then re-run.'
}
Note "Node $(node --version)"

# `npm` on Windows is three files, and PowerShell prefers the wrong one:
# npm.ps1 beats npm.cmd in command resolution, so `npm install` runs a
# PowerShell script in this session rather than a process beside it. That
# script inherits nothing useful and brings its own problems -- older ones
# read `$MyInvocation.Statement`, which does not exist on Windows PowerShell
# 5.1, and under the strict mode set at the top of this file that is a
# terminating error:
#
#     The property 'Statement' cannot be found on this object.
#
# npm later guarded that line with Get-Member; a Server with an older npm
# has no such guard, and the deploy died at "Building the frontend" with no
# line number, because the throw came from inside npm's own shim.
#
# Turning strict mode off does not help: npm.ps1 sets `Set-StrictMode
# -Version Latest` itself, on its first line. The fix is to not run it. The
# .cmd is a native process, so none of this session's state reaches it.
$Npm = (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source)
if (-not $Npm) {
    throw ('npm.cmd was not found beside node. Install Node 20+ from nodejs.org rather ' +
           'than a standalone npm, so the whole toolchain is on PATH together.')
}
Note "npm $(& $Npm --version)"

# --- 2. Backend dependencies ----------------------------------------------
Step 'Installing backend dependencies'
if (-not (Test-Path $Python)) {
    Note 'Creating virtual environment'
    Invoke-Checked 'venv creation' { & $pythonExe -m venv (Join-Path $Backend '.venv') }
}
Invoke-Checked 'pip upgrade'  { & $Python -m pip install --upgrade pip --quiet }
Invoke-Checked 'pip install'  { & $Python -m pip install -r (Join-Path $Backend 'requirements.txt') --quiet }

# --- 3. Configuration ------------------------------------------------------
Step 'Configuring'
$envFile = Join-Path $Backend '.env'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Backend '.env.example') $envFile
    Note "Created $envFile from the template"
    Note 'Set OPENAI_API_KEY / ANTHROPIC_API_KEY in it if you intend to use a cloud provider.'
} else {
    Note "Keeping the existing $envFile"
}

# Written every time: these three are the deployment's own settings, and a stale
# port or bind address in .env would silently override the arguments given here.
$deployed = @{
    APP_HOST = $BindAddress
    APP_PORT = "$Port"
    APP_ENV  = 'prod'
}
# A plain loop rather than List.FindIndex with a predicate: Windows PowerShell
# 5.1 will not reliably convert a scriptblock to a Predicate<string> delegate.
$lines = @(Get-Content $envFile)
foreach ($key in $deployed.Keys) {
    $line    = "$key=$($deployed[$key])"
    $replaced = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$key\s*=") { $lines[$i] = $line; $replaced = $true; break }
    }
    if (-not $replaced) { $lines += $line }
}
Set-Content -Path $envFile -Value $lines -Encoding utf8
Note "APP_HOST=$BindAddress  APP_PORT=$Port  APP_ENV=prod"

# --- 4. Database -----------------------------------------------------------
Step 'Applying database migrations'
# SQLite creates the file on first connect but not the tables in it. A no-op
# once the schema is current.
Push-Location $Backend
try { Invoke-Checked 'alembic upgrade' { & $Python -m alembic upgrade head } }
finally { Pop-Location }

# --- 5. Frontend -----------------------------------------------------------
Step 'Building the frontend'
Push-Location $Frontend
try {
    # `npm ci` is the reproducible install, but it deletes node_modules first -
    # which fails with EPERM if anything is holding a file in there, such as a
    # dev server left running. It is therefore used only on a clean tree; an
    # existing one is updated in place, which needs no delete.
    if ((Test-Path 'package-lock.json') -and -not (Test-Path 'node_modules')) {
        Invoke-Checked 'npm ci' { & $Npm ci --silent }
    } else {
        Invoke-Checked 'npm install' { & $Npm install --silent }
    }
    # .env.production sets VITE_API_BASE_URL=/api/v1 - the API is this same
    # process, so the bundle is host-independent and never needs rebuilding
    # because an address changed. Without it, the build falls back to .env's
    # absolute http://127.0.0.1:8000/api/v1, which works from this machine and
    # from nowhere else - the exact failure this script exists to avoid.
    Invoke-Checked 'npm run build' { & $Npm run build }
} finally { Pop-Location }

$dist = Join-Path $Frontend 'dist\index.html'
if (-not (Test-Path $dist)) { throw "Frontend build produced no $dist." }
Note 'Built. The API process will serve it.'

# --- 6. Firewall -----------------------------------------------------------
# The .DESCRIPTION has always promised the firewall was opened for this, and
# until now the script only printed the command at the end and left it to be
# noticed. A default Windows Server blocks the inbound port, so the deploy
# finished green and the application was reachable from nowhere -- the exact
# failure this script exists to avoid, arrived at by a different road.
#
# Nothing to open when bound to loopback: there is no inbound traffic to allow.
if ($BindAddress -eq '127.0.0.1') {
    Step 'No firewall rule needed'
    Note 'Bound to 127.0.0.1, so nothing outside this machine can reach it by design.'
} elseif ($NoService) {
    # -NoService does not elevate, and New-NetFirewallRule needs it.
    Step 'Skipping the firewall rule (-NoService)'
    Note "Open it yourself: New-NetFirewallRule -DisplayName '$FirewallRule' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow"
} else {
    Step 'Opening the firewall'
    # Run with strict mode off, in a child scope so the rest of the script
    # keeps it. The NetSecurity cmdlets are generated from CDXML rather than
    # written, and the script they generate is not strict-mode clean on every
    # Windows build: a deploy on Server reported
    #
    #     The property 'Statement' cannot be found on this object.
    #     FullyQualifiedErrorId : PropertyNotFoundStrict
    #
    # from inside them, with no line number, while the same calls are clean
    # on Windows 11. Their own internals are not this script's business to
    # be strict about.
    #
    # Removed and recreated rather than edited: a redeploy on a different port
    # would otherwise leave the old port open and the new one shut, which is
    # both a hole and a failure at once.
    & {
        Set-StrictMode -Off
        Get-NetFirewallRule -DisplayName $FirewallRule -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $FirewallRule -Direction Inbound `
            -Protocol TCP -LocalPort $Port -Action Allow -Profile Any | Out-Null
    }
    Note "Inbound TCP $Port allowed as '$FirewallRule'"
}

# --- 7. Service ------------------------------------------------------------
if ($NoService) {
    Step 'Skipping service registration (-NoService)'
    Write-Host "`nStart it in the foreground with:" -ForegroundColor Green
    Write-Host "    cd `"$Backend`"; .\.venv\Scripts\python.exe -m uvicorn frameworks_drivers.main:app --host $BindAddress --port $Port`n"
    return
}

Step 'Registering the startup task'
# Task Scheduler rather than a service wrapper: it is built into Windows,
# survives reboots and restarts the process if it dies.
# Strict mode off inside, for the same reason as the firewall block above:
# the ScheduledTasks cmdlets are CDXML-generated and their own internals are
# not strict-mode clean on every Windows build.
& {
    Set-StrictMode -Off

    $action = New-ScheduledTaskAction -Execute $Python `
        -Argument "-m uvicorn frameworks_drivers.main:app --host $BindAddress --port $Port" `
        -WorkingDirectory $Backend

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $TaskName -Force `
        -Action $action `
        -Trigger (New-ScheduledTaskTrigger -AtStartup) `
        -Principal (New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest) `
        -Settings $settings | Out-Null

    # Stop before start: a redeploy must not leave the previous build running.
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $TaskName
}

# --- 8. Verify -------------------------------------------------------------
Step 'Verifying'
$probe = if ($BindAddress -eq '0.0.0.0') { '127.0.0.1' } else { $BindAddress }
$base  = "http://${probe}:$Port"

$ready = $false
foreach ($attempt in 1..20) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod "$base/api/v1/health" -TimeoutSec 3
        if ($health) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    throw "The application did not answer on $base within 20s. Check data\logs\nanovox-insights-app.log."
}
Note "API healthy at $base/api/v1/health"

# The one check that catches a broken deployment which still looks fine: a
# client-side route has no file behind it, so it proves the SPA fallback works.
$page = Invoke-WebRequest "$base/calls" -TimeoutSec 5
if ($page.StatusCode -ne 200) { throw "Client-side route /calls returned $($page.StatusCode)." }
Note 'Client-side routing works'

$addresses = @(& {
    Set-StrictMode -Off   # NetTCPIP is CDXML too; see the firewall block.
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -ExpandProperty IPAddress
})

# Everything above this point was answered over loopback, which is the one
# address that proves nothing: `start.bat` binds to 127.0.0.1 too, and this
# script's whole purpose is to not be that. A deployment reachable from
# nowhere passed every check here and printed success in green.
#
# What this establishes is that the process is listening on a real interface
# rather than on loopback alone. It does NOT establish that the firewall
# lets anyone in: traffic from this machine to its own address is handled
# locally and does not cross the inbound rule. Only the other machine can
# answer that, which is why the summary below asks for it rather than
# claiming it.
if ($BindAddress -eq '0.0.0.0' -and $addresses.Count -gt 0) {
    $external = $addresses[0]
    try {
        $reached = Invoke-RestMethod "http://${external}:$Port/api/v1/health" -TimeoutSec 5
        if (-not $reached) { throw 'no answer' }
        Note "Listening on $external, not only on loopback"
    } catch {
        throw ("Healthy on 127.0.0.1 but not on $external`:$Port. The process is bound to " +
               'loopback rather than to every interface, so no other machine can reach it. ' +
               "Check APP_HOST in $envFile.")
    }
}

Write-Host "`nNanoVox Insights is running." -ForegroundColor Green
Write-Host "    Local:   $base"
foreach ($address in $addresses) { Write-Host "    Network: http://${address}:$Port" }
Write-Host @"

    Manage:  Stop-ScheduledTask -TaskName '$TaskName'
             Start-ScheduledTask -TaskName '$TaskName'
    Logs:    $Root\data\logs
    Update:  git pull; .\scripts\deploy.ps1

"@
if ($BindAddress -ne '127.0.0.1') {
    # The firewall rule is made above now, and the checks above prove the
    # process is on a real interface. The one thing this machine cannot test
    # about itself is whether anything else can get in, so that is the only
    # thing left to ask for.
    Write-Host "    Confirm from another machine on the network or VPN:" -ForegroundColor Yellow
    foreach ($address in $addresses) {
        Write-Host "        Test-NetConnection $address -Port $Port"
    }
    Write-Host "    then browse to one of the Network addresses above - not 127.0.0.1 or" -ForegroundColor Yellow
    Write-Host "    localhost, which only ever means 'the machine you are sitting at'.`n"
}
