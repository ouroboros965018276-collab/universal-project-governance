Set-StrictMode -Version Latest

$script:Providers = @{
    deepseek = [pscustomobject]@{
        Id = 'deepseek'; Name = 'DeepSeek 官方 API'; Model = 'deepseek-flash'
        Endpoint = 'https://api.deepseek.com/chat/completions'
        Header = 'Authorization'; Prefix = 'Bearer '
        ContextTokens = 1000000; OutputCap = 256
        PeakInputCnyPerMillion = 2.0; PeakOutputCnyPerMillion = 8.0
        OffPeakInputCnyPerMillion = 1.0; OffPeakOutputCnyPerMillion = 4.0
        InputCnyPerMillion = 0.0; OutputCnyPerMillion = 0.0
        ThinkingField = 'thinking'; ThinkingValue = @{ type = 'disabled' }
        ToolChoice = 'required'; MaxField = 'max_tokens'
    }
    mimo = [pscustomobject]@{
        Id = 'mimo'; Name = 'Xiaomi MiMo 官方 API'; Model = 'mimo-v2.6-flash'
        Endpoint = 'https://api.xiaomimimo.com/v1/chat/completions'
        Header = 'api-key'; Prefix = ''
        ContextTokens = 1000000; OutputCap = 256
        PeakInputCnyPerMillion = 0.0; PeakOutputCnyPerMillion = 0.0
        OffPeakInputCnyPerMillion = 0.0; OffPeakOutputCnyPerMillion = 0.0
        InputCnyPerMillion = 1.0; OutputCnyPerMillion = 2.0
        ThinkingField = 'thinking'; ThinkingValue = @{ type = 'disabled' }
        ToolChoice = 'auto'; MaxField = 'max_completion_tokens'
    }
}

$script:MaxRequestsPerProvider = 1
$script:RequestTimeoutMilliseconds = 20000
$script:MaxRequestBodyBytes = 3072
$script:MaxResponseBytes = 65536
$script:HttpMessageHandlerForTests = $null
$script:ToolName = 'upg_record_probe'
$script:ToolMarker = 'UPG_API_PROBE_OK'
function Get-ApiAcceptanceProvider {
    [CmdletBinding()]
    param([Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$Id)
    return $script:Providers[$Id]
}

function Get-ApiAcceptanceBudget {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$Id,
        [ValidateSet('peak','off-peak')][string]$DeepSeekRate = 'peak'
    )
    $p = Get-ApiAcceptanceProvider -Id $Id
    if ($Id -eq 'deepseek') {
        if ($DeepSeekRate -eq 'off-peak') {
            $inputCny = $p.OffPeakInputCnyPerMillion
            $outputCny = $p.OffPeakOutputCnyPerMillion
        }
        else {
            $inputCny = $p.PeakInputCnyPerMillion
            $outputCny = $p.PeakOutputCnyPerMillion
        }
    }
    else {
        $inputCny = $p.InputCnyPerMillion
        $outputCny = $p.OutputCnyPerMillion
    }
    # Reserve the model's entire documented context as input, not a character/token estimate.
    $worst = (($p.ContextTokens * $inputCny) + ($p.OutputCap * $outputCny)) / 1000000.0
    return [pscustomobject]@{
        Provider = $Id
        Currency = 'CNY'
        LimitCny = 2.50
        ContextTokensReserved = $p.ContextTokens
        OutputTokensReserved = $p.OutputCap
        WorstCaseCny = [math]::Round($worst, 8, [MidpointRounding]::AwayFromZero)
        DeepSeekRate = if ($Id -eq 'deepseek') { $DeepSeekRate } else { $null }
        InputCnyPerMillion = $inputCny
        OutputCnyPerMillion = $outputCny
        RequestCount = $script:MaxRequestsPerProvider
    }
}

function Assert-ApiAcceptanceEndpoint {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$ProviderId,
        [Parameter(Mandatory)][string]$Uri
    )
    $expected = [uri](Get-ApiAcceptanceProvider -Id $ProviderId).Endpoint
    $actual = $null
    if (-not [uri]::TryCreate($Uri, [UriKind]::Absolute, [ref]$actual)) { throw 'endpoint-not-allowed' }
    if ($actual.Scheme -cne 'https' -or $actual.UserInfo -or $actual.Query -or $actual.Fragment -or
        $actual.AbsoluteUri -cne $expected.AbsoluteUri -or $actual.Port -ne 443) { throw 'endpoint-not-allowed' }
    return $actual
}

