$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'api_acceptance.psm1') -Force

$script:assertions = 0
function Assert-True([bool]$Condition, [string]$Message) {
    $script:assertions++
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

$deep = Get-ApiAcceptanceBudget deepseek -DeepSeekRate peak
$mimo = Get-ApiAcceptanceBudget mimo
Assert-True ($deep.ContextTokensReserved -eq 1000000 -and $deep.OutputTokensReserved -eq 256 -and $deep.RequestCount -eq 1) 'DeepSeek reserves complete context and one capped request.'
Assert-True ($deep.WorstCaseCny -lt 2.50 -and [math]::Abs($deep.WorstCaseCny - 2.002048) -lt 0.00000001) 'DeepSeek peak reserve uses official CNY input and output prices with full context plus output cap.'
Assert-True ($mimo.ContextTokensReserved -eq 1000000 -and $mimo.OutputTokensReserved -eq 256 -and $mimo.RequestCount -eq 1) 'MiMo reserves complete context and one capped request.'
Assert-True ($mimo.WorstCaseCny -lt 2.50 -and [math]::Abs($mimo.WorstCaseCny - 1.000512) -lt 0.00000001) 'MiMo reserve is below the limit.'
Assert-True ((Get-ApiAcceptanceBudget deepseek -DeepSeekRate off-peak).WorstCaseCny -lt $deep.WorstCaseCny) 'DeepSeek off-peak reserve is lower than peak reserve.'
Assert-True ($deep.InputCnyPerMillion -eq 2 -and $deep.OutputCnyPerMillion -eq 8) 'DeepSeek peak prices are directly represented in CNY with no FX conversion.'
Assert-True ((Get-ApiAcceptanceCostCny deepseek -InputTokens 42 -OutputTokens 9) -eq 0.000156) 'DeepSeek fake usage estimate uses the official direct CNY peak rate.'

foreach ($provider in @('deepseek','mimo')) {
    $config = Get-ApiAcceptanceProvider $provider
    Assert-True ((Assert-ApiAcceptanceEndpoint -ProviderId $provider -Uri $config.Endpoint).AbsoluteUri -ceq $config.Endpoint) "$provider official endpoint accepted."
    foreach ($badUri in @('http://api.deepseek.com/chat/completions','https://api.deepseek.com.evil.test/chat/completions','https://api.deepseek.com/chat/completions?next=https://evil.test','https://user:pass@api.deepseek.com/chat/completions')) {
        try { $null = Assert-ApiAcceptanceEndpoint -ProviderId deepseek -Uri $badUri; throw 'unexpected accepted endpoint' }
        catch { Assert-True ($_.Exception.Message -eq 'endpoint-not-allowed') 'Endpoint allowlist rejects noncanonical destinations.' }
    }
}

$toolJson = '{"marker":"UPG_API_PROBE_OK"}'
$toolResponse = '{"id":"mock-id","model":"mock-model","choices":[{"index":0,"message":{"role":"assistant","content":null,"tool_calls":[{"id":"call-1","type":"function","function":{"name":"upg_record_probe","arguments":"' + $toolJson.Replace('"','\"') + '"}}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":42,"completion_tokens":9,"total_tokens":51}}'
$testKey = 'TEST_ONLY_SECRET_DO_NOT_LOG'

if (-not ('UpgAcceptanceBlockingReadStream' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
public sealed class UpgAcceptanceBlockingReadStream : Stream {
    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => throw new NotSupportedException();
    public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) {
        var completion = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        var registration = cancellationToken.Register(() => completion.TrySetCanceled(cancellationToken));
        completion.Task.ContinueWith(_ => registration.Dispose(), TaskScheduler.Default);
        return completion.Task;
    }
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
}
public sealed class UpgAcceptanceFiniteReadStream : Stream {
    private readonly byte[] data;
    private int position;
    public UpgAcceptanceFiniteReadStream(byte[] bytes) { data = bytes; }
    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => throw new NotSupportedException();
    public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
    public override void Flush() { }
    public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) {
        cancellationToken.ThrowIfCancellationRequested();
        var length = Math.Min(count, data.Length - position);
        if (length > 0) { Array.Copy(data, position, buffer, offset, length); position += length; }
        return Task.FromResult(length);
    }
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
}
public sealed class UpgAcceptanceFakeHttpHandler : HttpMessageHandler {
    private readonly Stream responseBody;
    public int CallCount { get; private set; }
    public bool LastResponseHadUnknownLength { get; private set; }
    public UpgAcceptanceFakeHttpHandler(Stream stream) { responseBody = stream; }
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) {
        CallCount++;
        var response = new HttpResponseMessage(System.Net.HttpStatusCode.OK);
        response.Content = new StreamContent(responseBody);
        LastResponseHadUnknownLength = response.Content.Headers.ContentLength == null;
        response.Headers.TransferEncodingChunked = true;
        return Task.FromResult(response);
    }
}
'@ -ReferencedAssemblies @([System.Net.Http.HttpMessageHandler].Assembly.Location, [System.Net.HttpStatusCode].Assembly.Location)
}

