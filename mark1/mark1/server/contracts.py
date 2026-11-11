"""One canonical schema source, registered locally with network retrieval disabled."""
import hashlib
import json
import copy

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .errors import APIError

HASH_FIELDS = ("mode", "workflow_id", "confirmed_identity", "manual_label", "cleared_images",
               "approved_catalog", "observations", "completed_check_ids", "catalog_version",
               "prompt_version", "model_config_version", "investigation_context")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class Contracts:
    def __init__(self, directory):
        self.directory = directory
        self.api = self.read("public-api.openapi.json")
        resources = []
        for path in directory.glob("*.schema.json"):
            schema = self.read(path.name)
            Draft202012Validator.check_schema(schema)
            resources.append((schema["$id"], Resource.from_contents(schema)))
        self.base = "https://schemas.mark1.invalid/v2/"
        self.api_uri = self.base + "public-api.openapi.json"
        resources.append((self.api_uri, Resource.from_contents(self.api, default_specification=DRAFT202012)))
        registry = Registry().with_resources(resources)
        self.validators = {}
        names = [(p.name, self.base + p.name) for p in directory.glob("*.schema.json")]
        names += [(name, self.api_uri + "#/components/schemas/" + name)
                  for name in self.api["components"]["schemas"]]
        for name, uri in names:
            self.validators[name] = Draft202012Validator(
                {"$ref": uri}, registry=registry, format_checker=FormatChecker())

    def read(self, name):
        return json.loads((self.directory / name).read_text(encoding="utf-8"))

    def validate(self, name, data, *, internal=False):
        if not self.validators[name].is_valid(data):
            if internal:
                raise ValueError("Invalid internal contract: " + name)
            raise APIError(422, "INVALID_REQUEST", "Request does not match the published contract.")

    @staticmethod
    def context_hash(request):
        return digest({key: request[key] for key in HASH_FIELDS})

    def bundled_api(self):
        """Swagger UI gets the canonical API with local schema references expanded."""
        def expand(value, document):
            if isinstance(value, list):
                return [expand(v, document) for v in value]
            if not isinstance(value, dict):
                return value
            if "$ref" in value:
                file, _, pointer = value["$ref"].partition("#")
                target_document = self.read(file) if file else document
                target = target_document
                for key in pointer.strip("/").split("/") if pointer else []:
                    target = target[key.replace("~1", "/").replace("~0", "~")]
                resolved = expand(target, target_document)
                siblings = {k: v for k, v in value.items() if k != "$ref"}
                return {"allOf": [resolved, expand(siblings, document)]} if siblings else resolved
            return {k: expand(v, document) for k, v in value.items() if k not in ("$id", "$schema")}
        return expand(copy.deepcopy(self.api), self.api)
