# Self-contained Windows tests. No Pester, app servers, or alternate ports.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot '../local-app.ps1')
$sourceHelper = $script:HelperPath
$sourceJob = $script:JobSource
$repository = Split-Path (Split-Path $sourceHelper -Parent) -Parent
$shellPath = (Get-Process -Id $PID).Path
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('Batatis local app tests ' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testRoot
$failures = 0
$checks = 0

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Check([string]$Name, [scriptblock]$Body) {
    $script:checks++
    try { & $Body; Write-Host "PASS $Name" }
    catch { $script:failures++; Write-Host "FAIL $Name -- $($_.Exception.Message)" }
}

function Await([scriptblock]$Condition, [int]$Seconds = 20) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (-not (& $Condition)) {
        if ($timer.Elapsed.TotalSeconds -ge $Seconds) { throw 'test condition timed out' }
        Start-Sleep -Milliseconds 100
    }
}

function New-Fixture {
    $root = Join-Path $testRoot ([guid]::NewGuid().ToString('N') + ' spaced checkout')
    $logs = Join-Path $root '.data/local-app'
    $scripts = Join-Path $root 'scripts'
    $null = New-Item -ItemType Directory -Path $logs, $scripts
    Copy-Item -LiteralPath $sourceHelper -Destination (Join-Path $scripts 'local-app.ps1')
    Copy-Item -LiteralPath $sourceJob -Destination (Join-Path $scripts 'local-app-job.cs')
    # Only the fixture worker sees free ports. It launches sleep processes, never servers.
    @'
param([string]$WorkerPlan)
$planInput = $WorkerPlan
. (Join-Path $PSScriptRoot 'local-app.ps1')
function Get-LocalListeners { @() }
Invoke-LocalWorker $planInput
'@ | Set-Content -LiteralPath (Join-Path $scripts 'worker.ps1')
    @'
param([string]$OutputFile)
[pscustomobject]@{ ProcessId=$PID; Cases=$env:BATATIS_CASES; EnvProbe=$env:BATATIS_TEST_ENV_FILE } |
    ConvertTo-Json | Set-Content -LiteralPath $OutputFile
while ($true) { Start-Sleep -Seconds 1 }
'@ | Set-Content -LiteralPath (Join-Path $scripts 'sleep.ps1')
    [pscustomobject]@{ Root = $root; Logs = $logs; Scripts = $scripts }
}

function New-DummyPlan($Fixture, [switch]$ParentExits) {
    $sleeper = Join-Path $Fixture.Scripts 'sleep.ps1'
    $output = Join-Path $Fixture.Root 'child identity.json'
    $arguments = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $sleeper, $output)
    if ($ParentExits) {
        @'
param([string]$Shell, [string]$SleepScript, [string]$OutputFile)
. (Join-Path $PSScriptRoot 'local-app.ps1')
[IO.File]::WriteAllText((Join-Path (Split-Path $PSScriptRoot -Parent) 'parent.id'), "$PID")
$a = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $SleepScript, $OutputFile)
$null = Start-Process -FilePath $Shell -ArgumentList $a -WindowStyle Hidden -PassThru
'@ | Set-Content -LiteralPath (Join-Path $Fixture.Scripts 'exiting-parent.ps1')
        $arguments = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
            (Join-Path $Fixture.Scripts 'exiting-parent.ps1'), $shellPath, $sleeper, $output)
    }
    [pscustomobject]@{
        Root = $Fixture.Root; Job = 'Batatis.LocalApp.' + [guid]::NewGuid().ToString('N')
        Commands = @([pscustomobject]@{
            Name = 'engine'; File = $shellPath; Directory = $Fixture.Root; Wait = $false
            Arguments = Join-ProcessArguments $arguments
        })
    }
}