foreach ($provider in @('deepseek','mimo')) {
    $config = Get-ApiAcceptanceProvider $provider
    $calls = [System.Collections.Generic.List[object]]::new()
    $checkpoints = [System.Collections.Generic.List[object]]::new()
    $mock = {
        param($endpoint,$header,$auth,$body)
        $calls.Add([pscustomobject]@{ endpoint=$endpoint.AbsoluteUri; header=$header; auth=$auth; body=$body })
        return [pscustomobject]@{ StatusCode=200; Body=$toolResponse }
    }.GetNewClosure()
    $checkpoint = { param($row) $checkpoints.Add($row) }.GetNewClosure()
    $result = Invoke-ApiAcceptanceProvider -ProviderId $provider -ApiKey $testKey -MockTransport $mock -Checkpoint $checkpoint
    Assert-True ($result.status -eq 'success' -and $result.request_count -eq 1) "$provider single mock request completes."
    Assert-True ($result.authentication_and_response -and $result.controlled_tool_call) "$provider validates response and executes only the local probe."
    Assert-True ($calls.Count -eq 1 -and $checkpoints.Count -ge 3) "$provider is called once and checkpointed before/after the request."
    Assert-True ($calls[0].endpoint -ceq $config.Endpoint) "$provider sends only to the fixed official endpoint."
    Assert-True ($calls[0].header -ceq $config.Header -and $calls[0].auth.Contains($testKey)) "$provider uses its documented auth header."
    Assert-True ($calls[0].body -notlike "*$testKey*") 'Credential is absent from request JSON body.'
    $request = $calls[0].body | ConvertFrom-Json
    Assert-True ($request.stream -eq $false -and $request.thinking.type -eq 'disabled') "$provider disables streaming and thinking."
    $configuredCap = $request.($config.MaxField)
    Assert-True ($configuredCap -eq 256 -and $request.tools.Count -eq 1) "$provider output cap and single function tool are set."
    Assert-True (($request.tool_choice -eq 'required') -or ($provider -eq 'mimo' -and $request.tool_choice -eq 'auto')) "$provider tool choice follows the documented support."
    Assert-True (($result | ConvertTo-Json -Depth 8 -Compress) -notlike "*$testKey*") 'No key appears in usage result.'
    Assert-True ($result.estimated_cny -lt 2.50 -and $result.charge_unknown -eq $false) "$provider records bounded usage with known cost."
    if ($provider -eq 'deepseek') { Assert-True ($result.estimated_cny -eq 0.000156) 'DeepSeek fake response ledger uses direct CNY peak pricing.' }
}

$redirectCount = 0
$redirectMock = { param($endpoint,$header,$auth,$body) $script:redirectCount++; [pscustomobject]@{ StatusCode=302; Body='' } }
$redirect = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey -MockTransport $redirectMock
Assert-True ($script:redirectCount -eq 1 -and $redirect.status -eq 'failed' -and $redirect.charge_unknown -and $redirect.error_code -eq 'redirect-blocked-charge-unknown') 'Redirect is blocked, not followed, retried, or treated as zero spend.'

$serverErrorCount = 0
$serverErrorMock = { param($endpoint,$header,$auth,$body) $script:serverErrorCount++; [pscustomobject]@{ StatusCode=503; Body='' } }
$serverError = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey -MockTransport $serverErrorMock
Assert-True ($script:serverErrorCount -eq 1 -and $serverError.status -eq 'failed' -and $serverError.charge_unknown -and $serverError.error_code -eq 'http-status-503-charge-unknown') '5xx is fully reserved and is not retried.'

$cancelSource = [System.Threading.CancellationTokenSource]::new()
$cancelSource.Cancel()
$cancelCallCount = 0
$cancelMock = { param($endpoint,$header,$auth,$body) $script:cancelCallCount++; [pscustomobject]@{ StatusCode=200; Body=$toolResponse } }
$cancelled = Invoke-ApiAcceptanceProvider -ProviderId deepseek -ApiKey $testKey -CancellationToken $cancelSource.Token -MockTransport $cancelMock
$cancelSource.Dispose()
Assert-True ($script:cancelCallCount -eq 0 -and $cancelled.request_count -eq 0 -and -not $cancelled.charge_unknown -and $cancelled.error_code -eq 'cancelled-before-request') 'Cancellation before submission sends nothing and reserves no charge.'

