param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [Parameter(Mandatory=$true)][string]$ResourcesDir,
  [Parameter(Mandatory=$true)][string]$EvidenceDir
)

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
  throw 'Run only on the parent disposable Windows GitHub Actions runner.'
}
$repoPath = (Resolve-Path -LiteralPath $Repo).Path
$resources = (Resolve-Path -LiteralPath $ResourcesDir).Path
$exe = (Resolve-Path -LiteralPath (Join-Path $repoPath 'desktop/codex/runtime/win32-x64/codex.exe')).Path
$node = (Get-Command node -CommandType Application | Select-Object -First 1).Source
if ((Get-Service MpsSvc).Status -ne 'Running') { throw 'Windows Firewall service must already be running.' }
$profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
if ($profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne $true }).Count) {
  throw 'All Windows Firewall profiles must already be enabled. This helper never changes profile policy.'
}
$rule = 'BatatisNativeCodex-' + [Guid]::NewGuid().ToString('N')
$exitCode = 1
$cleanup = @{ rule = $rule; executable = $exe; ruleRemoved = $false; nativeWindowsExecuted = $false }
try {
  New-NetFirewallRule -Name $rule -DisplayName $rule -Direction Outbound -Action Block `
    -Program $exe -Enabled True -Profile Any -Protocol Any -LocalAddress Any -RemoteAddress Any `
    -LocalPort Any -RemotePort Any -InterfaceType Any -PolicyStore PersistentStore | Out-Null
  & python -B (Join-Path $repoPath 'desktop/codex/native-check.py') `
    --resources-dir $resources --executable $exe --output $EvidenceDir --node $node `
    --windows-firewall-rule $rule --deadline-seconds 150
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) { throw "Native Windows acceptance failed with exit $exitCode." }
  $cleanup.nativeWindowsExecuted = $true
  & python -B (Join-Path $repoPath 'desktop/codex/native-check.py') --replay $EvidenceDir
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) { throw "Saved native Windows byte replay failed with exit $exitCode." }
}
catch {
  [Console]::Error.WriteLine($_.ToString())
  $exitCode = 1
}
finally {
  try {
    $owned = @(Get-NetFirewallRule -PolicyStore PersistentStore -Name $rule -ErrorAction SilentlyContinue)
    if ($owned.Count) { $owned | Remove-NetFirewallRule -ErrorAction Stop }
    if (@(Get-NetFirewallRule -PolicyStore PersistentStore -Name $rule -ErrorAction SilentlyContinue).Count) {
      throw 'Owned firewall rule remains.'
    }
    if (@(Get-NetFirewallRule -PolicyStore ActiveStore -Name $rule -ErrorAction SilentlyContinue).Count) {
      throw 'Owned firewall rule remains in the effective store.'
    }
    $cleanup.ruleRemoved = $true
  }
  catch {
    [Console]::Error.WriteLine($_.ToString())
    $exitCode = 1
  }
  $cleanup.exitCode = $exitCode
  $cleanup | ConvertTo-Json | Set-Content -LiteralPath "$EvidenceDir.firewall-cleanup.json" -Encoding utf8
}
exit $exitCode
