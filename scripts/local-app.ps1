# Usage: scripts/local-app.ps1 start | stop [--force] | status | wait [seconds]
# Windows counterpart of local-app.sh. Both ports must be free before starting.
# --force still requires recorded ownership; it never permits stopping a foreign process.
param([string]$Command = 'status', [string]$Value, [string]$WorkerPlan)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:HelperPath = $PSCommandPath
$script:JobSource = Join-Path $PSScriptRoot 'local-app-job.cs'

function Import-LocalAppJob {
    if (-not ('LocalAppJob' -as [type])) { Add-Type -Path $script:JobSource }
}

function Get-LocalListeners {
    # Query the whole table. Filtering the cmdlet by a free port can report a
    # not-found error, which must not be confused with an introspection failure.
    @(Get-NetTCPConnection -ErrorAction Stop | Where-Object {
        $_.State -eq 'Listen' -and $_.LocalPort -in @(3000, 8000)
    })
}

function Show-LocalStatus {
    $listeners = @(Get-LocalListeners)
    foreach ($port in @(3000, 8000)) {
        $owners = @($listeners | Where-Object LocalPort -eq $port | Select-Object -ExpandProperty OwningProcess -Unique)
        if ($owners.Count) { Write-Host "port ${port}: BUSY  pid $($owners -join ', ')" }
        else { Write-Host "port ${port}: free" }
    }
    if ($listeners.Count) { return 1 }
    return 0
}

function Join-ProcessArguments([string[]]$Arguments) {
    # Start-Process flattens its argument array, so apply Windows argv quoting once.
    ($Arguments | ForEach-Object {
        '"' + ([regex]::Replace([regex]::Replace($_, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1')) + '"'
    }) -join ' '
}

function Find-LocalPython([string]$Root) {
    $common = & git -C $Root rev-parse --path-format=absolute --git-common-dir 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'cannot locate the shared Git directory' }
    foreach ($base in @($Root, (Split-Path $common -Parent))) {
        $candidate = Join-Path $base '.venv/Scripts/python.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $python = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        if ($python) { return $python.Source }
    }
    throw 'Python is required; install engine/requirements.txt in .venv'
}

function New-LocalLaunchPlan([string]$Root) {
    $python = Find-LocalPython $Root
    $npm = Get-Command npm.cmd -CommandType Application -ErrorAction Stop
    $engineArgs = @('-m', 'uvicorn', 'engine.api:app')
    $envFile = Join-Path $Root '.env'
    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        & $python -c 'import dotenv' 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'install engine/requirements.txt in the selected Python environment before loading .env' }
        $engineArgs += @('--env-file', $envFile)
    }
    $engineArgs += @('--host', '127.0.0.1', '--port', '8000')
    $webRoot = Join-Path $Root 'web'
    $commands = @()
    if (-not (Test-Path -LiteralPath (Join-Path $webRoot 'node_modules') -PathType Container)) {
        $commands += [pscustomobject]@{
            Name = 'npm-ci'; File = $env:ComSpec; Directory = $webRoot; Wait = $true
            Arguments = '/d /s /c ""' + $npm.Source + '" ci"'
        }
    }
    $commands += [pscustomobject]@{
        Name = 'engine'; File = $python; Directory = $Root; Wait = $false
        Arguments = Join-ProcessArguments $engineArgs
    }
    $commands += [pscustomobject]@{
        Name = 'web'; File = $env:ComSpec; Directory = $webRoot; Wait = $false
        Arguments = '/d /s /c ""' + $npm.Source + '" run dev -- --port 3000 --strictPort --host 127.0.0.1"'
    }
    [pscustomobject]@{ Root = $Root; Job = 'Batatis.LocalApp.' + [guid]::NewGuid().ToString('N'); Commands = $commands }
}

function Write-LocalJson([string]$Path, $Data) {
    $temporary = $Path + '.tmp'
    $Data | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Read-LocalOwner([string]$Root, [string]$Logs) {
    $path = Join-Path $Logs 'windows-owner.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $owner = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($owner.Root -ne $Root -or $owner.Job -notmatch '^Batatis\.LocalApp\.[a-f0-9]{32}$' -or
        $owner.ProcessId -le 0 -or $owner.CreationTicks -notmatch '^\d+$') {
        throw 'unrecognized ownership record; preserving it and all processes'
    }
    return $owner
}

