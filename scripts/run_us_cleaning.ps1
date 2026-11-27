param(
    [string]$PythonExecutable = 'python'
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$runtimeDirectory = Join-Path $projectDirectory 'outputs/cleaning_runtime'
$env:JUPYTER_RUNTIME_DIR = Join-Path $runtimeDirectory 'jupyter'
$env:IPYTHONDIR = Join-Path $runtimeDirectory 'ipython'
$env:TEMP = Join-Path $runtimeDirectory 'temp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
foreach ($directory in @($env:JUPYTER_RUNTIME_DIR, $env:IPYTHONDIR, $env:TEMP)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}
# Use a project-local kernel spec so the selected interpreter actually executes the notebook.
$kernelDirectory = Join-Path $runtimeDirectory 'share/jupyter/kernels/7308-final-project'
New-Item -ItemType Directory -Force -Path $kernelDirectory | Out-Null
$pythonPath = (& $PythonExecutable -c 'import sys; print(sys.executable)')
if ($LASTEXITCODE -ne 0) { throw 'Cannot start the selected Python interpreter.' }
$kernelSpec = @{
    argv = @($pythonPath.Trim(), '-m', 'ipykernel_launcher', '-f', '{connection_file}')
    display_name = 'Python (7308-Final-project)'
    language = 'python'
}
$kernelJson = $kernelSpec | ConvertTo-Json -Depth 3
[IO.File]::WriteAllText((Join-Path $kernelDirectory 'kernel.json'), $kernelJson, [Text.UTF8Encoding]::new($false))
$kernelSearchPath = Join-Path $runtimeDirectory 'share/jupyter'
if ($env:JUPYTER_PATH) {
    $env:JUPYTER_PATH = $kernelSearchPath + [IO.Path]::PathSeparator + $env:JUPYTER_PATH
} else {
    $env:JUPYTER_PATH = $kernelSearchPath
}
& $PythonExecutable -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=7308-final-project --ExecutePreprocessor.timeout=1200 (Join-Path $projectDirectory 'notebooks/02_us_accidents_cleaning.ipynb')
if ($LASTEXITCODE -ne 0) {
    throw 'Notebook execution failed. Inspect its error before using the new run directory.'
}