function New-ApiAcceptanceHttpClient {
    [CmdletBinding()]
    param()
    $messageHandler = $script:HttpMessageHandlerForTests
    if ($null -eq $messageHandler) {
        $messageHandler = [System.Net.Http.HttpClientHandler]::new()
        $messageHandler.AllowAutoRedirect = $false
        $messageHandler.UseDefaultCredentials = $false
        $messageHandler.Credentials = $null
        $messageHandler.UseCookies = $false
    }
    $client = [System.Net.Http.HttpClient]::new($messageHandler, $true)
    # The linked request token governs both response headers and body reads.
    $client.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
    $client.MaxResponseContentBufferSize = $script:MaxResponseBytes
    return $client
}

function Read-ApiAcceptanceResponseBody {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][System.IO.Stream]$Stream,
        [Parameter(Mandatory)][long]$ContentLength,
        [Parameter(Mandatory)][System.Threading.CancellationToken]$CancellationToken
    )
    if ($ContentLength -gt $script:MaxResponseBytes) { throw 'response-body-limit-charge-unknown' }
    $buffer = [byte[]]::new(4096)
    $output = [System.IO.MemoryStream]::new()
    try {
        $total = 0
        while ($true) {
            $read = $Stream.ReadAsync($buffer, 0, $buffer.Length, $CancellationToken).GetAwaiter().GetResult()
            if ($read -eq 0) { break }
            if (($total + $read) -gt $script:MaxResponseBytes) { throw 'response-body-limit-charge-unknown' }
            $output.Write($buffer, 0, $read)
            $total += $read
        }
        try { return [System.Text.UTF8Encoding]::new($false, $true).GetString($output.ToArray()) }
        catch { throw 'response-body-invalid-utf8-charge-unknown' }
    }
    finally {
        $output.Dispose()
        $buffer = $null
    }
}

function ConvertFrom-ApiAcceptanceResponse {
    param([Parameter(Mandatory)][string]$Json)
    try { return ConvertFrom-Json -InputObject $Json -ErrorAction Stop }
    catch { throw 'invalid-response-json-charge-unknown' }
}

