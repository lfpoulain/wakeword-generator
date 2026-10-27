param(
    [ValidateSet('build', 'doctor', 'prepare', 'generate', 'augment', 'train', 'ecoute')]
    [string]$Etape = 'build',
    [switch]$Cpu,
    # Recette du mot : training.yml (Cornelius) par défaut, ou une autre, par exemple lumos.yml
    [string]$Config = 'training.yml'
)

$ErrorActionPreference = 'Stop'
$generator = $PSScriptRoot
$image = 'wakeword-fr-training'

Push-Location $generator
try {
    & docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) {
        & docker build -t $image '.'
        if ($LASTEXITCODE -ne 0) { throw "Construction de l'image Docker impossible." }
    }

    # Seul l'entraînement profite du GPU : les autres étapes tournent sur le processeur (la génération en parallèle).
    # Clips et caractéristiques dans un volume Docker : bien plus rapide que le dossier partagé
    # avec Windows. « ecoute » en copie quelques-uns dans output/<model_name>-ecoute/.
    $dockerArgs = @('run', '--rm', '--shm-size=8g', '-v', 'wakeword-travail:/travail', '-e', 'WAKEWORD_WORK=/travail')
    if (-not $Cpu -and $Etape -in @('build', 'train')) { $dockerArgs += @('--gpus', 'all') }
    $dockerArgs += @('-v', "${generator}:/workspace", '-w', '/workspace',
                     $image, '--config', $Config, $Etape)
    & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) { throw "L'étape $Etape a échoué." }

    if ($Etape -in @('build', 'train')) { Write-Host 'Modèle ONNX prêt dans output/.' }
} finally {
    Pop-Location
}
