param(
    [switch]$EnableKeyEntry,
    [switch]$UiPathSelfTest,
    [string]$SelfTestResultPath
)

$ErrorActionPreference = 'Stop'
if ($UiPathSelfTest -and $EnableKeyEntry) { throw 'selftest-and-live-entry-are-mutually-exclusive' }
if ($UiPathSelfTest -and [string]::IsNullOrWhiteSpace($SelfTestResultPath)) { throw 'selftest-result-path-required' }
$keyEntryEnabled = [bool]($EnableKeyEntry -or $UiPathSelfTest)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module (Join-Path $PSScriptRoot 'api_acceptance.psm1') -Force

$modulePath = Join-Path $PSScriptRoot 'api_acceptance.psm1'
$deepBudget = Get-ApiAcceptanceBudget deepseek -DeepSeekRate peak
$mimoBudget = Get-ApiAcceptanceBudget mimo
$deepProvider = Get-ApiAcceptanceProvider deepseek
$mimoProvider = Get-ApiAcceptanceProvider mimo

$script:worker = $null
$script:runspace = $null
$script:async = $null
$script:cancelSource = $null
$script:workerRunning = $false
$script:closeRequested = $false
$script:ledgerPath = $null
$script:buttonEventCount = 0
$script:activeUiPhase = 'form-initialization'
$script:workerError = $null
$script:selfTestShown = $false

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'UPG API Key Entry — DeepSeek + MiMo'
$form.StartPosition = 'CenterScreen'
$form.Size = [System.Drawing.Size]::new(780, 625)
$form.MinimumSize = [System.Drawing.Size]::new(780, 625)
$form.MaximizeBox = $false
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
if ($UiPathSelfTest) { $form.ShowInTaskbar = $false; $form.Opacity = 0 }