function Start-Dummy($Fixture, $Plan) {
    $script:HelperPath = Join-Path $Fixture.Scripts 'worker.ps1'
    $worker = Start-LocalWorker $Plan $Fixture.Logs
    try {
        Await { $worker.HasExited -or (Test-Path -LiteralPath (Join-Path $Fixture.Root 'child identity.json')) }
        if ($worker.HasExited) {
            $message = Get-Content -LiteralPath (Join-Path $Fixture.Logs 'supervisor.err.log') -Raw
            throw "dummy supervisor exited: $message"
        }
        return $worker
    }
    catch { Cleanup-Dummy $worker; throw }
}

function Child-Identity($Fixture) {
    Get-Content -LiteralPath (Join-Path $Fixture.Root 'child identity.json') -Raw | ConvertFrom-Json
}

function Is-Running([int]$ProcessId) {
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    return ($null -ne $process)
}

function Cleanup-Dummy($Worker) {
    # Only ever terminate the retained handle returned by our own Start-Process.
    if ($Worker) {
        if (-not $Worker.HasExited) { $Worker.Kill(); $Worker.WaitForExit() }
        $Worker.Dispose()
    }
}

try {
    Check 'PowerShell parses and native job helper compiles' {
        $tokens = $null
        $parseErrors = $null
        $null = [Management.Automation.Language.Parser]::ParseFile($sourceHelper, [ref]$tokens, [ref]$parseErrors)
        Assert ($parseErrors.Count -eq 0) 'launcher has PowerShell syntax errors'
        Import-LocalAppJob
    }
    Check 'status reports both ports and start refuses either busy port' {
        foreach ($port in @(3000, 8000)) {
            $script:busyPort = $port
            function Get-NetTCPConnection { [pscustomobject]@{ State = 'Listen'; LocalPort = $script:busyPort; OwningProcess = 123 } }
            function New-LocalLaunchPlan { throw 'must not launch when either port is busy' }
            Assert ((Show-LocalStatus) -eq 1) 'status did not report busy'
            Assert ((Start-LocalApp $testRoot $testRoot) -eq 3) 'start did not refuse the busy port'
        }
    }
    Check 'port introspection errors fail closed' {
        function Get-NetTCPConnection { throw 'simulated permission failure' }
        $caught = $false
        try { $null = Start-LocalApp $testRoot $testRoot } catch { $caught = $true }
        Assert $caught 'start treated failed introspection as a free port'
        $caught = $false
        try { $null = Wait-LocalApp $testRoot $testRoot 0 } catch { $caught = $true }
        Assert $caught 'wait treated failed introspection as a free port'
    }
    Check 'wait timeout is bounded and never starts on a busy port' {
        function Get-NetTCPConnection { [pscustomobject]@{ State = 'Listen'; LocalPort = 3000; OwningProcess = 123 } }
        function Start-LocalApp { throw 'must not start while busy' }
        $timer = [Diagnostics.Stopwatch]::StartNew()
        Assert ((Wait-LocalApp $testRoot $testRoot 1) -eq 3) 'wrong timeout exit code'
        Assert ($timer.Elapsed.TotalSeconds -lt 3) 'wait overshot its deadline'
    }
    Check 'wait starts once both ports are free' {
        function Get-NetTCPConnection { @() }
        function Start-LocalApp { return 42 }
        Assert ((Wait-LocalApp $testRoot $testRoot 0) -eq 42) 'wait did not start'
    }
    Check 'invalid CLI arguments and legacy force cannot bypass ownership' {
        foreach ($pair in @(@('wait', '-1'), @('wait', 'x'), @('start', '--force'), @('stop', 'foreign'))) {
            Assert ((Invoke-LocalApp $testRoot $pair[0] $pair[1]) -eq 2) 'invalid argument accepted'
        }
        Assert ((Invoke-LocalApp $testRoot 'stop' '--force') -eq 0) 'empty stop failed'
    }
    Check 'incomplete or malformed ownership remains untouched and blocks startup' {
        $fixture = New-Fixture
        function Get-LocalListeners { @() }
        function New-LocalLaunchPlan { throw 'must not overwrite an unknown launch' }
        $launch = Join-Path $fixture.Logs 'windows-launch.json'
        'interrupted launch' | Set-Content -LiteralPath $launch
        $caught = $false
        try { $null = Start-LocalApp $fixture.Root $fixture.Logs } catch { $caught = $true }
        Assert $caught 'incomplete launch was replaced'
        Assert ((Stop-LocalApp $fixture.Root $fixture.Logs) -eq 1) 'unknown launch did not refuse stop'
        Assert ((Get-Content -LiteralPath $launch -Raw).Trim() -eq 'interrupted launch') 'unknown launch was changed'
        '{invalid json' | Set-Content -LiteralPath (Join-Path $fixture.Logs 'windows-owner.json')
        $caught = $false
        try { $null = Stop-LocalApp $fixture.Root $fixture.Logs } catch { $caught = $true }
        Assert $caught 'malformed ownership was accepted'
    }
    Check 'Python discovery finds the shared Windows venv and prefers a worktree venv' {
        $python = Find-LocalPython $repository
        Assert ($python -like '*\.venv\Scripts\python.exe') 'shared Windows venv not found'
        $fixture = New-Fixture
        $null = & git -C $fixture.Root init --quiet
        $venv = Join-Path $fixture.Root '.venv/Scripts'
        $null = New-Item -ItemType Directory -Path $venv
        $localPython = Join-Path $venv 'python.exe'
        $null = New-Item -ItemType File -Path $localPython
        Assert ((Find-LocalPython $fixture.Root) -eq $localPython) 'worktree venv not preferred'
    }
    Check 'launch plan fixes ports, uses npm.cmd, and passes env only to Uvicorn' {
        $fixture = New-Fixture
        $python = Find-LocalPython $repository
        function Find-LocalPython { return $python }
        $null = New-Item -ItemType Directory -Path (Join-Path $fixture.Root 'web')
        'BATATIS_TEST_ENV_FILE=not-exported' | Set-Content -LiteralPath (Join-Path $fixture.Root '.env')
        $plan = New-LocalLaunchPlan $fixture.Root
        Assert ($plan.Commands.Count -eq 3) 'npm ci missing for fresh checkout'
        $engine = $plan.Commands | Where-Object Name -eq 'engine'
        $web = $plan.Commands | Where-Object Name -eq 'web'
        Assert ($engine.Arguments -like '*"--env-file"*"spaced checkout*' -or
            $engine.Arguments.Contains((Join-Path $fixture.Root '.env'))) 'env path missing'
        Assert ($engine.Arguments -like '*"--port" "8000"*') 'engine port changed'
        Assert ($web.File -eq $env:ComSpec -and $web.Arguments -like '*npm.cmd" run dev*--port 3000 --strictPort*') 'npm launch is not strict'
        Assert (-not $env:BATATIS_TEST_ENV_FILE) 'env file was shell-sourced'
        $null = New-Item -ItemType Directory -Path (Join-Path $fixture.Root 'web/node_modules')
        Assert ((New-LocalLaunchPlan $fixture.Root).Commands.Count -eq 2) 'unnecessary npm ci'
    }
    Check 'native argument quoting preserves spaces, quotes, empty strings, and trailing backslashes' {
        $fixture = New-Fixture
        $python = Find-LocalPython $repository
        $output = Join-Path $fixture.Root 'quoted arguments.json'
        $wanted = @('path with spaces', 'embedded"quote', 'C:\trailing\', '', 'spaces and \\"quotes"')
        $code = 'import json,sys; open(sys.argv[1], "w").write(json.dumps(sys.argv[2:]))'
        $process = Start-Process -FilePath $python -ArgumentList (Join-ProcessArguments (@('-c', $code, $output) + $wanted)) `
            -WindowStyle Hidden -PassThru -Wait
        Assert ($process.ExitCode -eq 0) 'quoted process failed'
        $actual = Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
        Assert ($actual.Count -eq $wanted.Count) 'argument count changed'
        for ($i = 0; $i -lt $wanted.Count; $i++) { Assert ($actual[$i] -ceq $wanted[$i]) "argument $i changed" }
        $process.Dispose()
    }
    Check 'npm.cmd in a spaced path executes with the fixed web arguments and working directory' {
        $fixture = New-Fixture
        $python = Find-LocalPython $repository
        $npmDirectory = Join-Path $fixture.Root 'node tools'
        $webRoot = Join-Path $fixture.Root 'web'
        $null = New-Item -ItemType Directory -Path $npmDirectory, $webRoot
        $fakeNpm = Join-Path $npmDirectory 'npm.cmd'
        "@echo off`r`necho %*`r`necho %CD%`r`nexit /b 0`r`n" | Set-Content -LiteralPath $fakeNpm -Encoding ASCII
        function Find-LocalPython { return $python }
        function Get-Command { [pscustomobject]@{ Source = $fakeNpm } }
        $plan = New-LocalLaunchPlan $fixture.Root
        foreach ($name in @('npm-ci', 'web')) {
            $item = $plan.Commands | Where-Object Name -eq $name
            $output = Join-Path $fixture.Root ($name + ' args.log')
            $process = Start-Process -FilePath $item.File -ArgumentList $item.Arguments -WorkingDirectory $item.Directory `
                -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $output
            Assert ($process.ExitCode -eq 0) 'npm.cmd did not execute'
            $lines = @(Get-Content -LiteralPath $output)
            $expected = if ($name -eq 'web') { 'run dev -- --port 3000 --strictPort --host 127.0.0.1' } else { 'ci' }
            Assert ($lines[0] -eq $expected -and $lines[1] -eq $webRoot) 'npm arguments or cwd changed'
            $process.Dispose()
        }
    }
    Check 'ownership survives the starting launcher exiting and readiness rejects a foreign listener' {
        $fixture = New-Fixture
        $plan = New-DummyPlan $fixture
        Write-LocalJson (Join-Path $fixture.Root 'test-plan.json') $plan
        @'
. (Join-Path $PSScriptRoot 'local-app.ps1')
$fixtureRoot = Split-Path $PSScriptRoot -Parent
$plan = Get-Content -LiteralPath (Join-Path $fixtureRoot 'test-plan.json') -Raw | ConvertFrom-Json
function New-LocalLaunchPlan { return $plan }
function Get-LocalListeners {
    $identityPath = Join-Path $fixtureRoot 'child identity.json'
    if (Test-Path -LiteralPath $identityPath) {
        $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
        foreach ($port in @(3000, 8000)) {
            [pscustomobject]@{ LocalPort = $port; OwningProcess = $identity.ProcessId }
        }
    }
}
function Test-LocalHttp { return $true }
$script:HelperPath = Join-Path $PSScriptRoot 'worker.ps1'
exit (Start-LocalApp $fixtureRoot (Join-Path $fixtureRoot '.data/local-app') 15)
'@ | Set-Content -LiteralPath (Join-Path $fixture.Scripts 'start-fixture.ps1')
        $starter = $null
        try {
            $startArgs = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                '-File', (Join-Path $fixture.Scripts 'start-fixture.ps1'))
            $starter = Start-Process -FilePath $shellPath -ArgumentList $startArgs -WindowStyle Hidden -PassThru
            $null = $starter.Handle
            Assert ($starter.WaitForExit(20000)) 'starting launcher did not return'
            Assert ($starter.ExitCode -eq 0) 'owned ready process did not start'
            $identity = Child-Identity $fixture
            Assert (Is-Running $identity.ProcessId) 'child stopped when starting launcher exited'
            function Get-LocalListeners {
                foreach ($port in @(3000, 8000)) { [pscustomobject]@{ LocalPort = $port; OwningProcess = $PID } }
            }
            Assert (-not (Test-LocalReady $plan $fixture.Logs)) 'foreign listeners satisfied readiness'
        }
        finally {
            Cleanup-Dummy $starter
            $null = Stop-LocalApp $fixture.Root $fixture.Logs
            if (Test-Path -LiteralPath (Join-Path $fixture.Root 'child identity.json')) {
                $identity = Child-Identity $fixture
                Await { -not (Is-Running $identity.ProcessId) }
            }
        }
    }
    Check 'owned descendant survives its parent and is stopped from a fresh launcher; foreign process survives --force' {
        $fixture = New-Fixture
        $foreign = $null
        $worker = $null
        try {
            $foreign = Start-Process -FilePath $shellPath -ArgumentList '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 120"' -WindowStyle Hidden -PassThru
            $null = $foreign.Handle
            $plan = New-DummyPlan $fixture -ParentExits
            $worker = Start-Dummy $fixture $plan
            $identity = Child-Identity $fixture
            $parentId = [int](Get-Content -LiteralPath (Join-Path $fixture.Root 'parent.id') -Raw)
            Await { -not (Is-Running $parentId) }
            Assert (Is-Running $identity.ProcessId) 'descendant died with npm-like parent'
            $stopArgs = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                '-File', (Join-Path $fixture.Scripts 'local-app.ps1'), 'stop', '--force')
            $stopError = Join-Path $fixture.Root 'stop.err.log'
            $stop = Start-Process -FilePath $shellPath -ArgumentList $stopArgs -WindowStyle Hidden -PassThru -Wait -RedirectStandardError $stopError
            Assert ($stop.ExitCode -eq 0) ('fresh stop failed: ' + (Get-Content -LiteralPath $stopError -Raw))
            $stop.Dispose()
            Await { -not (Is-Running $identity.ProcessId) }
            Assert (-not $foreign.HasExited) 'foreign process was killed'
            Assert (-not (Test-Path -LiteralPath (Join-Path $fixture.Logs 'windows-owner.json'))) 'ownership state remained after stop'
        }
        finally { Cleanup-Dummy $worker; Cleanup-Dummy $foreign }
    }
    Check 'stale PID creation identity and a foreign PID preserve all processes and ownership records' {
        $fixture = New-Fixture
        $worker = $null
        try {
            $worker = Start-Dummy $fixture (New-DummyPlan $fixture)
            $owner = Read-LocalOwner $fixture.Root $fixture.Logs
            $path = Join-Path $fixture.Logs 'windows-owner.json'
            $originalTicks = $owner.CreationTicks
            $owner.CreationTicks = '1'
            Write-LocalJson $path $owner
            Assert ((Stop-LocalApp $fixture.Root $fixture.Logs) -eq 1) 'stale creation time was trusted'
            Assert (-not $worker.HasExited) 'live worker killed by stale identity'
            $self = [Diagnostics.Process]::GetCurrentProcess()
            $owner.ProcessId = $PID
            $owner.CreationTicks = $self.StartTime.ToUniversalTime().Ticks.ToString()
            Write-LocalJson $path $owner
            Assert ((Stop-LocalApp $fixture.Root $fixture.Logs) -eq 1) 'foreign PID was trusted'
            Assert (Test-Path -LiteralPath $path) 'unknown record was deleted'
            $owner.ProcessId = $worker.Id
            $owner.CreationTicks = $originalTicks
            Write-LocalJson $path $owner
            Assert ((Stop-LocalApp $fixture.Root $fixture.Logs) -eq 0) 'verified owner could not stop'
        }
        finally { Cleanup-Dummy $worker }
    }
    Check 'engine cases default and override survive with a spaced checkout path' {
        $original = $env:BATATIS_CASES
        try {
            foreach ($cases in @('', (Join-Path $testRoot 'custom cases.sqlite'))) {
                $env:BATATIS_CASES = $cases
                $fixture = New-Fixture
                $worker = $null
                try {
                    $worker = Start-Dummy $fixture (New-DummyPlan $fixture)
                    $identity = Child-Identity $fixture
                    $expected = if ($cases) { $cases } else { Join-Path $fixture.Root '.data/cases.sqlite' }
                    Assert ($identity.Cases -eq $expected) 'BATATIS_CASES changed'
                    Assert (-not $identity.EnvProbe) 'env file leaked to child'
                    Assert ((Stop-LocalApp $fixture.Root $fixture.Logs) -eq 0) 'dummy did not stop'
                }
                finally { Cleanup-Dummy $worker }
            }
        }
        finally { $env:BATATIS_CASES = $original }
    }
    Check 'partial spawn failure cleans up the attempt and preserves a foreign process' {
        $fixture = New-Fixture
        $foreign = $null
        try {
            $foreign = Start-Process -FilePath $shellPath -ArgumentList '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 120"' -WindowStyle Hidden -PassThru
            $null = $foreign.Handle
            $plan = New-DummyPlan $fixture
            $barrier = Join-Path $fixture.Scripts 'await-child.ps1'
            @'
param([string]$IdentityPath)
while (-not (Test-Path -LiteralPath $IdentityPath)) { Start-Sleep -Milliseconds 50 }
'@ | Set-Content -LiteralPath $barrier
            $plan.Commands += [pscustomobject]@{
                Name = 'barrier'; File = $shellPath; Directory = $fixture.Root; Wait = $true
                Arguments = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                    '-File', $barrier, (Join-Path $fixture.Root 'child identity.json'))
            }
            $plan.Commands += [pscustomobject]@{
                Name = 'web'; File = (Join-Path $fixture.Root 'missing.exe'); Arguments = ''; Directory = $fixture.Root; Wait = $false
            }
            function Get-LocalListeners { @() }
            function New-LocalLaunchPlan { return $plan }
            $script:HelperPath = Join-Path $fixture.Scripts 'worker.ps1'
            Assert ((Start-LocalApp $fixture.Root $fixture.Logs 15) -eq 1) 'partial failure reported success'
            $identity = Child-Identity $fixture
            Await { -not (Is-Running $identity.ProcessId) }
            Assert (-not $foreign.HasExited) 'partial failure killed a foreign process'
            Assert (-not (Test-Path -LiteralPath (Join-Path $fixture.Logs 'windows-owner.json'))) 'failed attempt state remained'
        }
        finally { Cleanup-Dummy $foreign }
    }
    Check 'readiness timeout cleans up live children, not only the supervisor' {
        $fixture = New-Fixture
        $plan = New-DummyPlan $fixture
        function Get-LocalListeners { @() }
        function New-LocalLaunchPlan { return $plan }
        function Test-LocalReady { return $false }
        $script:HelperPath = Join-Path $fixture.Scripts 'worker.ps1'
        Assert ((Start-LocalApp $fixture.Root $fixture.Logs 8) -eq 1) 'readiness timeout reported success'
        $identity = Child-Identity $fixture
        Await { -not (Is-Running $identity.ProcessId) }
        Assert (-not (Test-Path -LiteralPath (Join-Path $fixture.Logs 'windows-owner.json'))) 'timeout state remained'
    }
    Check 'dependency installation finishes before the server readiness timeout begins' {
        $fixture = New-Fixture
        $plan = New-DummyPlan $fixture
        $installScript = Join-Path $fixture.Scripts 'install.ps1'
        'Start-Sleep -Seconds 3' | Set-Content -LiteralPath $installScript
        $install = [pscustomobject]@{
            Name = 'npm-ci'; File = $shellPath; Directory = $fixture.Root; Wait = $true
            Arguments = Join-ProcessArguments @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $installScript)
        }
        $plan.Commands = @($install) + $plan.Commands
        function Get-LocalListeners { @() }
        function New-LocalLaunchPlan { return $plan }
        function Test-LocalReady { return (Test-Path -LiteralPath (Join-Path $fixture.Root 'child identity.json')) }
        $script:HelperPath = Join-Path $fixture.Scripts 'worker.ps1'
        try { Assert ((Start-LocalApp $fixture.Root $fixture.Logs 2) -eq 0) 'dependency installation consumed the readiness deadline' }
        finally { $null = Stop-LocalApp $fixture.Root $fixture.Logs }
    }
}
finally {
    $script:HelperPath = $sourceHelper
    # This directory was created above, under the OS temp directory, for this run only.
    $resolved = [IO.Path]::GetFullPath($testRoot)
    Assert ($resolved.StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) -and
        (Split-Path $resolved -Leaf) -like 'Batatis local app tests *') 'unsafe test cleanup path'
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Host "$checks checks; $failures failures"
if ($failures) { exit 1 }