function Invoke-LocalWorker([string]$PlanPath) {
    $plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
    $logs = Split-Path $PlanPath -Parent
    Import-LocalAppJob
    $job = [LocalAppJob]::Create($plan.Job)
    $phase = 'ownership setup'
    try {
        $self = [Diagnostics.Process]::GetCurrentProcess()
        Write-LocalJson (Join-Path $logs 'windows-owner.json') ([pscustomobject]@{
            Root = $plan.Root; Job = $plan.Job; ProcessId = $PID
            CreationTicks = $self.StartTime.ToUniversalTime().Ticks.ToString()
        })
        $phase = 'port inspection'
        if (@(Get-LocalListeners).Count) { throw 'a port became busy before startup' }
        foreach ($item in $plan.Commands) {
            $phase = $item.Name
            if (-not $item.Wait -and @(Get-LocalListeners | Where-Object {
                -not [LocalAppJob]::Contains($plan.Job, $_.OwningProcess)
            }).Count) { throw 'a port became busy before startup' }
            $originalCases = $env:BATATIS_CASES
            try {
                if ($item.Name -eq 'engine' -and -not $env:BATATIS_CASES) {
                    $env:BATATIS_CASES = Join-Path $plan.Root '.data/cases.sqlite'
                }
                $child = Start-Process -FilePath $item.File -ArgumentList $item.Arguments -WorkingDirectory $item.Directory `
                    -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs ($item.Name + '.log')) `
                    -RedirectStandardError (Join-Path $logs ($item.Name + '.err.log'))
            }
            finally { $env:BATATIS_CASES = $originalCases }
            if ($item.Wait) {
                $null = $child.Handle
                $child.WaitForExit()
                if ($child.ExitCode -ne 0) { throw "$($item.Name) failed; see its log" }
            }
            $child.Dispose()
        }
        Write-LocalJson (Join-Path $logs 'windows-started.json') @{ Job = $plan.Job }
        while ($true) { Start-Sleep -Seconds 1 }
    }
    catch {
        [Console]::Error.WriteLine("local-app: supervisor failed during $phase; inspect the service logs in .data/local-app.")
        throw
    }
    finally { $job.Dispose() }
}

function Start-LocalWorker($Plan, [string]$Logs) {
    $planPath = Join-Path $Logs 'windows-launch.json'
    Write-LocalJson $planPath $Plan
    $shell = (Get-Process -Id $PID).Path
    $arguments = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', $script:HelperPath, '-WorkerPlan', $planPath)
    $worker = Start-Process -FilePath $shell -ArgumentList $arguments -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $Logs 'supervisor.log') -RedirectStandardError (Join-Path $Logs 'supervisor.err.log')
    # Keep a handle to the process we just created for rollback, never a later PID lookup.
    $null = $worker.Handle
    return $worker
}

function Test-LocalHttp([string]$Url) {
    try {
        $request = [Net.HttpWebRequest]::Create($Url)
        $request.Proxy = $null
        $request.Timeout = 1500
        $response = $request.GetResponse()
        $response.Dispose()
        return $true
    }
    catch { return $false }
}

function Test-LocalStarted($Plan, [string]$Logs) {
    $startedPath = Join-Path $Logs 'windows-started.json'
    if (-not (Test-Path -LiteralPath $startedPath)) { return $false }
    $started = Get-Content -LiteralPath $startedPath -Raw | ConvertFrom-Json
    return ($started.Job -eq $Plan.Job)
}

function Test-LocalReady($Plan, [string]$Logs) {
    if (-not (Test-LocalStarted $Plan $Logs)) { return $false }
    $listeners = @(Get-LocalListeners)
    foreach ($port in @(3000, 8000)) {
        $owners = @($listeners | Where-Object LocalPort -eq $port)
        if (-not $owners.Count) { return $false }
        foreach ($owner in $owners) {
            if (-not [LocalAppJob]::Contains($Plan.Job, $owner.OwningProcess)) { return $false }
        }
    }
    return ((Test-LocalHttp 'http://127.0.0.1:8000/docs') -and (Test-LocalHttp 'http://127.0.0.1:3000/'))
}

