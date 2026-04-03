param(
    [Parameter(Position = 0)]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Arg1,

    [Parameter(Position = 2)]
    [string]$Arg2,

    [Parameter(Position = 3)]
    [string]$Arg3
)

# --- Config file management ---
$configDir = Join-Path (Join-Path $HOME ".config") "llama"
$configFile = Join-Path $configDir "config.json"

function Read-Config {
    if (Test-Path $configFile) {
        Get-Content $configFile -Raw | ConvertFrom-Json
    } else {
        [PSCustomObject]@{ current = ""; contexts = [PSCustomObject]@{} }
    }
}

function Save-Config($cfg) {
    if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Force -Path $configDir | Out-Null }
    $cfg | ConvertTo-Json -Depth 5 | Set-Content $configFile
}

# --- Handle context command before resolving host ---
if ($Command -eq "context") {
    $cfg = Read-Config

    if (-not $Arg1) {
        # List contexts
        $names = $cfg.contexts.PSObject.Properties
        if ($names.Count -eq 0) {
            Write-Host "No contexts configured. Add one with: llama context add <name> <host:port>" -ForegroundColor Yellow
        } else {
            foreach ($p in $names) {
                $marker = if ($p.Name -eq $cfg.current) { "*" } else { " " }
                $color = if ($p.Name -eq $cfg.current) { "Green" } else { "White" }
                Write-Host ("{0} {1,-12} {2}" -f $marker, $p.Name, $p.Value.host) -ForegroundColor $color
            }
        }
        return
    }

    if ($Arg1 -eq "add") {
        if (-not $Arg2 -or -not $Arg3) {
            Write-Host "Usage: llama context add <name> <host:port>" -ForegroundColor Yellow
            return
        }
        $name = $Arg2
        $hostPort = $Arg3
        $cfg.contexts | Add-Member -NotePropertyName $name -NotePropertyValue ([PSCustomObject]@{ host = $hostPort }) -Force
        if (-not $cfg.current) { $cfg.current = $name }
        Save-Config $cfg
        Write-Host "Added context `"$name`" ($hostPort)" -ForegroundColor Green
        return
    }

    if ($Arg1 -eq "rm") {
        if (-not $Arg2) {
            Write-Host "Usage: llama context rm <name>" -ForegroundColor Yellow
            return
        }
        $cfg.contexts.PSObject.Properties.Remove($Arg2)
        if ($cfg.current -eq $Arg2) { $cfg.current = "" }
        Save-Config $cfg
        Write-Host "Removed context `"$Arg2`"" -ForegroundColor Green
        return
    }

    # Switch context: llama context <name>
    $target = $Arg1
    $exists = $cfg.contexts.PSObject.Properties[$target]
    if (-not $exists) {
        Write-Host "Unknown context `"$target`". Available:" -ForegroundColor Red
        foreach ($p in $cfg.contexts.PSObject.Properties) { Write-Host "  $($p.Name)  $($p.Value.host)" }
        return
    }
    $cfg.current = $target
    Save-Config $cfg
    Write-Host "Switched to context `"$target`" ($($exists.Value.host))" -ForegroundColor Green
    return
}

# --- Resolve host: env var > config file ---
$contextName = ""
if ($env:LLAMA_HOST) {
    $resolvedHost = $env:LLAMA_HOST
} else {
    $cfg = Read-Config
    if ($cfg.current -and $cfg.contexts.PSObject.Properties[$cfg.current]) {
        $contextName = $cfg.current
        $resolvedHost = $cfg.contexts.$($cfg.current).host
    } else {
        Write-Host "No active context. Set one up:" -ForegroundColor Red
        Write-Host "  llama context add local 127.0.0.1:8080" -ForegroundColor Yellow
        Write-Host "  llama context local" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Or set LLAMA_HOST directly:" -ForegroundColor Red
        Write-Host '  $env:LLAMA_HOST = "127.0.0.1:8080"' -ForegroundColor Yellow
        return
    }
}

$label = if ($contextName) { "$contextName ($resolvedHost)" } else { $resolvedHost }
$base = "http://$resolvedHost"
$hostIP = ($resolvedHost -split ":")[0]

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
            Write-Host "${label}: $r"
        } catch {
            Write-Host "${label}: unreachable" -ForegroundColor Red
        }
    }

    "status" {
        try {
            $r = Invoke-RestMethod -Uri "$base/running" -TimeoutSec 5
            $r | ConvertTo-Json -Depth 5
        } catch {
            Write-Host "${label}: unreachable" -ForegroundColor Red
            return
        }
        # If a model is loaded, show its server config
        try {
            $props = Invoke-RestMethod -Uri "$base/props" -TimeoutSec 5
            $dgs = $props.default_generation_settings
            if ($dgs.n_ctx) {
                $ctx = if ($dgs.n_ctx -ge 1024) { "{0:N0} ({1}K)" -f $dgs.n_ctx, [math]::Floor($dgs.n_ctx / 1024) } else { "{0:N0}" -f $dgs.n_ctx }
                Write-Host "Context:       $ctx tokens"
            }
            if ($props.total_slots) { Write-Host "Parallel:      $($props.total_slots)" }
            foreach ($item in @(@("Cache (K)", "cache_type_k"), @("Cache (V)", "cache_type_v"))) {
                $val = if ($props.PSObject.Properties[$item[1]]) { $props.$($item[1]) } elseif ($dgs.PSObject.Properties[$item[1]]) { $dgs.$($item[1]) } else { $null }
                if ($val) { Write-Host "$($item[0]):     $val" }
            }
        } catch {}
    }

    "test" {
        if (-not $Arg1) {
            Write-Host "Usage: llama test <model>" -ForegroundColor Yellow
            return
        }
        $body = @{
            model      = $Arg1
            messages   = @(@{ role = "user"; content = "Write a haiku about coding." })
            max_tokens = 100
        } | ConvertTo-Json -Depth 3

        Write-Host "Loading $Arg1 on $label..." -ForegroundColor Cyan
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
        $modelName = if ($Arg1) { $Arg1 } else { "devstral-small-2" }
        $body = @{
            model      = $modelName
            messages   = @(@{ role = "user"; content = $prompt })
            max_tokens = 500
        } | ConvertTo-Json -Depth 3

        Write-Host "Benchmarking $modelName on $label..." -ForegroundColor Cyan
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

    "info" {
        if (-not $Arg1) {
            Write-Host "Usage: llama info <model>" -ForegroundColor Yellow
            return
        }
        Write-Host "Loading $Arg1 on $label..." -ForegroundColor Cyan
        try {
            $props = Invoke-RestMethod -Uri "$base/upstream/$Arg1/props" -TimeoutSec 120
        } catch {
            Write-Host "Failed to load $Arg1" -ForegroundColor Red
            return
        }
        $dgs = $props.default_generation_settings
        Write-Host "Model:         $Arg1"
        if ($dgs.n_ctx) {
            $ctx = if ($dgs.n_ctx -ge 1024) { "{0:N0} ({1}K)" -f $dgs.n_ctx, [math]::Floor($dgs.n_ctx / 1024) } else { "{0:N0}" -f $dgs.n_ctx }
            Write-Host "Context:       $ctx tokens"
        }
        if ($props.total_slots) { Write-Host "Parallel:      $($props.total_slots)" }
        foreach ($item in @(@("Cache (K)", "cache_type_k"), @("Cache (V)", "cache_type_v"))) {
            $val = if ($props.PSObject.Properties[$item[1]]) { $props.$($item[1]) } elseif ($dgs.PSObject.Properties[$item[1]]) { $dgs.$($item[1]) } else { $null }
            if ($val) { Write-Host "$($item[0]):     $val" }
        }
        if ($props.model_path) { Write-Host "Model path:    $($props.model_path)" }
    }

    "models" {
        try {
            $r = Invoke-RestMethod -Uri "$base/v1/models" -TimeoutSec 5
            Write-Host "Models on ${label}:" -ForegroundColor Cyan
            foreach ($m in $r.data) {
                Write-Host "  - $($m.id)"
            }
        } catch {
            Write-Host "${label}: unreachable" -ForegroundColor Red
        }
    }

    default {
        Write-Host "Usage: llama <command> [args]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  health              Check if llama-swap is running"
        Write-Host "  status              Show currently loaded model + config"
        Write-Host "  info <model>        Show model config (context, cache, etc.)"
        Write-Host "  test <model>        Send a test prompt"
        Write-Host "  speed [model]       Benchmark generation speed"
        Write-Host "  restart             Restart the llama-swap service"
        Write-Host "  models              List available models"
        Write-Host ""
        Write-Host "Context management:"
        Write-Host "  context             List all contexts"
        Write-Host "  context <name>      Switch active context"
        Write-Host "  context add <name> <host:port>"
        Write-Host "  context rm <name>"
    }
}
