import re
import uuid

from .context import request_id_var

_SAFE_ID = re.compile(r"^[A-Za-z0-9._\-]{8,64}$")


class RequestIDMiddleware:
    """Attach a correlation id to every request/response/log line.

    An incoming X-Request-ID is reused only if it looks safe; otherwise we mint one,
    so clients cannot inject junk into logs.
    """

    header = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(self.header, "")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[self.header] = rid
        return response
