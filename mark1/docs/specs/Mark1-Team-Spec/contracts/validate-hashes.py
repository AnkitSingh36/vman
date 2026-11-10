"""Validate canonical hash golden fixtures and catalog-schema equivalence."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
fields = (
    'mode', 'workflow_id', 'confirmed_identity', 'manual_label',
    'cleared_images', 'approved_catalog', 'observations', 'completed_check_ids',
    'catalog_version', 'prompt_version', 'model_config_version', 'investigation_context',
)

def canonical_context(request):
    return json.dumps(
        {key: request[key] for key in fields}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True, allow_nan=False,
    )

def main():
    requests = json.loads((root / 'request-fixtures.json').read_text())
    golden = json.loads((root / 'hash-golden.json').read_text())
    for name in ('identify_request', 'investigate_request'):
        canonical = canonical_context(requests[name])
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        assert canonical == golden[name]['canonical_json'], name
        assert digest == golden[name]['sha256'] == requests[name]['context_hash'], name
    catalog = json.loads((root / 'catalog.schema.json').read_text())
    engine = json.loads((root / 'engine-request.schema.json').read_text())
    assert catalog == engine['properties']['approved_catalog'], 'Embedded catalog schema drift'
    print('Two v2 canonical-hash golden fixtures and catalog-schema equivalence passed.')

if __name__ == '__main__':
    main()
