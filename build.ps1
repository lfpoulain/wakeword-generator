param(
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

    $dockerArgs = @('run', '--rm', '--shm-size=8g')
    if (-not $Cpu) { $dockerArgs += @('--gpus', 'all') }
    $dockerArgs += @('-v', "${generator}:/workspace", '-w', '/workspace',
                     $image, '--config', 'training.yml', 'build')
    & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) { throw "La génération du mot d'appel a échoué." }

    Write-Host 'Modèle ONNX prêt dans output/.'
} finally {
    Pop-Location
}
