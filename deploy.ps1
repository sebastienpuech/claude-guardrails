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

# --- Sauvegarde avant ecrasement -------------------------------------------
# Incident du 21/08/2026 : ce script a ecrase deux hooks dont le travail n'etait
# pas commite ; il a fallu les reconstituer a la main dans les transcripts. Une
# cible qui differe de la source contient peut-etre du travail qui n'existe nulle
# part ailleurs. On ne l'ecrase plus sans en garder une copie horodatee.
$Sauvegardes = Join-Path $Cible ".sauvegardes\deploiements"
function Sauvegarder-Avant-Ecrasement {
    param([string]$Fichier)
    if (-not (Test-Path $Fichier)) { return }
    $horodatage = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $dossier = Join-Path $Sauvegardes $horodatage
    if (-not (Test-Path $dossier)) { New-Item -ItemType Directory $dossier -Force | Out-Null }
    Copy-Item $Fichier (Join-Path $dossier (Split-Path $Fichier -Leaf)) -Force
    Write-Host "      sauvegarde : .sauvegardes\deploiements\$horodatage\$(Split-Path $Fichier -Leaf)" -ForegroundColor DarkGray
}

Write-Host "Source : $Source"
Write-Host "Cible  : $Cible`n"

# --- 1. Goldens verts avant tout deploiement -------------------------------
# Les DEUX suites : les hooks Claude Code, et les garde-fous git (etage 2, ajoute
# le 25/08 apres la red team). Deployer avec l'une des deux rouge reviendrait a
# propager une regression sur la machine.
Write-Host "[1/7] Tests de contournement..."
foreach ($suite in @("tests\test_hooks.py", "tests\test_garde_fous_git.py")) {
    & python (Join-Path $Source $suite) | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REFUS : $suite est rouge. Rien n'est deploye." -ForegroundColor Red
        Write-Host "        Relancer : python $suite"
        exit 2
    }
    Write-Host "      $suite : vert."
}
Write-Host ""

# --- 2. CLAUDE.md ----------------------------------------------------------
# Source nommee CLAUDE-global.md pour ne PAS etre auto-chargee comme memoire de
# sous-dossier quand on travaille dans ce repo. Deployee sous son nom canonique.
Write-Host "[2/7] CLAUDE-global.md -> ~/.claude/CLAUDE.md"
$src = Join-Path $Source "CLAUDE-global.md"
$dst = Join-Path $Cible  "CLAUDE.md"
# Fail-closed, pas fail-crash. La source peut manquer (extrait public filtre, copie
# partielle) : on le dit et on passe, au lieu de laisser Get-FileHash lever une
# exception PowerShell brute au milieu d'un deploiement a moitie fait.
if (-not (Test-Path $src)) {
    Write-Host "      ABSENT : $src introuvable, etape ignoree." -ForegroundColor Yellow
    Write-Host "      (attendu dans l'extrait public : la doctrine n'y est pas publiee)"
    $derive++
} else {
$identique = (Test-Path $dst) -and
             ((Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash)
if ($identique) {
    Write-Host "      a jour."
} elseif ($Verifier) {
    Write-Host "      DERIVE : le deploye differe de la source." -ForegroundColor Yellow
    $derive++
} else {
    Sauvegarder-Avant-Ecrasement $dst
    Copy-Item $src $dst -Force
    Write-Host "      deploye."
}
}

# --- 3. hooks --------------------------------------------------------------
Write-Host "`n[3/7] hooks/"
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
        Sauvegarder-Avant-Ecrasement $dst
        Copy-Item $hook.FullName $dst -Force
        Write-Host "      $($hook.Name) : deploye."
    }
}

# --- 4. output-styles/ : le style de sortie --------------------------------
# Ajoute le 2026-08-28. Un output style modifie le SYSTEM PROMPT, la ou CLAUDE.md
# n'est qu'un message utilisateur pose apres : c'est pour ca que la regle
# "pyramide inversee", presente dans CLAUDE.md depuis des semaines, se diluait en
# fin de session. Claude Code re-rappelle le style en cours de conversation, ce
# qu'aucun CLAUDE.md ne fait.
# Le fichier est actif seulement si settings.json porte "outputStyle": "<nom>" ;
# ce script ne l'ecrit pas (cf. etape 7), il se contente de le verifier.
Write-Host "`n[4/7] output-styles/ -> ~/.claude/output-styles/"
$dossierStyles = Join-Path $Cible "output-styles"
if (-not (Test-Path $dossierStyles)) { New-Item -ItemType Directory $dossierStyles | Out-Null }
foreach ($style in Get-ChildItem (Join-Path $Source "output-styles") -Filter *.md) {
    $dst = Join-Path $dossierStyles $style.Name
    $identique = (Test-Path $dst) -and
                 ((Get-FileHash $style.FullName).Hash -eq (Get-FileHash $dst).Hash)
    if ($identique) {
        Write-Host "      $($style.Name) : a jour."
    } elseif ($Verifier) {
        Write-Host "      $($style.Name) : DERIVE." -ForegroundColor Yellow
        $derive++
    } else {
        Sauvegarder-Avant-Ecrasement $dst
        Copy-Item $style.FullName $dst -Force
        Write-Host "      $($style.Name) : deploye."
    }
}
# Un style deploye mais non selectionne ne s'applique jamais : l'ecart est muet
# cote Claude Code, donc il se signale ici.
$styleActif = $null
$fichierReglages = Join-Path $Cible "settings.json"
if (Test-Path $fichierReglages) {
    $styleActif = (Get-Content $fichierReglages -Raw | ConvertFrom-Json).outputStyle
}
if ($styleActif) {
    Write-Host "      settings.json : outputStyle = '$styleActif'."
} else {
    Write-Host "      settings.json : AUCUN outputStyle declare - le style ne s'applique pas." -ForegroundColor Yellow
    $derive++
}