$missingToolJson = '{"choices":[{"message":{"role":"assistant","content":"no tool"}}],"usage":{"prompt_tokens":42,"completion_tokens":9}}'
$missCount = 0
$missingToolMock = { param($endpoint,$header,$auth,$body) $script:missCount++; [pscustomobject]@{ StatusCode=200; Body=$missingToolJson } }
$missingTool = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey -MockTransport $missingToolMock
Assert-True ($script:missCount -eq 1 -and $missingTool.status -eq 'failed' -and $missingTool.error_code -eq 'tool-call-missing' -and -not $missingTool.charge_unknown -and $null -ne $missingTool.estimated_cny) 'No tool call fails once without retry while preserving known usage cost.'

$badToolJson = '{"choices":[{"message":{"role":"assistant","tool_calls":[{"id":"call-1","type":"function","function":{"name":"run_shell","arguments":"{}"}}]}}],"usage":{"prompt_tokens":42,"completion_tokens":9}}'
$badToolMock = { param($endpoint,$header,$auth,$body) [pscustomobject]@{ StatusCode=200; Body=$badToolJson } }
$badTool = Invoke-ApiAcceptanceProvider -ProviderId deepseek -ApiKey $testKey -MockTransport $badToolMock
Assert-True ($badTool.status -eq 'failed' -and $badTool.error_code -eq 'tool-name-rejected' -and -not $badTool.controlled_tool_call -and -not $badTool.charge_unknown) 'Unknown model tool is rejected after one response, with no execution.'

try { $null = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey 'tp-TEST_TOKEN_PLAN' -MockTransport $mock; throw 'unexpected Token Plan key accepted' }
catch { Assert-True ($_.Exception.Message -eq 'mimo-token-plan-key-not-supported-by-this-paygo-api-acceptance') 'MiMo Token Plan key is refused before any API request.' }