function Remove-LocalAttempt([string]$Logs) {
    foreach ($name in @('windows-owner.json', 'windows-launch.json', 'windows-started.json')) {
        $path = Join-Path $Logs $name
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
}

function Start-LocalApp([string]$Root, [string]$Logs, [int]$TimeoutSeconds = 60) {
    if ((Show-LocalStatus) -ne 0) {
        Write-Host 'local-app: not starting; a port is in use. Ask its owner to stop it, or use wait.'
        return 3
    }
    if ((Read-LocalOwner $Root $Logs) -or (Test-Path -LiteralPath (Join-Path $Logs 'windows-launch.json'))) {
        throw 'a previous launch record exists; run stop first. Unknown ownership is preserved.'
    }
    $plan = New-LocalLaunchPlan $Root
    Import-LocalAppJob
    $worker = $null
    try {
        $worker = Start-LocalWorker $plan $Logs
        $setupTimer = [Diagnostics.Stopwatch]::StartNew()
        $readyTimer = $null
        while ($true) {
            if ($worker.HasExited) { throw 'startup process exited; see supervisor.err.log' }
            if (-not $readyTimer -and (Test-LocalStarted $plan $Logs)) {
                $readyTimer = [Diagnostics.Stopwatch]::StartNew()
            }
            if ($readyTimer) {
                if (Test-LocalReady $plan $Logs) {
                    Write-Host "local-app: up. Web http://localhost:3000   Engine http://127.0.0.1:8000/docs   logs $Logs"
                    return 0
                }
                if ($readyTimer.Elapsed.TotalSeconds -ge $TimeoutSeconds) { throw "did not come up within ${TimeoutSeconds}s" }
            }
            elseif ($setupTimer.Elapsed.TotalSeconds -ge 600) { throw 'dependency setup exceeded 600s' }
            Start-Sleep -Milliseconds 250
        }
    }
    catch {
        if ($worker) {
            if (-not $worker.HasExited) {
                $worker.Kill()
                if (-not $worker.WaitForExit(5000)) { throw 'could not confirm cleanup; preserving ownership records' }
            }
            Remove-LocalAttempt $Logs
        }
        Write-Host "local-app: startup failed; this attempt was stopped. Logs: $Logs"
        return 1
    }
    finally { if ($worker) { $worker.Dispose() } }
}

function Stop-LocalApp([string]$Root, [string]$Logs) {
    $owner = Read-LocalOwner $Root $Logs
    if (-not $owner) {
        if (Test-Path -LiteralPath (Join-Path $Logs 'windows-launch.json')) {
            Write-Host 'local-app: incomplete launch record; preserving it and all processes.'
            return 1
        }
        Write-Host 'local-app: no processes recorded for this worktree; leaving all other processes.'
        return 0
    }
    Import-LocalAppJob
    if (-not [LocalAppJob]::Stop($owner.Job, $owner.ProcessId, [long]$owner.CreationTicks)) {
        Write-Host 'local-app: ownership could not be verified; preserving the record and all processes.'
        return 1
    }
    Remove-LocalAttempt $Logs
    Write-Host 'local-app: stopped the processes started by this worktree.'
    return 0
}

function Wait-LocalApp([string]$Root, [string]$Logs, [int]$Seconds) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (@(Get-LocalListeners).Count) {
        if ($timer.Elapsed.TotalSeconds -ge $Seconds) {
            $null = Show-LocalStatus
            Write-Host "local-app: still busy after ${Seconds}s."
            return 3
        }
        Start-Sleep -Milliseconds ([int][Math]::Min(1000, [Math]::Max(1, ($Seconds - $timer.Elapsed.TotalSeconds) * 1000)))
    }
    return Invoke-LocalApp $Root 'start' ''
}

function Invoke-LocalApp([string]$Root, [string]$Action, [string]$Argument) {
    $seconds = 600
    if ($Action -notin @('start', 'stop', 'status', 'wait') -or
        ($Action -in @('start', 'status') -and $Argument) -or
        ($Action -eq 'stop' -and $Argument -and $Argument -ne '--force') -or
        ($Action -eq 'wait' -and $Argument -and (-not [int]::TryParse($Argument, [ref]$seconds) -or $seconds -lt 0))) {
        Write-Host 'Usage: scripts/local-app.ps1 start | stop [--force] | status | wait [seconds]'
        return 2
    }
    if ($Action -eq 'status') { return Show-LocalStatus }
    $logs = Join-Path $Root '.data/local-app'
    if ($Action -eq 'wait') { return Wait-LocalApp $Root $logs $seconds }
    $null = New-Item -ItemType Directory -Path $logs -Force
    try { $lock = [IO.File]::Open((Join-Path $logs 'windows.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'another local-app command is active for this worktree' }
    try {
        switch ($Action) {
            start { return Start-LocalApp $Root $logs }
            stop { return Stop-LocalApp $Root $logs }
        }
    }
    finally { $lock.Dispose() }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        if ($WorkerPlan) { Invoke-LocalWorker $WorkerPlan; exit 0 }
        if ($Command -eq 'stop' -and -not $Value -and $args.Count -eq 1 -and $args[0] -eq '--force') {
            $Value = '--force'
        }
        elseif ($args.Count) { throw 'too many arguments' }
        exit (Invoke-LocalApp (Split-Path $PSScriptRoot -Parent) $Command $Value)
    }
    catch {
        # Do not print exception details, which can include inherited environment values.
        [Console]::Error.WriteLine('local-app: command failed; no unverified processes were stopped. Check prerequisites and ownership records in .data/local-app.')
        exit 2
    }
}
