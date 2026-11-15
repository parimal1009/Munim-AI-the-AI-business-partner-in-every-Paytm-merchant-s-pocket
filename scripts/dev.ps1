# Usage:  ./scripts/dev.ps1 <command>
#   setup | api | web | seed | test | lint | typecheck
param([Parameter(Mandatory = $true)][ValidateSet("setup", "api", "web", "seed", "test", "lint", "typecheck")][string]$Cmd)

$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

switch ($Cmd) {
  "setup" {
    python -m venv "$root\backend\.venv"
    & $py -m pip install -r "$root\backend\requirements.txt"
    Push-Location "$root\frontend"; npm install; Pop-Location
  }
  "api"       { Push-Location "$root\backend"; & $py -m uvicorn app.main:app --reload --port 8000; Pop-Location }
  "web"       { Push-Location "$root\frontend"; npm run dev; Pop-Location }
  "seed"      { Push-Location "$root\backend"; & $py -m app.seed; Pop-Location }
  "test"      { Push-Location "$root\backend"; & $py -m pytest -q; Pop-Location }
  "lint"      { Push-Location "$root\backend"; & $py -m ruff check .; Pop-Location }
  "typecheck" { Push-Location "$root\frontend"; npm run typecheck; Pop-Location }
}