# --- 5. githooks/ : les shims git globaux ----------------------------------
# Ajoute le 2026-08-25. Ces shims etaient installes A LA MAIN depuis le 21/08 :
# le script ne les deployait pas et `-Verifier` ne signalait pas leur absence.
# Un garde-fou qui ne survit qu'a une copie manuelle est decoratif — c'est
# exactement le trou par lequel `pre-merge-commit` aurait disparu au premier
# redeploiement, et n'aurait jamais existe sur une autre machine.
#
# Liste EXPLICITE, et non un `*` : githooks/ contient aussi des hooks propres a
# CE depot (`pre-commit-local`), qui vont dans .git/hooks/ et n'ont rien
# a faire dans la couche globale. Le controle d'exhaustivite juste apres empeche
# la liste de se perimer en silence.
Write-Host "`n[5/7] githooks/ -> ~/.claude/githooks/ (shims globaux)"
$Shims = @("pre-commit", "post-commit", "pre-merge-commit")
$dossierShims = Join-Path $Cible "githooks"
if (-not (Test-Path $dossierShims)) { New-Item -ItemType Directory $dossierShims | Out-Null }
foreach ($nom in $Shims) {
    $src = Join-Path $Source "githooks\$nom"
    if (-not (Test-Path $src)) {
        Write-Host "      $nom : ABSENT DE LA SOURCE." -ForegroundColor Red
        $derive++
        continue
    }
    $dst = Join-Path $dossierShims $nom
    $identique = (Test-Path $dst) -and
                 ((Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash)
    if ($identique) {
        Write-Host "      $nom : a jour."
    } elseif ($Verifier) {
        Write-Host "      $nom : DERIVE." -ForegroundColor Yellow
        $derive++
    } else {
        Sauvegarder-Avant-Ecrasement $dst
        Copy-Item $src $dst -Force
        Write-Host "      $nom : deploye."
    }
}
# Exhaustivite : tout fichier de githooks/ qui n'est ni un shim global connu, ni
# un hook clairement propre a un depot (suffixe `-<nom du depot>`), est signale.
# Sans ce controle, ajouter un shim et oublier de l'inscrire ici le rendrait
# invisible — le defaut qu'on vient de corriger se reformerait tout seul.
foreach ($f in Get-ChildItem (Join-Path $Source "githooks") -File) {
    if ($Shims -contains $f.Name) { continue }
    if ($f.Name -like "*-*" -and ($Shims | Where-Object { $f.Name -like "$_-*" })) { continue }
    Write-Host "      NON DEPLOYE : githooks\$($f.Name) n'est dans aucune categorie." -ForegroundColor Yellow
    Write-Host "        -> l'ajouter a `$Shims, ou le nommer <shim>-<depot> s'il est local."
    $derive++
}

# --- 5. core.hooksPath : sans lui, les shims ne sont jamais appeles ---------
# Un shim parfaitement deploye mais non branche ne s'execute jamais. On verifie
# donc le branchement, pas seulement la presence du fichier.
Write-Host "`n[6/7] git config --global core.hooksPath"
$hooksPath = (& git config --global core.hooksPath) 2>$null
$attenduPath = ($dossierShims -replace '\\', '/')
if (-not $hooksPath) {
    Write-Host "      NON DEFINI : les shims ne seront jamais appeles." -ForegroundColor Red
    Write-Host "        -> git config --global core.hooksPath `"$attenduPath`""
    $derive++
} elseif (($hooksPath -replace '\\', '/').TrimEnd('/') -ne $attenduPath.TrimEnd('/')) {
    Write-Host "      POINTE AILLEURS : $hooksPath" -ForegroundColor Red
    Write-Host "        -> attendu : $attenduPath"
    $derive++
} else {
    Write-Host "      OK      $hooksPath"
}

# --- 7. settings.json : verification seule ---------------------------------
Write-Host "`n[7/7] settings.json (verification, aucune ecriture)"
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
    @{ event = "SessionStart"; matcher = "";                        hook = "alerte_parc.py" },
    @{ event = "PostToolUse";  matcher = "Bash|PowerShell";         hook = "rappel_lecon.py" },
    @{ event = "PreCompact";   matcher = "";                        hook = "checkpoint_precompact.py" },
    @{ event = "UserPromptSubmit"; matcher = "";                    hook = "alerte_contexte.py" },
    @{ event = "UserPromptSubmit"; matcher = "";                    hook = "gate_modele.py" },
    @{ event = "Stop";             matcher = "";                    hook = "autosauvegarde_config.py" }
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
