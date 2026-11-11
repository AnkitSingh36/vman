from uuid import uuid4


class APIError(Exception):
    def __init__(self, status, code, message, revision=None):
        self.status = status
        self.payload = {"code": code, "message": message, "request_id": uuid4().hex,
                        "retryable": status in (429, 503)}
        if revision is not None:
            self.payload["current_revision"] = revision
        super().__init__(message)


def conflict(revision):
    return APIError(409, "CONFLICT", "Refresh current state or reconcile the original command.", revision)
