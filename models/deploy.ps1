#requires -Version 5.1
<#
.SYNOPSIS
  Build and push the RTX-4090 and RTX-5090 Ollama Modelfiles to the odytrice/* namespace.

.EXAMPLES
  # Build everything, then push everything
  ./deploy.ps1

  # Only the 4090 variants
  ./deploy.ps1 -Filter 4090

  # Only the gemma models
  ./deploy.ps1 -Filter gemma4

  # Single model
  ./deploy.ps1 -Filter qwen3.6-35b:5090

  # Build locally without pushing
  ./deploy.ps1 -BuildOnly

  # Push pre-built tags (re-push after a registry hiccup)
  ./deploy.ps1 -PushOnly

  # Preview commands without executing
  ./deploy.ps1 -DryRun
#>
param(
  [switch]$BuildOnly,
  [switch]$PushOnly,
  [string]$Filter = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptRoot = $PSScriptRoot
if (-not $scriptRoot) { $scriptRoot = Split-Path $MyInvocation.MyCommand.Path }

$models = @(
  @{ Folder = "gemma4-12b";  File = "4090.Modelfile";  Tag = "odytrice/gemma4-12b:4090"   },
  @{ Folder = "gemma4-12b";  File = "5090.Modelfile";  Tag = "odytrice/gemma4-12b:5090"   },
  @{ Folder = "gemma4-26b";  File = "4090.Modelfile";  Tag = "odytrice/gemma4-26b:4090"   },
  @{ Folder = "gemma4-26b";  File = "5090.Modelfile";  Tag = "odytrice/gemma4-26b:5090"   },
  @{ Folder = "gemma4-31b";  File = "5090.Modelfile";  Tag = "odytrice/gemma4-31b:5090"   },
  @{ Folder = "qwen3.6-27b"; File = "5090.Modelfile";  Tag = "odytrice/qwen3.6-27b:5090"  },
  @{ Folder = "qwen3.6-35b"; File = "5090.Modelfile";  Tag = "odytrice/qwen3.6-35b:5090"  }
)

function Invoke-Step([string]$Label, [string[]]$ArgList) {
  Write-Host ""
  Write-Host "==> $Label" -ForegroundColor Cyan
  Write-Host "    ollama $($ArgList -join ' ')" -ForegroundColor DarkGray
  if ($DryRun) { return }
  & ollama @ArgList
  if ($LASTEXITCODE -ne 0) { throw "ollama exited with $LASTEXITCODE" }
}

foreach ($m in $models) {
  if ($Filter -and ($m.Tag -notlike "*$Filter*")) { continue }

  $modelfilePath = Join-Path $scriptRoot (Join-Path $m.Folder $m.File)
  if (-not (Test-Path -LiteralPath $modelfilePath)) {
    throw "Modelfile not found: $modelfilePath"
  }

  if (-not $PushOnly) {
    Invoke-Step "Build $($m.Tag)" @("create", $m.Tag, "-f", $modelfilePath)
  }
  if (-not $BuildOnly) {
    Invoke-Step "Push  $($m.Tag)" @("push", $m.Tag)
  }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