$module = Get-Module api_acceptance
$module.SessionState.PSVariable.Set('RequestTimeoutMilliseconds', 250)
try {
    $unknownLengthCount = 0
    $unknownLengthMock = {
        param($endpoint,$header,$auth,$body)
        $script:unknownLengthCount++
        [pscustomobject]@{ StatusCode=200; BodyStream=[System.IO.MemoryStream]::new([byte[]]::new(65537)); ContentLength=-1 }
    }
    $unknownLength = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey -MockTransport $unknownLengthMock
    Assert-True ($script:unknownLengthCount -eq 1 -and $unknownLength.error_code -eq 'response-body-limit-charge-unknown' -and $unknownLength.request_count -eq 1) 'Unknown-length/chunked oversized response stops during bounded streaming after one request.'
    Assert-True ($unknownLength.charge_unknown -and $unknownLength.worst_case_reserved_cny -eq $mimo.WorstCaseCny) 'Unknown-length oversized response retains full reserve.'

    $timeoutCount = 0
    $timeoutMock = {
        param($endpoint,$header,$auth,$body)
        $script:timeoutCount++
        [pscustomobject]@{ StatusCode=200; BodyStream=[UpgAcceptanceBlockingReadStream]::new(); ContentLength=-1 }
    }
    $timedOut = Invoke-ApiAcceptanceProvider -ProviderId deepseek -ApiKey $testKey -MockTransport $timeoutMock
    Assert-True ($script:timeoutCount -eq 1 -and $timedOut.error_code -eq 'request-timeout-charge-unknown' -and $timedOut.request_count -eq 1) 'A body stream that never completes times out after one request.'
    Assert-True ($timedOut.charge_unknown -and $timedOut.worst_case_reserved_cny -eq $deep.WorstCaseCny) 'Timed-out body read retains full reserve.'

    $cancelSource = [System.Threading.CancellationTokenSource]::new()
    $cancelSource.CancelAfter(100)
    $cancelBodyCount = 0
    $cancelBodyMock = {
        param($endpoint,$header,$auth,$body)
        $script:cancelBodyCount++
        [pscustomobject]@{ StatusCode=200; BodyStream=[UpgAcceptanceBlockingReadStream]::new(); ContentLength=-1 }
    }
    $cancelBody = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey -CancellationToken $cancelSource.Token -MockTransport $cancelBodyMock
    $cancelSource.Dispose()
    Assert-True ($script:cancelBodyCount -eq 1 -and $cancelBody.error_code -eq 'request-cancelled-charge-unknown' -and $cancelBody.request_count -eq 1) 'Cancellation during a pending body read returns promptly after one request.'
    Assert-True ($cancelBody.charge_unknown -and $cancelBody.worst_case_reserved_cny -eq $mimo.WorstCaseCny) 'Cancelled pending body read retains full reserve.'

    $fakeLimitHandler = [UpgAcceptanceFakeHttpHandler]::new([UpgAcceptanceFiniteReadStream]::new([byte[]]::new(65537)))
    $module.SessionState.PSVariable.Set('HttpMessageHandlerForTests', $fakeLimitHandler)
    $fakeLimit = Invoke-ApiAcceptanceProvider -ProviderId deepseek -ApiKey $testKey
    Assert-True ($fakeLimitHandler.CallCount -eq 1 -and $fakeLimitHandler.LastResponseHadUnknownLength -and $fakeLimit.error_code -eq 'response-body-limit-charge-unknown' -and $fakeLimit.request_count -eq 1) ("Fake HttpClient path expected chunked unknown-length body-limit/no-retry; calls=$($fakeLimitHandler.CallCount), unknownLength=$($fakeLimitHandler.LastResponseHadUnknownLength), error=$($fakeLimit.error_code), requests=$($fakeLimit.request_count).")
    Assert-True ($fakeLimit.charge_unknown -and $fakeLimit.worst_case_reserved_cny -eq $deep.WorstCaseCny) 'Production HTTP path retains full reserve on unknown-length overflow.'

    $fakeTimeoutHandler = [UpgAcceptanceFakeHttpHandler]::new([UpgAcceptanceBlockingReadStream]::new())
    $module.SessionState.PSVariable.Set('HttpMessageHandlerForTests', $fakeTimeoutHandler)
    $fakeTimeout = Invoke-ApiAcceptanceProvider -ProviderId mimo -ApiKey $testKey
    Assert-True ($fakeTimeoutHandler.CallCount -eq 1 -and $fakeTimeout.error_code -eq 'request-timeout-charge-unknown' -and $fakeTimeout.request_count -eq 1) 'Fake HttpClient handler body hang times out through production SendAsync/body streaming with no retry.'
    Assert-True ($fakeTimeout.charge_unknown -and $fakeTimeout.worst_case_reserved_cny -eq $mimo.WorstCaseCny) 'Production HTTP path retains full reserve on body timeout.'

    $fakeCancelSource = [System.Threading.CancellationTokenSource]::new()
    $fakeCancelSource.CancelAfter(100)
    $fakeCancelHandler = [UpgAcceptanceFakeHttpHandler]::new([UpgAcceptanceBlockingReadStream]::new())
    $module.SessionState.PSVariable.Set('HttpMessageHandlerForTests', $fakeCancelHandler)
    $fakeCancelled = Invoke-ApiAcceptanceProvider -ProviderId deepseek -ApiKey $testKey -CancellationToken $fakeCancelSource.Token
    $fakeCancelSource.Dispose()
    Assert-True ($fakeCancelHandler.CallCount -eq 1 -and $fakeCancelled.error_code -eq 'request-cancelled-charge-unknown' -and $fakeCancelled.request_count -eq 1) 'External cancellation interrupts a pending fake HTTP response body after one request.'
    Assert-True ($fakeCancelled.charge_unknown -and $fakeCancelled.worst_case_reserved_cny -eq $deep.WorstCaseCny) 'Production HTTP path retains full reserve when user cancels body read.'
}
finally {
    $module.SessionState.PSVariable.Set('HttpMessageHandlerForTests', $null)
    $module.SessionState.PSVariable.Set('RequestTimeoutMilliseconds', 20000)
}

$source = Get-Content (Join-Path $PSScriptRoot 'api_acceptance.psm1') -Raw
Assert-True ($source -match 'AllowAutoRedirect\s*=\s*\$false') 'Production HttpClient does not follow redirects.'
Assert-True ($source -match 'PeakInputCnyPerMillion\s*=\s*2\.0\s*;\s*PeakOutputCnyPerMillion\s*=\s*8\.0') 'DeepSeek budget uses official CNY peak input and output rates.'
Assert-True ($source -notmatch 'DeepSeekFx|PerUsd|InputUsdPerMillion|OutputUsdPerMillion') 'DeepSeek price calculations have no foreign-exchange conversion path.'
Assert-True ($source -match 'ReadAsStreamAsync\(\$cts\.Token\)') 'Production response body stream is acquired with the request cancellation token.'
Assert-True ($source -match 'ReadAsync\(\$buffer, 0, \$buffer\.Length, \$CancellationToken\)') 'Response is consumed incrementally with cancellation, not buffered as a whole.'
Assert-True ($source -notmatch '(?im)\b(Start-Process|ProcessStartInfo|Start-Job|Start-ThreadJob)\b') 'The API-key-bearing execution path creates no child process or job.'

Write-Output "PASS: $script:assertions mock and static assertions; no model request was made."
