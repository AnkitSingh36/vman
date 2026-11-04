$ErrorActionPreference = 'Stop'
$contractRoot = $PSScriptRoot
$cases = 0

function Assert-Contract($Payload, [string]$SchemaName, [bool]$Expected = $true) {
    $raw = $Payload | ConvertTo-Json -Depth 100 -Compress
    $valid = Test-Json -Json $raw -SchemaFile (Join-Path $contractRoot $SchemaName) -ErrorAction SilentlyContinue
    if ([bool]$valid -ne $Expected) {
        throw "Contract check failed for $SchemaName (expected valid=$Expected): $raw"
    }
    $script:cases++
}

$fixtures = Get-Content -LiteralPath (Join-Path $contractRoot 'all-fixtures.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($session in $fixtures.sessions.Values) { Assert-Contract $session 'session.schema.json' }
foreach ($proposal in $fixtures.engine_proposals.Values) { Assert-Contract $proposal 'engine-proposal.schema.json' }
$requests = Get-Content -LiteralPath (Join-Path $contractRoot 'request-fixtures.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Contract $requests.catalog 'catalog.schema.json'
Assert-Contract $requests.identify_request 'engine-request.schema.json'
Assert-Contract $requests.next_check_request 'engine-request.schema.json'

function Copy-Data($Data) { return ($Data | ConvertTo-Json -Depth 100 | ConvertFrom-Json -AsHashtable) }
$bad = Copy-Data $fixtures.sessions.READY
$bad.current_check = $null
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.sessions.BLOCKED
$bad.current_check = $fixtures.sessions.READY.current_check
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.sessions.RECORD_PENDING
$bad.receipt.state = 'PERSISTED'
$bad.receipt.record_id = 'record-1'
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.sessions.COMPLETED
$bad.receipt.record_id = $null
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.sessions.READY
$bad.current_check.Remove('stop_conditions')
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.sessions.READY
$bad.current_check.Remove('guidance_valid_until')
Assert-Contract $bad 'session.schema.json' $false
$bad = Copy-Data $fixtures.engine_proposals.PROPOSE_CHECK
$bad.payload.instruction = 'Untrusted model instruction'
Assert-Contract $bad 'engine-proposal.schema.json' $false
$bad = Copy-Data $fixtures.engine_proposals.ASK_OBSERVATION
$bad.payload.Remove('check_id')
Assert-Contract $bad 'engine-proposal.schema.json' $false
$bad = Copy-Data $requests.next_check_request
$bad.confirmed_identity = $null
Assert-Contract $bad 'engine-request.schema.json' $false
$bad = Copy-Data $requests.identify_request
$bad.remaining_budgets.calls = 17
Assert-Contract $bad 'engine-request.schema.json' $false
$bad = Copy-Data $requests.catalog
$bad.checks[0].state = 'Withdrawn'
Assert-Contract $bad 'catalog.schema.json' $false

$api = Get-Content -LiteralPath (Join-Path $contractRoot 'public-api.openapi.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($errorFixture in $fixtures.errors.Values) {
    $valid = Test-Json -Json ($errorFixture | ConvertTo-Json -Depth 100) -Schema ($api.components.schemas.Error | ConvertTo-Json -Depth 100) -ErrorAction SilentlyContinue
    if (-not $valid) { throw 'Public error fixture failed.' }
    $script:cases++
}
$bodyFixtures = @{
    CreateSession = @{ workflow_id='demo-laptop-no-power'; symptom_code='NO_POWER' }
    IdentityCandidates = @{ expected_revision=0; manual_label='DEMO-LAPTOP' }
    ConfirmIdentity = @{ expected_revision=1; model_id='DEMO-LAPTOP'; configuration_id='DEMO-C1'; human_confirmed=$true }
    Observation = @{ expected_revision=4; check_id='DEMO-OBSERVE'; check_version='1'; observation_code='DEMO_INDICATOR'; value='ON'; human_confirmed=$true }
    Outcome = @{ expected_revision=6; human_reported_outcome='RESOLVED'; human_confirmed=$true }
    Stop = @{ expected_revision=4; reason_code='USER_STOP' }
    Hazard = @{ expected_revision=4; hazard_code='UNSURE' }
    ImageReceipt = @{ image_id='image-demo'; session_id='demo-session-1'; revision=1; status='STORED' }
}
foreach ($name in $bodyFixtures.Keys) {
    $schema = $api.components.schemas[$name] | ConvertTo-Json -Depth 100
    $valid = Test-Json -Json ($bodyFixtures[$name] | ConvertTo-Json -Depth 100) -Schema $schema -ErrorAction SilentlyContinue
    if (-not $valid) { throw "Public body fixture failed: $name" }
    $script:cases++
}
$invalidBody = @{ expected_revision=1 }
$valid = Test-Json -Json ($invalidBody | ConvertTo-Json) -Schema ($api.components.schemas.IdentityCandidates | ConvertTo-Json -Depth 100) -ErrorAction SilentlyContinue
if ($valid) { throw 'IdentityCandidates accepted no identity input.' }
$script:cases++

Write-Output "$cases schema fixture checks passed. This validates artifacts only, not runtime policy or product readiness."