function Send-ApiAcceptanceRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$ProviderId,
        [Parameter(Mandatory)][string]$ApiKey,
        [Parameter(Mandatory)][object]$Payload,
        [System.Threading.CancellationToken]$CancellationToken = [System.Threading.CancellationToken]::None,
        [scriptblock]$MockTransport
    )
    $provider = Get-ApiAcceptanceProvider -Id $ProviderId
    $endpoint = Assert-ApiAcceptanceEndpoint -ProviderId $ProviderId -Uri $provider.Endpoint
    $body = $Payload | ConvertTo-Json -Depth 16 -Compress
    if ([System.Text.Encoding]::UTF8.GetByteCount($body) -gt $script:MaxRequestBodyBytes) { throw 'request-body-limit' }
    if ($CancellationToken.IsCancellationRequested) { throw 'cancelled-before-request' }
    $authValue = $provider.Prefix + $ApiKey
    $client = $null; $request = $null; $response = $null; $cts = $null; $mockStream = $null
    try {
      $cts = [System.Threading.CancellationTokenSource]::CreateLinkedTokenSource($CancellationToken)
      $cts.CancelAfter([TimeSpan]::FromMilliseconds($script:RequestTimeoutMilliseconds))
      if ($MockTransport) {
        $mock = & $MockTransport $endpoint $provider.Header $authValue $body
        if ($null -eq $mock -or $null -eq $mock.StatusCode) { throw 'mock-transport-invalid' }
        $status = [int]$mock.StatusCode
        if ($status -ge 300 -and $status -lt 400) { throw 'redirect-blocked-charge-unknown' }
        if ($status -lt 200 -or $status -ge 300) { throw "http-status-$status-charge-unknown" }
        $contentLength = -1L
        if ($null -ne $mock.PSObject.Properties['ContentLength']) { $contentLength = [long]$mock.ContentLength }
        if ($null -ne $mock.PSObject.Properties['BodyStream']) { $mockStream = $mock.BodyStream }
        else { $mockStream = [System.IO.MemoryStream]::new([System.Text.Encoding]::UTF8.GetBytes([string]$mock.Body)) }
        $responseBody = Read-ApiAcceptanceResponseBody -Stream $mockStream -ContentLength $contentLength -CancellationToken $cts.Token
      }
      else {
        $client = New-ApiAcceptanceHttpClient
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, $endpoint)
        [void]$request.Headers.TryAddWithoutValidation($provider.Header, $authValue)
        $request.Content = [System.Net.Http.StringContent]::new($body, [System.Text.Encoding]::UTF8, 'application/json')
        $response = $client.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead, $cts.Token).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        if ($status -ge 300 -and $status -lt 400) { throw 'redirect-blocked-charge-unknown' }
        if (-not $response.IsSuccessStatusCode) { throw "http-status-$status-charge-unknown" }
        $contentLength = -1L
        $reportedLength = $response.Content.Headers.ContentLength
        if ($null -ne $reportedLength) { $contentLength = [long]$reportedLength }
        $stream = $response.Content.ReadAsStreamAsync($cts.Token).GetAwaiter().GetResult()
        $responseBody = Read-ApiAcceptanceResponseBody -Stream $stream -ContentLength $contentLength -CancellationToken $cts.Token
      }
    }
    catch [System.Threading.Tasks.TaskCanceledException] { if ($CancellationToken.IsCancellationRequested) { throw 'request-cancelled-charge-unknown' }; throw 'request-timeout-charge-unknown' }
    catch [System.OperationCanceledException] { if ($CancellationToken.IsCancellationRequested) { throw 'request-cancelled-charge-unknown' }; throw 'request-timeout-charge-unknown' }
    catch {
        $message = [string]$_.Exception.Message
        if ($message -match '^(endpoint-not-allowed|request-body-limit|redirect-blocked-charge-unknown|response-body-limit-charge-unknown|response-body-invalid-utf8-charge-unknown|invalid-response-json-charge-unknown|request-cancelled-charge-unknown|cancelled-before-request|request-timeout-charge-unknown|http-status-[0-9]{3}-charge-unknown)$') { throw $message }
        throw 'request-failed-charge-unknown'
    }
    finally {
        if ($cts) { $cts.Dispose() }
        if ($response) { $response.Dispose() }
        if ($request) { $request.Dispose() }
        if ($client) { $client.Dispose() }
        if ($mockStream) { $mockStream.Dispose() }
        $authValue = $null; $body = $null
    }
    $parsed = ConvertFrom-ApiAcceptanceResponse -Json $responseBody
    $responseBody = $null
    return $parsed
}

function Get-ApiAcceptanceToolSchema {
    return @(@{
        type = 'function'
        function = @{
            name = $script:ToolName
            description = 'Return one fixed local acceptance marker. It performs no file, process, or network action.'
            strict = $true
            parameters = @{
                type = 'object'
                additionalProperties = $false
                properties = @{ marker = @{ type = 'string'; enum = @($script:ToolMarker) } }
                required = @('marker')
            }
        }
    })
}

function Invoke-ApiAcceptanceLocalTool {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$ToolCall)
    if ($ToolCall.type -cne 'function' -or $ToolCall.function.name -cne $script:ToolName) { throw 'tool-name-rejected' }
    try { $argsObject = ConvertFrom-Json -InputObject ([string]$ToolCall.function.arguments) -ErrorAction Stop }
    catch { throw 'tool-arguments-rejected' }
    $names = @($argsObject.PSObject.Properties.Name)
    if ($names.Count -ne 1 -or $names[0] -cne 'marker' -or $argsObject.marker -cne $script:ToolMarker) { throw 'tool-arguments-rejected' }
    return [pscustomobject]@{ ok = $true; marker = $script:ToolMarker }
}

