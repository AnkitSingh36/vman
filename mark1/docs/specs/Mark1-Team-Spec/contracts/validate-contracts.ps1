$ErrorActionPreference = 'Stop'
# Install validation-requirements.txt in an isolated Python environment first.
& python (Join-Path $PSScriptRoot 'validate-contracts.py')
if ($LASTEXITCODE -ne 0) { throw 'Contract artifact validation failed.' }
& python (Join-Path $PSScriptRoot 'validate-hashes.py')
if ($LASTEXITCODE -ne 0) { throw 'Canonical hash validation failed.' }
