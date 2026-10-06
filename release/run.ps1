<#
    NanoVox Insights - load and run the shipped image.

    Needs Docker and nothing else: no Python, no Node, no registry login.

        .\run.ps1
        .\run.ps1 -Port 9000

    Set OPENAI_API_KEY first to enable the AI insight panels; without it the
    application runs on every other screen and shows those panels as
    unavailable, which is a designed state rather than a fault.
#>
[CmdletBinding()]
param(
    [int] $Port = 8050
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Image     = 'nanovox-insights:1.0.0'
$Volume    = 'nanovox-data'
$Container = 'nanovox'
$Here      = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say([string] $Message) { Write-Host "`n== $Message" }

# Resolve docker.exe rather than trusting name resolution: PowerShell prefers an
# ExternalScript on PATH over an Application of the same name, which is exactly
# how `npm` resolves to npm.ps1 and fails under strict mode on this project.
$Docker = (Get-Command 'docker.exe' -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source)
if (-not $Docker) { throw 'Docker is not installed or not on PATH.' }

<#
    Run docker and hand back its exit code without throwing.

    Windows PowerShell 5.1 wraps each stderr line of a native command in an
    ErrorRecord when that stream is redirected, and $ErrorActionPreference =
    'Stop' then makes an ordinary "no such image" into a terminating error. So
    stderr is swallowed here with the preference relaxed, and callers decide
    what a non-zero exit means — several of these commands are questions, not
    instructions, and are *expected* to fail on a clean machine.
#>
function Invoke-Docker {
    param(
        [Parameter(Mandatory)] [string[]] $DockerArgs,
        [switch] $Quiet
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Quiet) {
            & $Docker @DockerArgs 2>&1 | Out-Null
        } else {
            & $Docker @DockerArgs 2>&1 | ForEach-Object { "$_" }
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Assert-Docker {
    param([Parameter(Mandatory)] [string[]] $DockerArgs, [Parameter(Mandatory)] [string] $What)
    $code = Invoke-Docker -DockerArgs $DockerArgs -Quiet
    if ($code -ne 0) { throw "$What failed with exit code $code." }
}

if ((Invoke-Docker -DockerArgs @('info') -Quiet) -ne 0) {
    throw 'Docker is installed but the engine is not running.'
}

Say 'Loading the image'
if ((Invoke-Docker -DockerArgs @('image', 'inspect', $Image) -Quiet) -eq 0) {
    Write-Host '   already loaded.'
} else {
    Assert-Docker -DockerArgs @('load', '-i', (Join-Path $Here 'nanovox-insights-1.0.0.tar.gz')) `
        -What 'Loading the image'
}

Say 'Preparing the database'
# Test for the database itself, not for the volume. A seed that failed halfway
# leaves the volume behind with nothing in it, and "the volume exists" would
# then skip the copy and start the application on an empty corpus - every screen
# in its withheld state, which reads as a broken build rather than an empty one.
$seeded = $false
if ((Invoke-Docker -DockerArgs @('volume', 'inspect', $Volume) -Quiet) -eq 0) {
    $probe = @('run', '--rm', '-v', "${Volume}:/data", 'alpine',
               'test', '-s', '/data/db/nanovox_insights.db')
    if ((Invoke-Docker -DockerArgs $probe -Quiet) -eq 0) { $seeded = $true }
}

if ($seeded) {
    Write-Host '   database already present; leaving it alone.'
} else {
    Assert-Docker -DockerArgs @('volume', 'create', $Volume) -What 'Creating the volume'

    # The seeder has to be *running*, not merely created: `docker cp` into a
    # stopped container writes to its own filesystem layer, and the volume is
    # not mounted until the container runs, so the copy would land nowhere.
    $seeder = (& $Docker run -d -v "${Volume}:/data" alpine sleep 300)
    if ($LASTEXITCODE -ne 0) { throw 'Starting the seeder failed.' }
    $seeder = "$seeder".Trim()

    try {
        Assert-Docker -DockerArgs @('exec', $seeder, 'mkdir', '-p', '/data/db', '/data/logs') `
            -What 'Creating the data directories'
        Assert-Docker -DockerArgs @('cp', (Join-Path $Here 'nanovox_insights.db'),
            "${seeder}:/data/db/nanovox_insights.db") -What 'Copying the database'
        # chown after the copy: a file copied in arrives owned by root, and the
        # application runs as uid 10001 and could not write it - reads would
        # work and the first action-board click would fail.
        Assert-Docker -DockerArgs @('exec', $seeder, 'chown', '-R', '10001:10001', '/data') `
            -What 'Setting ownership'
    } finally {
        # Whatever happened, do not leave a container holding the volume: the
        # next attempt could then not delete it to start over, and would
        # silently reuse an empty one.
        Invoke-Docker -DockerArgs @('rm', '-f', $seeder) -Quiet | Out-Null
    }
    Write-Host '   seeded with the shipped corpus.'
}

Say 'Starting'
Invoke-Docker -DockerArgs @('rm', '-f', $Container) -Quiet | Out-Null

$runArgs = @(
    'run', '-d',
    '--name', $Container,
    '-p', "${Port}:8000",
    '-v', "${Volume}:/app/data",
    '--restart', 'unless-stopped'
)
if ($env:OPENAI_API_KEY) { $runArgs += @('-e', "OPENAI_API_KEY=$env:OPENAI_API_KEY") }
$provider = if ($env:LLM_PROVIDER) { $env:LLM_PROVIDER } else { 'ollama' }
$runArgs += @('-e', "LLM_PROVIDER=$provider", $Image)

Assert-Docker -DockerArgs $runArgs -What 'Starting the container'

Say 'Waiting for health'
$state = 'starting'
foreach ($attempt in 1..30) {
    $ErrorActionPreference = 'Continue'
    $state = "$(& $Docker inspect -f '{{.State.Health.Status}}' $Container 2>$null)".Trim()
    $ErrorActionPreference = 'Stop'
    if ($state -eq 'healthy') { break }
    Start-Sleep -Seconds 2
}

if ($state -ne 'healthy') {
    Write-Host "Did not become healthy (state: '$state'). Last lines:"
    Invoke-Docker -DockerArgs @('logs', '--tail', '30', $Container)
    throw "Container is '$state'."
}

Say 'Ready'
Write-Host "   http://localhost:$Port"
Write-Host ''
Write-Host "   stop:  docker stop $Container"
Write-Host "   logs:  docker logs -f $Container"