function New-ApiAcceptancePayload {
    [CmdletBinding()]
    param([Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$ProviderId)
    $p = Get-ApiAcceptanceProvider -Id $ProviderId
    $payload = [ordered]@{
        model = $p.Model
        messages = @(@{ role='user'; content=('For this one-time API check, call the function ' + $script:ToolName + ' exactly once with marker ' + $script:ToolMarker + '. Do not do anything else.') })
        stream = $false
        tools = @(Get-ApiAcceptanceToolSchema)
        tool_choice = $p.ToolChoice
        thinking = $p.ThinkingValue
    }
    if ($ProviderId -eq 'deepseek') { $payload['parallel_tool_calls'] = $false }
    $payload[$p.MaxField] = $p.OutputCap
    return $payload
}

function Get-ApiAcceptanceUsage {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Response)
    $usage = $Response.usage
    if ($null -eq $usage) { throw 'usage-missing-charge-unknown' }
    $inputTokens = $usage.prompt_tokens
    $outputTokens = $usage.completion_tokens
    if (($inputTokens -isnot [int] -and $inputTokens -isnot [long]) -or ($outputTokens -isnot [int] -and $outputTokens -isnot [long]) -or $inputTokens -lt 1 -or $outputTokens -lt 1) { throw 'usage-invalid-charge-unknown' }
    if ($inputTokens -gt 1000000 -or $outputTokens -gt 256) { throw 'usage-limit-exceeded-charge-unknown' }
    return [pscustomobject]@{ InputTokens = $inputTokens; OutputTokens = $outputTokens }
}

