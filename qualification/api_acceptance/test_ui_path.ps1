$ErrorActionPreference = 'Stop'
$pwshCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($null -eq $pwshCommand -or [string]::IsNullOrWhiteSpace($pwshCommand.Source)) { throw 'selftest-runtime-missing' }
$pwsh = $pwshCommand.Source
$launcher = Join-Path $PSScriptRoot 'launch_api_acceptance.ps1'
if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { throw 'selftest-runtime-missing' }
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'selftest-launcher-missing' }
$tag = [guid]::NewGuid().ToString('N')
$resultPath = Join-Path ([IO.Path]::GetTempPath()) ('upg-api-ui-selftest-result-' + $tag + '.json')
$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $pwsh
$psi.Arguments = '-NoLogo -NoProfile -STA -File "' + $launcher + '" -UiPathSelfTest -SelfTestResultPath "' + $resultPath + '"'
$psi.UseShellExecute = $false
$process = [Diagnostics.Process]::Start($psi)
if (-not $process.WaitForExit(30000)) {
    $process.Kill()
    throw 'selftest-ui-path-timeout'
}
if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { throw 'selftest-ui-result-missing' }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
$ledgerPath = [string]$result.sanitized_ledger_path
if ([string]::IsNullOrWhiteSpace($ledgerPath) -or -not (Test-Path -LiteralPath $ledgerPath -PathType Leaf)) { throw 'selftest-ledger-missing' }
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$assertions = 0
function Assert-UiPath([bool]$Condition,[string]$Code) {
    $script:assertions++
    if (-not $Condition) { throw "UI_PATH_ASSERTION_FAILED:$Code" }
}
Assert-UiPath ($process.ExitCode -eq 0) 'launcher-process-exit'
Assert-UiPath ($result.form_shown_then_hidden -eq $true) 'hidden-form-shown'
Assert-UiPath ($result.button_event_count -eq 1) 'real-button-click-handler-fired-once'
Assert-UiPath ($result.worker_completed -eq $true -and $result.status -eq 'complete') 'runspace-returned-complete'
Assert-UiPath ($result.test_transport_call_count -eq 2) 'fake-transport-called-once-per-provider'
Assert-UiPath ($ledger.test_transport_call_count -eq 2) 'ledger-records-two-fake-calls'
Assert-UiPath ($ledger.status -eq 'complete') 'ledger-finalized'
foreach ($provider in @('deepseek','mimo')) {
    $row = $ledger.providers.$provider
    Assert-UiPath ($row.status -eq 'success' -and $row.request_count -eq 1) "$provider-successful-fake-path"
    Assert-UiPath ($row.controlled_tool_call -eq $true -and $row.authentication_and_response -eq $true) "$provider-fake-response-and-tool-validated"
    Assert-UiPath ($row.estimated_cny -lt 2.50 -and $row.charge_unknown -eq $false) "$provider-fake-budget-bounded"
}
$summary = [pscustomobject]@{
    Passed = $true
    AssertionCount = $assertions
    TestMode = $result.test_mode
    ButtonEvents = $result.button_event_count
    WorkerCompleted = $result.worker_completed
    FakeTransportCalls = $result.test_transport_call_count
    Providers = @($ledger.providers.PSObject.Properties | ForEach-Object { [pscustomobject]@{ Provider=$_.Name; Status=$_.Value.status; RequestCount=$_.Value.request_count; InputTokens=$_.Value.input_tokens; OutputTokens=$_.Value.output_tokens; EstimatedCny=$_.Value.estimated_cny; ControlledToolCall=$_.Value.controlled_tool_call } })
    NoModelRequestMade = $true
}
$summary | ConvertTo-Json -Depth 5 -Compress
foreach ($file in @($resultPath,$ledgerPath)) {
    $resolved = (Resolve-Path -LiteralPath $file).Path
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'selftest-cleanup-path-outside-temp' }
    Remove-Item -LiteralPath $resolved -Force
}
