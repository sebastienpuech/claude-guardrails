<#
    Deploie la couche globale Claude Code : CLAUDE.md + hooks -> ~/.claude/

    Ce script COPIE le CLAUDE.md et les hooks, puis VERIFIE que settings.json declare
    bien les hooks attendus. Il ne reecrit jamais settings.json : c'est de la config
    utilisateur (modele, plugins, theme, permissions), on ne patche pas du JSON a l'aveugle.

    Usage :
      powershell -ExecutionPolicy Bypass -File deploy.ps1            # deploie
      powershell -ExecutionPolicy Bypass -File deploy.ps1 -Verifier  # constate la derive, n'ecrit rien

    Exit 0 = deploye et conforme. Exit 2 = derive detectee (fail-closed).
#>
param([switch]$Verifier)

$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
$Cible  = Join-Path $HOME ".claude"
$derive = 0

Write-Host "Source : $Source"
Write-Host "Cible  : $Cible`n"

# --- 1. Golden vert avant tout deploiement ---------------------------------
Write-Host "[1/4] Test de contournement des hooks..."
& python (Join-Path $Source "tests\test_hooks.py") | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "REFUS : le golden des hooks est rouge. Rien n'est deploye." -ForegroundColor Red
    Write-Host "        Relancer : python tests\test_hooks.py"
    exit 2
}
Write-Host "      golden vert.`n"

# --- 2. CLAUDE.md ----------------------------------------------------------
# Source nommee CLAUDE-global.md pour ne PAS etre auto-chargee comme memoire de
# sous-dossier quand on travaille dans ce repo. Deployee sous son nom canonique.
Write-Host "[2/4] CLAUDE-global.md -> ~/.claude/CLAUDE.md"
$src = Join-Path $Source "CLAUDE-global.md"
$dst = Join-Path $Cible  "CLAUDE.md"
$identique = (Test-Path $dst) -and
             ((Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash)
if ($identique) {
    Write-Host "      a jour."
} elseif ($Verifier) {
    Write-Host "      DERIVE : le deploye differe de la source." -ForegroundColor Yellow
    $derive++
} else {
    Copy-Item $src $dst -Force
    Write-Host "      deploye."
}

# --- 3. hooks --------------------------------------------------------------
Write-Host "`n[3/4] hooks/"
$dossierHooks = Join-Path $Cible "hooks"
if (-not (Test-Path $dossierHooks)) { New-Item -ItemType Directory $dossierHooks | Out-Null }
foreach ($hook in Get-ChildItem (Join-Path $Source "hooks") -Filter *.py) {
    $dst = Join-Path $dossierHooks $hook.Name
    $identique = (Test-Path $dst) -and
                 ((Get-FileHash $hook.FullName).Hash -eq (Get-FileHash $dst).Hash)
    if ($identique) {
        Write-Host "      $($hook.Name) : a jour."
    } elseif ($Verifier) {
        Write-Host "      $($hook.Name) : DERIVE." -ForegroundColor Yellow
        $derive++
    } else {
        Copy-Item $hook.FullName $dst -Force
        Write-Host "      $($hook.Name) : deploye."
    }
}

# --- 4. settings.json : verification seule ---------------------------------
Write-Host "`n[4/4] settings.json (verification, aucune ecriture)"
$fichierSettings = Join-Path $Cible "settings.json"
if (-not (Test-Path $fichierSettings)) {
    Write-Host "      ABSENT : creer settings.json depuis settings.hooks.json." -ForegroundColor Red
    exit 2
}
$conf = Get-Content $fichierSettings -Raw | ConvertFrom-Json

# La verification couvre TOUS les evenements declares, pas seulement PreToolUse :
# un hook non verifie est un hook dont on ne sait pas s'il tourne (2026-08-18).
$attendus = @(
    @{ event = "PreToolUse";   matcher = "Edit|Write|NotebookEdit"; hook = "block_cloud_cache.py" },
    @{ event = "PreToolUse";   matcher = "Bash|PowerShell";         hook = "block_git_add_all.py" },
    @{ event = "PreToolUse";   matcher = "Bash|PowerShell";         hook = "block_cloud_cache.py" },
    @{ event = "SessionStart"; matcher = "";                        hook = "inject_lecons.py" },
    @{ event = "SessionStart"; matcher = "";                        hook = "journal_etat.py" },
    @{ event = "PostToolUse";  matcher = "Bash|PowerShell";         hook = "rappel_lecon.py" },
    @{ event = "PreCompact";   matcher = "";                        hook = "checkpoint_precompact.py" },
    @{ event = "UserPromptSubmit"; matcher = "";                    hook = "alerte_contexte.py" },
    @{ event = "UserPromptSubmit"; matcher = "";                    hook = "gate_modele.py" }
)
foreach ($a in $attendus) {
    $declares = $conf.hooks.($a.event) |
                ForEach-Object { $m = $_.matcher; $_.hooks | ForEach-Object { "$m => $($_.command)" } }
    $trouve = $declares | Where-Object { $_ -like "*$($a.matcher)*$($a.hook)*" }
    $etiquette = if ($a.matcher) { "$($a.event) $($a.matcher)" } else { $a.event }
    if ($trouve) {
        Write-Host "      OK      $etiquette -> $($a.hook)"
    } else {
        Write-Host "      MANQUE  $etiquette -> $($a.hook)" -ForegroundColor Red
        $derive++
    }
}

# Cle inconnue dans une entree de hook = desactivation SILENCIEUSE (incident du
# 2026-07-27 : une cle "if" faisait sauter block_git_add_all.py sur les appels
# PowerShell, sans le moindre message, JSON valide). On ne peut pas prouver ce
# qui ne s'execute pas : on refuse donc tout ce qui n'est pas documente.
$clesConnues = @("type", "command", "timeout")
foreach ($evenement in $conf.hooks.PSObject.Properties.Name) {
    foreach ($groupe in $conf.hooks.$evenement) {
        foreach ($h in $groupe.hooks) {
            $inconnues = $h.PSObject.Properties.Name | Where-Object { $clesConnues -notcontains $_ }
            if ($inconnues) {
                $ou = if ($groupe.matcher) { "$evenement '$($groupe.matcher)'" } else { $evenement }
                Write-Host "      CLE INCONNUE dans $ou : $($inconnues -join ', ')" -ForegroundColor Red
                Write-Host "        -> une cle non documentee peut desactiver le hook sans erreur."
                $derive++
            }
        }
    }
}

Write-Host ""
if ($derive -gt 0) {
    Write-Host "$derive ecart(s) - cf. settings.hooks.json pour le fragment a fusionner." -ForegroundColor Red
    exit 2
}
Write-Host "Conforme." -ForegroundColor Green
exit 0
