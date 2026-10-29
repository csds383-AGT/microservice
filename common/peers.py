import os
from contextlib import contextmanager
from contextvars import ContextVar

import grpc

from common.records import FestHubError

TIMEOUT_SECONDS = float(os.getenv("GRPC_TIMEOUT_SECONDS", "3"))
# lets calls to other services share the deadline of the request being handled
incoming = ContextVar("incoming_request", default=None)


def stub(stub_class, service):
    host = os.getenv(f"{service}_HOST", "localhost")
    port = os.getenv(f"{service}_PORT", "50051")
    return stub_class(grpc.insecure_channel(f"{host}:{port}"))


@contextmanager
def handling(context):
    token = incoming.set(context)
    try:
        yield
    finally:
        incoming.reset(token)


def call(method, request):
    context = incoming.get()
    remaining = context.time_remaining() if context is not None else None
    try:
        return method(request, timeout=TIMEOUT_SECONDS if remaining is None else remaining)
    except grpc.RpcError as error:
        raise FestHubError(error.details() or error.code().name.lower(), code=error.code()) from error