function Get-ApiAcceptanceCostCny {
    [CmdletBinding()]
    param([Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$ProviderId,[Parameter(Mandatory)][long]$InputTokens,[Parameter(Mandatory)][long]$OutputTokens,[ValidateSet('peak','off-peak')][string]$DeepSeekRate = 'peak')
    $p = Get-ApiAcceptanceProvider -Id $ProviderId
    if ($ProviderId -eq 'deepseek') {
        if ($DeepSeekRate -eq 'off-peak') { $inputCny=$p.OffPeakInputCnyPerMillion; $outputCny=$p.OffPeakOutputCnyPerMillion }
        else { $inputCny=$p.PeakInputCnyPerMillion; $outputCny=$p.PeakOutputCnyPerMillion }
    }
    else { $inputCny = $p.InputCnyPerMillion; $outputCny = $p.OutputCnyPerMillion }
    return [math]::Round((($InputTokens * $inputCny) + ($OutputTokens * $outputCny)) / 1000000.0, 8, [MidpointRounding]::AwayFromZero)
}

function Invoke-ApiAcceptanceProvider {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('deepseek','mimo')][string]$ProviderId,
        [Parameter(Mandatory)][string]$ApiKey,
        [System.Threading.CancellationToken]$CancellationToken = [System.Threading.CancellationToken]::None,
        [scriptblock]$MockTransport,
        [scriptblock]$Checkpoint,
        [ValidateSet('peak','off-peak')][string]$DeepSeekRate = 'peak'
    )
    $p = Get-ApiAcceptanceProvider -Id $ProviderId
    $budget = Get-ApiAcceptanceBudget -Id $ProviderId -DeepSeekRate $DeepSeekRate
    if ($budget.WorstCaseCny -ge $budget.LimitCny) { throw 'reserved-budget-exceeds-limit' }
    if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'missing-api-key' }
    if ($ProviderId -eq 'mimo' -and $ApiKey.StartsWith('tp-', [StringComparison]::OrdinalIgnoreCase)) { throw 'mimo-token-plan-key-not-supported-by-this-paygo-api-acceptance' }

    $ledger = [ordered]@{
        provider = $ProviderId
        provider_name = $p.Name
        model = $p.Model
        status = 'request-pending'
        request_count = 0
        maximum_request_count = 1
        context_tokens_reserved = $budget.ContextTokensReserved
        output_tokens_reserved = $budget.OutputTokensReserved
        worst_case_reserved_cny = $budget.WorstCaseCny
        pricing_currency = 'CNY'
        pricing_period = if ($ProviderId -eq 'deepseek') { $DeepSeekRate } else { 'published-rate' }
        input_cny_per_million = $budget.InputCnyPerMillion
        output_cny_per_million = $budget.OutputCnyPerMillion
        input_tokens = $null
        output_tokens = $null
        estimated_cny = $null
        charge_unknown = $true
        authentication_and_response = $false
        controlled_tool_call = $false
        error_code = $null
    }
    $notify = {
        if ($Checkpoint) {
            $snapshot = [ordered]@{}
            foreach ($key in $ledger.Keys) { $snapshot[$key] = $ledger[$key] }
            & $Checkpoint ([pscustomobject]$snapshot)
        }
    }.GetNewClosure()
    & $notify
    try {
        if ($CancellationToken.IsCancellationRequested) { throw 'cancelled-before-request' }
        $payload = New-ApiAcceptancePayload -ProviderId $ProviderId
        $ledger.request_count = 1
        $ledger.status = 'request-in-flight'
        & $notify
        $response = Send-ApiAcceptanceRequest -ProviderId $ProviderId -ApiKey $ApiKey -Payload $payload -CancellationToken $CancellationToken -MockTransport $MockTransport
        if ($null -eq $response.choices -or $response.choices.Count -ne 1 -or $null -eq $response.choices[0].message) { throw 'model-response-invalid-charge-unknown' }
        $usage = Get-ApiAcceptanceUsage -Response $response
        if ($ProviderId -eq 'deepseek') { $rate = $DeepSeekRate } else { $rate = 'peak' }
        $cost = Get-ApiAcceptanceCostCny -ProviderId $ProviderId -InputTokens $usage.InputTokens -OutputTokens $usage.OutputTokens -DeepSeekRate $rate
        if ($cost -gt $budget.LimitCny) { throw 'account-budget-exceeded-charge-unknown' }
        $ledger.input_tokens = $usage.InputTokens
        $ledger.output_tokens = $usage.OutputTokens
        $ledger.estimated_cny = $cost
        $ledger.charge_unknown = $false
        $ledger.authentication_and_response = $true
        $message = $response.choices[0].message
        $callsProperty = $message.PSObject.Properties['tool_calls']
        if ($null -eq $callsProperty -or $null -eq $callsProperty.Value -or $callsProperty.Value.Count -ne 1) { throw 'tool-call-missing' }
        $null = Invoke-ApiAcceptanceLocalTool -ToolCall $callsProperty.Value[0]
        $ledger.controlled_tool_call = $true
        $ledger.status = 'success'
    }
    catch {
        $code = [string]$_.Exception.Message
        if ($code -notmatch '^(mimo-token-plan-key-not-supported-by-this-paygo-api-acceptance|missing-api-key|request-body-limit|redirect-blocked-charge-unknown|response-body-limit-charge-unknown|response-body-invalid-utf8-charge-unknown|invalid-response-json-charge-unknown|request-cancelled-charge-unknown|cancelled-before-request|request-timeout-charge-unknown|http-status-[0-9]{3}-charge-unknown|request-failed-charge-unknown|usage-missing-charge-unknown|usage-invalid-charge-unknown|usage-limit-exceeded-charge-unknown|model-response-invalid-charge-unknown|tool-call-missing|tool-name-rejected|tool-arguments-rejected|account-budget-exceeded-charge-unknown)$') { $code='acceptance-failed-charge-unknown' }
        $ledger.status = 'failed'
        $ledger.error_code = $code
        if ($code -eq 'cancelled-before-request' -or $code -eq 'request-body-limit') { $ledger.request_count = 0 }
        if ($code -notmatch 'charge-unknown$') { $ledger.charge_unknown = $false; $ledger.worst_case_reserved_cny = 0.0 }
    }
    finally { $ApiKey = $null; $payload = $null; $response = $null; $message = $null }
    & $notify
    return [pscustomobject]$ledger
}

Export-ModuleMember -Function Get-ApiAcceptanceProvider,Get-ApiAcceptanceBudget,Assert-ApiAcceptanceEndpoint,New-ApiAcceptanceHttpClient,Get-ApiAcceptanceToolSchema,Invoke-ApiAcceptanceLocalTool,Send-ApiAcceptanceRequest,New-ApiAcceptancePayload,Get-ApiAcceptanceUsage,Get-ApiAcceptanceCostCny,Invoke-ApiAcceptanceProvider