$font = [System.Drawing.Font]::new('Segoe UI', 10)
$title = [System.Windows.Forms.Label]::new()
$title.Text = '一次性官方 API 接入验收'
$title.Font = [System.Drawing.Font]::new('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$title.Location = [System.Drawing.Point]::new(24, 20)
$title.Size = [System.Drawing.Size]::new(700, 34)
$form.Controls.Add($title)

$intro = [System.Windows.Forms.Label]::new()
$intro.Text = "仅此次验收；不自动充值。每家预算上限 ¥2.50。每家最多 1 个请求，输出上限 256 tokens，思考关闭，只允许单个本地无副作用 function 工具。关闭且尚未提交即取消。"
$intro.Font = $font
$intro.Location = [System.Drawing.Point]::new(26, 62)
$intro.Size = [System.Drawing.Size]::new(715, 52)
$form.Controls.Add($intro)

$budgetText = [System.Windows.Forms.Label]::new()
$budgetText.Text = ("最坏预留按完整 1M context（缓存未命中输入）及最多 256 输出 tokens：`nDeepSeek 峰时 ¥2/M 输入、¥8/M 输出：¥{0:N6}；MiMo ¥1/M 输入、¥2/M 输出：¥{1:N6}；各家上限 ¥2.50。" -f $deepBudget.WorstCaseCny,$mimoBudget.WorstCaseCny)
$budgetText.Font = $font
$budgetText.Location = [System.Drawing.Point]::new(26, 118)
$budgetText.Size = [System.Drawing.Size]::new(715, 62)
$form.Controls.Add($budgetText)

$deepLabel = [System.Windows.Forms.Label]::new()
$deepLabel.Text = "DeepSeek 官方 API — $($deepProvider.Model) — $($deepProvider.Endpoint)"
$deepLabel.Font = [System.Drawing.Font]::new('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$deepLabel.Location = [System.Drawing.Point]::new(28, 198)
$deepLabel.Size = [System.Drawing.Size]::new(705, 24)
$form.Controls.Add($deepLabel)

$deepBox = [System.Windows.Forms.TextBox]::new()
$deepBox.Location = [System.Drawing.Point]::new(30, 226)
$deepBox.Size = [System.Drawing.Size]::new(700, 30)
$deepBox.Font = $font
$deepBox.UseSystemPasswordChar = $true
$deepBox.MaxLength = 512
$deepBox.Enabled = $keyEntryEnabled
$form.Controls.Add($deepBox)

$mimoLabel = [System.Windows.Forms.Label]::new()
$mimoLabel.Text = "Xiaomi MiMo 官方 Pay-As-You-Go API — $($mimoProvider.Model) — $($mimoProvider.Endpoint)"
$mimoLabel.Font = [System.Drawing.Font]::new('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$mimoLabel.Location = [System.Drawing.Point]::new(28, 274)
$mimoLabel.Size = [System.Drawing.Size]::new(705, 24)
$form.Controls.Add($mimoLabel)

$mimoBox = [System.Windows.Forms.TextBox]::new()
$mimoBox.Location = [System.Drawing.Point]::new(30, 302)
$mimoBox.Size = [System.Drawing.Size]::new(700, 30)
$mimoBox.Font = $font
$mimoBox.UseSystemPasswordChar = $true
$mimoBox.MaxLength = 512
$mimoBox.Enabled = $keyEntryEnabled
$form.Controls.Add($mimoBox)

$keyNote = [System.Windows.Forms.Label]::new()
$keyNote.Text = '密钥仅在此进程内存中用于官方 HTTPS 请求，不写文件/环境变量/命令行/控制台/日志；API key 不会传给子进程。MiMo Token Plan tp- 密钥不适用于此 PAYG 测试。'
$keyNote.Font = $font
$keyNote.Location = [System.Drawing.Point]::new(30, 344)
$keyNote.Size = [System.Drawing.Size]::new(700, 48)
$form.Controls.Add($keyNote)

$status = [System.Windows.Forms.Label]::new()
$status.Font = [System.Drawing.Font]::new('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$status.Location = [System.Drawing.Point]::new(30, 405)
$status.Size = [System.Drawing.Size]::new(700, 56)
if ($keyEntryEnabled) {
    $status.Text = '准备就绪。填写两家专用 API Key；点击“确认并启动”即授权开始本次限额请求。'
    $status.ForeColor = [System.Drawing.Color]::DarkGreen
}
else {
    $status.Text = '只读安全审查待完成：输入框已锁定。审查通过后才会启用输入与启动按钮。'
    $status.ForeColor = [System.Drawing.Color]::DarkOrange
}
$form.Controls.Add($status)

$cancelButton = [System.Windows.Forms.Button]::new()
$cancelButton.Text = '关闭并取消'
$cancelButton.Font = $font
$cancelButton.Location = [System.Drawing.Point]::new(474, 500)
$cancelButton.Size = [System.Drawing.Size]::new(125, 38)
$form.Controls.Add($cancelButton)

$runButton = [System.Windows.Forms.Button]::new()
$runButton.Text = '确认并启动'
$runButton.Font = $font
$runButton.Location = [System.Drawing.Point]::new(610, 500)
$runButton.Size = [System.Drawing.Size]::new(120, 38)
$runButton.Enabled = $keyEntryEnabled
$form.Controls.Add($runButton)
$form.AcceptButton = $runButton
$form.CancelButton = $cancelButton

$script:timer = [System.Windows.Forms.Timer]::new()
$script:timer.Interval = 200

function Get-SafeFailureDetails($ErrorRecord, [string]$Stage) {
    $exceptionType = if ($ErrorRecord.Exception) { $ErrorRecord.Exception.GetType().FullName } else { 'System.Management.Automation.ErrorRecord' }
    $errorId = [string]$ErrorRecord.FullyQualifiedErrorId
    $errorId = $errorId -replace '[^A-Za-z0-9_.:-]', '_'
    if ($errorId.Length -gt 120) { $errorId = $errorId.Substring(0,120) }
    return [ordered]@{ stage=$Stage; exception_type=$exceptionType; error_id=$errorId }
}

function Save-SelfTestSummary([object]$Results, [object]$Failure) {
    if (-not $UiPathSelfTest) { return }
    $providerRows = @()
    if ($null -ne $Results -and $Results.providers) {
        foreach ($id in @('deepseek','mimo')) {
            $row = $Results.providers.$id
            if ($null -ne $row) {
                $providerRows += [ordered]@{ provider=$id; status=$row.status; request_count=$row.request_count; charge_unknown=$row.charge_unknown; reserved_cny=$row.worst_case_reserved_cny; input_tokens=$row.input_tokens; output_tokens=$row.output_tokens; estimated_cny=$row.estimated_cny; error_code=$row.error_code }
            }
        }
    }
    $summary = [ordered]@{
        schema_version = 1
        test_mode = 'ui-button-to-runspace-to-module-fake-transport'
        form_shown_then_hidden = $script:selfTestShown
        button_event_count = $script:buttonEventCount
        worker_completed = ($null -ne $Results)
        status = if ($null -ne $Results) { $Results.status } else { 'local-failed' }
        local_failure = if ($null -ne $Results -and $Results.local_failure) { $Results.local_failure } else { $Failure }
        test_transport_call_count = if ($null -ne $Results) { $Results.test_transport_call_count } else { $null }
        providers = $providerRows
        sanitized_ledger_path = $script:ledgerPath
    }
    $json = $summary | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($SelfTestResultPath,$json,(New-Object System.Text.UTF8Encoding($false)))
}

$cancelButton.Add_Click({
    if ($script:workerRunning) {
        $script:closeRequested = $true
        $status.Text = '正在取消当前请求；已发送请求的费用状态未知，将按完整上界保留；不会重试。'
        $cancelButton.Enabled = $false
        if ($script:cancelSource) { $script:cancelSource.Cancel() }
        return
    }
    $deepBox.Clear(); $mimoBox.Clear()
    $form.Close()
})

$form.Add_FormClosing({
    param($sender,$eventArgs)
    if ($script:workerRunning) {
        $eventArgs.Cancel = $true
        $script:closeRequested = $true
        $status.Text = '正在取消当前请求；已发送请求的费用状态未知，将按完整上界保留；不会重试。'
        $cancelButton.Enabled = $false
        if ($script:cancelSource) { $script:cancelSource.Cancel() }
    }
    else {
        $deepBox.Clear(); $mimoBox.Clear()
    }
})

$script:timer.Add_Tick({
    if (-not $script:workerRunning -or -not $script:async.IsCompleted) { return }
    $script:timer.Stop()
    $outputText = $null
    try {
        $output = $script:worker.EndInvoke($script:async)
        if ($output.Count -gt 0) { $outputText = [string]$output[$output.Count - 1] }
    }
    catch { $script:workerError = Get-SafeFailureDetails $_ 'worker-endinvoke'; $outputText = $null }
    finally {
        $script:workerRunning = $false
        if ($script:worker) { $script:worker.Dispose(); $script:worker = $null }
        if ($script:runspace) { $script:runspace.Close(); $script:runspace.Dispose(); $script:runspace = $null }
        if ($script:cancelSource) { $script:cancelSource.Dispose(); $script:cancelSource = $null }
        $script:async = $null
        $deepKey = $null; $mimoKey = $null
        [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    }

    $results = $null
    if ($outputText) {
        try { $results = ConvertFrom-Json -InputObject $outputText -ErrorAction Stop }
        catch { $script:workerError = Get-SafeFailureDetails $_ 'worker-result-parse'; $results = $null }
    }
    if ($null -ne $results) {
        $lines = @('验收执行结束（不显示模型回复或密钥）：')
        foreach ($id in @('deepseek','mimo')) {
            $row = $results.providers.$id
            if ($null -eq $row) { continue }
            if ($null -ne $row.estimated_cny) {
                $lines += ("{0}: {1}; input={2}, output={3}, 费用上界估算 ¥{4:N8}" -f $row.provider_name,$row.status,$row.input_tokens,$row.output_tokens,[double]$row.estimated_cny)
            }
            elseif ($row.charge_unknown) {
                $lines += ("{0}: {1}; 费用未知，保留完整上界 ¥{2:N6}; 不重试" -f $row.provider_name,$row.status,[double]$row.worst_case_reserved_cny)
            }
            else { $lines += ("{0}: {1}; 请求未发送或未达到工具验收" -f $row.provider_name,$row.status) }
        }
        $lines += "Usage ledger（不含密钥/原始响应）：$script:ledgerPath"
        $status.Text = $lines -join [Environment]::NewLine
        $status.ForeColor = if ($script:closeRequested) { [System.Drawing.Color]::DarkOrange } else { [System.Drawing.Color]::DarkGreen }
    }
    else {
        $status.Text = "结果未能确认；账本保留已知状态或完整费用上界。不会自动重试。账本：$script:ledgerPath"
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
    }
    $cancelButton.Text = '关闭'
    $cancelButton.Enabled = $true
    $runButton.Enabled = $false
    $deepBox.Clear(); $mimoBox.Clear()
    if ($null -ne $results -and $results.local_failure) {
        $failure = $results.local_failure
        $status.Text += ([Environment]::NewLine + "Local failure stage=$($failure.stage); type=$($failure.exception_type); error_id=$($failure.error_id). No automatic retry.")
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
    }
    elseif ($null -eq $results -and $script:workerError) {
        $failure = $script:workerError
        $status.Text = "Local result failed at $($failure.stage); type=$($failure.exception_type); error_id=$($failure.error_id). No automatic retry. Ledger: $script:ledgerPath"
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
    }
    Save-SelfTestSummary $results $script:workerError
    if ($script:closeRequested) { $form.Close() }
    if ($UiPathSelfTest) { $form.Close() }
})

$runButton.Add_Click({
    if (-not $keyEntryEnabled) { return }
    $script:buttonEventCount++
    $script:activeUiPhase = 'button-validation'
    $deepKey = [string]$deepBox.Text
    $mimoKey = [string]$mimoBox.Text
    if ([string]::IsNullOrWhiteSpace($deepKey) -or [string]::IsNullOrWhiteSpace($mimoKey)) {
        $status.Text = '请同时填写两家专用 key。字段内容不会显示在状态区。'
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
        return
    }
    if ($mimoKey.StartsWith('tp-', [StringComparison]::OrdinalIgnoreCase)) {
        $deepKey = $null; $mimoKey = $null
        $deepBox.Clear(); $mimoBox.Clear()
        $status.Text = 'MiMo Token Plan key 不适用于本次 PAYG API 验收；未发送请求。'
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
        return
    }
    if ($deepBudget.WorstCaseCny -ge $deepBudget.LimitCny -or $mimoBudget.WorstCaseCny -ge $mimoBudget.LimitCny) {
        $deepKey = $null; $mimoKey = $null
        $deepBox.Clear(); $mimoBox.Clear()
        $status.Text = '当前价格/汇率上界超过预算；未发送请求。'
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
        return
    }

    # Clear masked controls immediately; the key strings stay only in this process/runspace memory.
    $deepBox.Clear(); $mimoBox.Clear()
    $runButton.Enabled = $false
    $cancelButton.Text = '取消请求并关闭'
    $status.Text = '本次请求已由你的点击确认。按固定官方 endpoint 串行发送；无重试/回退。可关闭或取消。'
    $status.ForeColor = [System.Drawing.Color]::DarkBlue
    $script:cancelSource = [System.Threading.CancellationTokenSource]::new()
    if ($UiPathSelfTest) { $script:ledgerPath = Join-Path ([System.IO.Path]::GetTempPath()) ('upg-api-ui-selftest-' + [guid]::NewGuid().ToString('N') + '.json') }
    else { $script:ledgerPath = Join-Path ([System.IO.Path]::GetTempPath()) ('upg-api-acceptance-usage-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.json') }
    $script:workerScript = @'
param($ModulePath,$DeepKey,$MiMoKey,$LedgerPath,$CancellationToken,$UseMockTransport)
$ErrorActionPreference = 'Stop'
$phase = 'module-import'
$ledger = $null
$keys = $null
$transportState = @{ call_count = 0 }
$mockTransport = $null
try {
Import-Module $ModulePath -Force
$phase = 'budget-initialization'
$deepBudget = Get-ApiAcceptanceBudget deepseek -DeepSeekRate peak
$mimoBudget = Get-ApiAcceptanceBudget mimo
$ledger = [ordered]@{
  schema_version = 1
  started_utc = [DateTime]::UtcNow.ToString('o')
  status = 'running'
  request_policy = 'one request per provider; no retry/fallback; full-context reserve'
  providers = [ordered]@{
    deepseek = [ordered]@{ provider='deepseek'; provider_name='DeepSeek 官方 API'; model='deepseek-flash'; status='not-started'; request_count=0; maximum_request_count=1; context_tokens_reserved=1000000; output_tokens_reserved=256; worst_case_reserved_cny=$deepBudget.WorstCaseCny; pricing_currency='CNY'; pricing_period='peak'; input_cny_per_million=$deepBudget.InputCnyPerMillion; output_cny_per_million=$deepBudget.OutputCnyPerMillion; input_tokens=$null; output_tokens=$null; estimated_cny=$null; charge_unknown=$false; authentication_and_response=$false; controlled_tool_call=$false; error_code=$null }
    mimo = [ordered]@{ provider='mimo'; provider_name='Xiaomi MiMo 官方 API'; model='mimo-v2.6-flash'; status='not-started'; request_count=0; maximum_request_count=1; context_tokens_reserved=1000000; output_tokens_reserved=256; worst_case_reserved_cny=$mimoBudget.WorstCaseCny; pricing_currency='CNY'; pricing_period='published-rate'; input_cny_per_million=$mimoBudget.InputCnyPerMillion; output_cny_per_million=$mimoBudget.OutputCnyPerMillion; input_tokens=$null; output_tokens=$null; estimated_cny=$null; charge_unknown=$false; authentication_and_response=$false; controlled_tool_call=$false; error_code=$null }
  }
}
function Save-UsageLedger([object]$Data,[string]$Path) {
  $temp = $Path + '.pending'
  $json = $Data | ConvertTo-Json -Depth 12
  [System.IO.File]::WriteAllText($temp,$json,(New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::Move($temp,$Path,[System.IO.File]::Exists($Path))
}
$phase = 'initial-ledger-write'
Save-UsageLedger $ledger $LedgerPath
$phase = 'request-loop-initialization'
$keys = @{ deepseek=$DeepKey; mimo=$MiMoKey }
if ($UseMockTransport) {
  $phase = 'selftest-mock-setup'
  $mockBody = '{"choices":[{"message":{"tool_calls":[{"type":"function","function":{"name":"upg_record_probe","arguments":"{\"marker\":\"UPG_API_PROBE_OK\"}"}}]}}],"usage":{"prompt_tokens":42,"completion_tokens":9}}'
  $mockTransport = {
    param($endpoint,$header,$auth,$body)
    if ($endpoint.AbsoluteUri -notin @('https://api.deepseek.com/chat/completions','https://api.xiaomimimo.com/v1/chat/completions')) { throw 'selftest-endpoint-rejected' }
    $transportState.call_count++
    [pscustomobject]@{ StatusCode=200; Body=$mockBody }
  }.GetNewClosure()
  if ($null -eq $mockTransport) { throw 'selftest-mock-unavailable' }
}
foreach ($id in @('deepseek','mimo')) {
  if ($CancellationToken.IsCancellationRequested) { break }
  $phase = "$id-ledger-inflight"
  $row = $ledger.providers[$id]
  $row.status = 'request-in-flight'
  $row.request_count = 1
  $row.charge_unknown = $true
  Save-UsageLedger $ledger $LedgerPath
  $checkpoint = {
    param($next)
    $ledger.providers[$next.provider] = $next
    Save-UsageLedger $ledger $LedgerPath
  }.GetNewClosure()
  $phase = "$id-provider-call"
  if ($UseMockTransport) {
    $result = Invoke-ApiAcceptanceProvider -ProviderId $id -ApiKey ([string]$keys[$id]) -CancellationToken $CancellationToken -Checkpoint $checkpoint -MockTransport $mockTransport
  }
  else {
    $result = Invoke-ApiAcceptanceProvider -ProviderId $id -ApiKey ([string]$keys[$id]) -CancellationToken $CancellationToken -Checkpoint $checkpoint
  }
  $ledger.providers[$id] = $result
  $phase = "$id-result-ledger-write"
  Save-UsageLedger $ledger $LedgerPath
  $keys[$id] = $null
  if ($CancellationToken.IsCancellationRequested) { break }
}
$ledger.test_transport_call_count = if ($UseMockTransport) { $transportState.call_count } else { $null }
$phase = 'final-ledger-write'
if ($CancellationToken.IsCancellationRequested) { $ledger.status = 'cancelled-or-partial' }
else { $ledger.status = 'complete' }
Save-UsageLedger $ledger $LedgerPath
$ledger | ConvertTo-Json -Depth 12 -Compress
}
catch {
  $record = $_
  $exceptionType = if ($record.Exception) { $record.Exception.GetType().FullName } else { 'System.Management.Automation.ErrorRecord' }
  $errorId = ([string]$record.FullyQualifiedErrorId) -replace '[^A-Za-z0-9_.:-]', '_'
  if ($errorId.Length -gt 120) { $errorId = $errorId.Substring(0,120) }
  $failure = [ordered]@{ stage=$phase; exception_type=$exceptionType; error_id=$errorId }
  if ($null -ne $ledger) {
    $ledger.status = 'local-failed'
    $ledger.local_failure = $failure
    if ($UseMockTransport) { $ledger.test_transport_call_count = $transportState.call_count }
    try { Save-UsageLedger $ledger $LedgerPath } catch { }
    $ledger | ConvertTo-Json -Depth 12 -Compress
  }
  else {
    [ordered]@{ schema_version=1; status='local-failed'; local_failure=$failure; providers=[ordered]@{} } | ConvertTo-Json -Depth 8 -Compress
  }
}
finally { $DeepKey=$null; $MiMoKey=$null; $keys=$null; $mockBody=$null; $mockTransport=$null }
'@
    $script:workerRunning = $true
    $script:closeRequested = $false
    try {
        $script:activeUiPhase = 'runspace-create'
        $script:runspace = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
        $script:runspace.Open()
        $script:worker = [System.Management.Automation.PowerShell]::Create()
        $script:worker.Runspace = $script:runspace
        $null = $script:worker.AddScript($script:workerScript.ToString())
        $null = $script:worker.AddArgument($modulePath)
        $null = $script:worker.AddArgument($deepKey)
        $null = $script:worker.AddArgument($mimoKey)
        $null = $script:worker.AddArgument($script:ledgerPath)
        $null = $script:worker.AddArgument($script:cancelSource.Token)
        $null = $script:worker.AddArgument([bool]$UiPathSelfTest)
        $script:activeUiPhase = 'runspace-begininvoke'
        $script:async = $script:worker.BeginInvoke()
        $deepKey = $null; $mimoKey = $null
        $script:workerRunning = $true
        $script:timer.Start()
    }
    catch {
        $script:workerRunning = $false
        $script:workerError = Get-SafeFailureDetails $_ $script:activeUiPhase
        $deepKey = $null; $mimoKey = $null
        $status.Text = "Local submission failed at $($script:workerError.stage); type=$($script:workerError.exception_type); error_id=$($script:workerError.error_id). No request was automatically retried."
        $status.ForeColor = [System.Drawing.Color]::DarkOrange
        $runButton.Enabled = $false
        $deepBox.Clear(); $mimoBox.Clear()
        Save-SelfTestSummary $null $script:workerError
        if ($UiPathSelfTest) { $form.Close() }
    }
})

if ($UiPathSelfTest) {
    $form.Add_Shown({
        $script:selfTestShown = $true
        $deepBox.Text = 'TEST_ONLY_DEEPSEEK_KEY'
        $mimoBox.Text = 'TEST_ONLY_MIMO_KEY'
        $runButton.PerformClick()
        $form.Hide()
        if ($script:buttonEventCount -ne 1) {
            $script:workerError = [ordered]@{ stage='ui-selftest-button-event'; exception_type='System.InvalidOperationException'; error_id='button-event-not-fired' }
            Save-SelfTestSummary $null $script:workerError
            $form.Close()
        }
    })
}

[System.Windows.Forms.Application]::Run($form)
