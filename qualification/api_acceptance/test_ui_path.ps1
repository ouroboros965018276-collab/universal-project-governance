param([string]$PowerShellPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($PowerShellPath)) { $PowerShellPath = (Get-Process -Id $PID).Path }
$launcher = Join-Path $PSScriptRoot 'launch_api_acceptance.ps1'
if (-not (Test-Path -LiteralPath $PowerShellPath -PathType Leaf)) { throw 'selftest-runtime-missing' }
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'selftest-launcher-missing' }
$tag = [guid]::NewGuid().ToString('N')
$resultPath = Join-Path ([IO.Path]::GetTempPath()) ('upg-api-ui-selftest-result-' + $tag + '.json')
$ledgerPath = $resultPath + '.ledger.json'
$process = $null
$summary = $null
$script:assertions = 0
function Assert-UiPath([bool]$Condition,[string]$Code) {
    $script:assertions++
    if (-not $Condition) { throw "UI_PATH_ASSERTION_FAILED:$Code" }
}
try {
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $PowerShellPath
    $psi.Arguments = '-NoLogo -NoProfile -STA -File "' + $launcher + '" -UiPathSelfTest -SelfTestResultPath "' + $resultPath + '"'
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $process = [Diagnostics.Process]::Start($psi)
    if (-not $process.WaitForExit(30000)) {
        try { if (-not $process.HasExited) { $process.Kill() } } catch [InvalidOperationException] { } catch [ComponentModel.Win32Exception] { }
        $null = $process.WaitForExit(5000)
        throw 'selftest-ui-path-timeout'
    }
    if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { throw 'selftest-ui-result-missing' }
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    Assert-UiPath ([string]$result.sanitized_ledger_path -ceq $ledgerPath) 'expected-ledger-path'
    if (-not (Test-Path -LiteralPath $ledgerPath -PathType Leaf)) { throw 'selftest-ledger-missing' }
    $ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
    Assert-UiPath ($process.ExitCode -eq 0) 'launcher-process-exit'
    Assert-UiPath ($result.test_mode -ceq 'ui-button-to-runspace-to-module-fake-transport') 'fake-transport-test-mode'
    Assert-UiPath ($result.form_shown_then_hidden -eq $true) 'hidden-form-shown'
    Assert-UiPath ($result.button_event_count -eq 1) 'real-button-click-handler-fired-once'
    Assert-UiPath ($result.worker_completed -eq $true -and $result.status -eq 'complete') 'runspace-returned-complete'
    Assert-UiPath ($result.test_transport_call_count -eq 2) 'fake-transport-called-once-per-provider'
    Assert-UiPath ($ledger.test_transport_call_count -eq 2) 'ledger-records-two-fake-calls'
    Assert-UiPath ($ledger.status -eq 'complete') 'ledger-finalized'
    Assert-UiPath ((@($ledger.providers.PSObject.Properties.Name | Sort-Object) -join ',') -ceq 'deepseek,mimo') 'exact-provider-set'
    foreach ($provider in @('deepseek','mimo')) {
        $row = $ledger.providers.$provider
        Assert-UiPath ($row.status -eq 'success' -and $row.request_count -eq 1) "$provider-successful-fake-path"
        Assert-UiPath ($row.controlled_tool_call -eq $true -and $row.authentication_and_response -eq $true) "$provider-fake-response-and-tool-validated"
        Assert-UiPath ($null -ne $row.estimated_cny -and [double]$row.estimated_cny -ge 0 -and [double]$row.estimated_cny -lt 2.50 -and $row.charge_unknown -eq $false) "$provider-fake-budget-bounded"
    }
    $summary = [pscustomobject]@{ Passed=$true; AssertionCount=$script:assertions; TestMode=$result.test_mode; ButtonEvents=$result.button_event_count; WorkerCompleted=$result.worker_completed; FakeTransportCalls=$result.test_transport_call_count; NoModelRequestMade=$true }
}
finally {
    if ($null -ne $process) {
        try { if (-not $process.HasExited) { $process.Kill(); $null=$process.WaitForExit(5000) } } finally { $process.Dispose() }
    }
    # Delete only the exact unique files allocated by this invocation.
    foreach ($file in @($resultPath,$ledgerPath,($ledgerPath + '.pending'))) {
        if (Test-Path -LiteralPath $file) {
            $item=Get-Item -LiteralPath $file -Force
            if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'selftest-cleanup-unexpected-file-type' }
            Remove-Item -LiteralPath $file -Force
        }
    }
}
$summary | ConvertTo-Json -Depth 5 -Compress
