param(
    [Parameter(Position = 0)]
    [ValidateSet("health", "status", "test", "speed", "restart", "models")]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Model
)

if (-not $env:LLAMA_HOST) {
    Write-Host "LLAMA_HOST not set. Export it as host:port, e.g.:" -ForegroundColor Red
    Write-Host '  $env:LLAMA_HOST = "127.0.0.1:8080"' -ForegroundColor Yellow
    return
}

$base = "http://$env:LLAMA_HOST"
$hostIP = ($env:LLAMA_HOST -split ":")[0]

# Detect if the target is the local machine
$localAddrs = @("127.0.0.1", "localhost") + @(
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty IPAddress
)
$isLocal = $localAddrs -contains $hostIP

switch ($Command) {
    "health" {
        try {
            $r = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 5
            Write-Host "$env:LLAMA_HOST`: $r"
        } catch {
            Write-Host "$env:LLAMA_HOST`: unreachable" -ForegroundColor Red
        }
    }

    "status" {
        try {
            $r = Invoke-RestMethod -Uri "$base/running" -TimeoutSec 5
            $r | ConvertTo-Json -Depth 5
        } catch {
            Write-Host "$env:LLAMA_HOST`: unreachable" -ForegroundColor Red
        }
    }

    "test" {
        if (-not $Model) {
            Write-Host "Usage: llama test <model>" -ForegroundColor Yellow
            return
        }
        $body = @{
            model      = $Model
            messages   = @(@{ role = "user"; content = "Write a haiku about coding." })
            max_tokens = 100
        } | ConvertTo-Json -Depth 3

        Write-Host "Loading $Model on $env:LLAMA_HOST..." -ForegroundColor Cyan
        try {
            $r = Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120
            Write-Host "`n$($r.choices[0].message.content)" -ForegroundColor Green
            Write-Host "`nTokens: $($r.usage.prompt_tokens) prompt + $($r.usage.completion_tokens) completion"
            if ($r.timings) {
                Write-Host ("Speed: {0:F1} tok/s prompt, {1:F1} tok/s generation" -f $r.timings.prompt_per_second, $r.timings.predicted_per_second)
            }
        } catch {
            Write-Host "Error: $_" -ForegroundColor Red
        }
    }

    "speed" {
        $prompt = "Write a detailed explanation of how a CPU pipeline works, including fetch, decode, execute, memory access, and writeback stages. Include examples of pipeline hazards and how modern processors handle them."
        $modelName = if ($Model) { $Model } else { "devstral-small-2" }
        $body = @{
            model      = $modelName
            messages   = @(@{ role = "user"; content = $prompt })
            max_tokens = 500
        } | ConvertTo-Json -Depth 3

        Write-Host "Benchmarking $modelName on $env:LLAMA_HOST..." -ForegroundColor Cyan
        try {
            $r = Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 300
            if ($r.timings) {
                Write-Host "`nResults:" -ForegroundColor Green
                Write-Host ("  Prompt:     {0:F1} tok/s ({1} tokens)" -f $r.timings.prompt_per_second, $r.usage.prompt_tokens)
                Write-Host ("  Generation: {0:F1} tok/s ({1} tokens)" -f $r.timings.predicted_per_second, $r.usage.completion_tokens)
            } else {
                Write-Host "`nTokens: $($r.usage.prompt_tokens) prompt + $($r.usage.completion_tokens) completion"
            }
        } catch {
            Write-Host "Error: $_" -ForegroundColor Red
        }
    }

    "restart" {
        if ($isLocal) {
            Write-Host "Restarting llama-swap service locally..." -ForegroundColor Cyan
            nssm restart llama-swap
        } else {
            Write-Host "Restarting llama-swap on $hostIP via SSH..." -ForegroundColor Cyan
            ssh $hostIP "sudo systemctl restart llama-swap"
            Write-Host "Done." -ForegroundColor Green
        }
    }

    "models" {
        try {
            $r = Invoke-RestMethod -Uri "$base/v1/models" -TimeoutSec 5
            Write-Host "Models on $env:LLAMA_HOST`:" -ForegroundColor Cyan
            foreach ($m in $r.data) {
                Write-Host "  - $($m.id)"
            }
        } catch {
            Write-Host "$env:LLAMA_HOST`: unreachable" -ForegroundColor Red
        }
    }

    default {
        Write-Host "Usage: llama <command> [model]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  health           Check if llama-swap is running"
        Write-Host "  status           Show currently loaded model"
        Write-Host "  test <model>     Send a test prompt"
        Write-Host "  speed [model]    Benchmark generation speed"
        Write-Host "  restart          Restart the llama-swap service"
        Write-Host "  models           List available models"
        Write-Host ""
        Write-Host "Requires: `$env:LLAMA_HOST = `"host:port`""
    }
}
