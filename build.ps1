param(
    [ValidateSet('build', 'doctor', 'prepare', 'generate', 'augment', 'train')]
    [string]$Etape = 'build',
    [switch]$Cpu
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

    # Seul l'entraînement profite du GPU : les autres étapes tournent sur le processeur.
    $dockerArgs = @('run', '--rm', '--shm-size=8g')
    if (-not $Cpu -and $Etape -in @('build', 'train')) { $dockerArgs += @('--gpus', 'all') }
    $dockerArgs += @('-v', "${generator}:/workspace", '-w', '/workspace',
                     $image, '--config', 'training.yml', $Etape)
    & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) { throw "L'étape $Etape a échoué." }

    if ($Etape -in @('build', 'train')) { Write-Host 'Modèle ONNX prêt dans output/.' }
} finally {
    Pop-Location
}
