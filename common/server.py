from concurrent import futures
import logging
import os
from urllib.parse import unquote

import grpc

from common import peers
from common.records import FestHubError

PORT = int(os.getenv("BUSINESS_PORT", "50051"))
# the address to listen on and the API gateway's address; docker-compose.yml sets these to the containers'
# fixed IPs, and the defaults keep a server run outside Docker local to this machine
BIND_ADDRESS = os.getenv("BIND_ADDRESS", "127.0.0.1")
GATEWAY_IP = os.getenv("GATEWAY_IP", "127.0.0.1")
PEER_IPS = [ip.strip() for ip in os.getenv("PEER_IPS", "").split(",") if ip.strip()]
WORKERS = int(os.getenv("GRPC_WORKERS", "10"))


def field(record, name, default=None):
    """Read a field from a database namedtuple, object, or dictionary."""
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def string_id(value):
    return "" if value is None else str(value)


def abort_for_error(context, error):
    """Map known service errors to useful gRPC status codes.

    FestHubError is the application's business-rule exception. Unexpected exceptions
    are logged server-side and returned without leaking internal details.
    """
    message = str(error)
    lowered = message.lower()

    if isinstance(error, FestHubError):
        if error.code is not None:
            code = error.code
        elif lowered.startswith("no ") and " with id " in lowered:
            code = grpc.StatusCode.NOT_FOUND
        elif any(phrase in lowered for phrase in (
            "already exists", "already booked", "already in this category",
        )):
            code = grpc.StatusCode.ALREADY_EXISTS
        else:
            code = grpc.StatusCode.INVALID_ARGUMENT
        context.abort(code, message)

    if isinstance(error, (ValueError, TypeError)):
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
    if isinstance(error, LookupError):
        context.abort(grpc.StatusCode.NOT_FOUND, message)

    logging.exception("Unhandled error in gRPC request", exc_info=(type(error), error, error.__traceback__))
    context.abort(grpc.StatusCode.INTERNAL, "Internal server error")


def invoke(context, function, *args, **kwargs):
    try:
        with peers.handling(context):
            return function(*args, **kwargs)
    except Exception as error:
        abort_for_error(context, error)


def peer_ip(peer):
    """Pull the IP out of context.peer(), e.g. "ipv4:172.30.83.10:41234" or "ipv6:%5B::1%5D:41234"."""
    return unquote(peer.partition(":")[2]).rpartition(":")[0].strip("[]")


class GatewayAndPeersOnly(grpc.ServerInterceptor):
    """Refuse every call that doesn't come from the API gateway or from one of PEER_IPS."""

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None
        allowed = {GATEWAY_IP, *PEER_IPS}

        def guarded(request, context):
            caller = peer_ip(context.peer())
            if caller not in allowed:
                logging.warning("Rejected gRPC call %s from %s", handler_call_details.method, caller)
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "calls to this service must go through the API gateway")
            return handler.unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            guarded,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


def serve(name, *servicers):
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=WORKERS), interceptors=[GatewayAndPeersOnly()])
    for add_to_server, servicer in servicers:
        add_to_server(servicer, server)
    bound_port = server.add_insecure_port(f"{BIND_ADDRESS}:{PORT}")
    if bound_port == 0:
        raise RuntimeError(f"Could not bind gRPC server to {BIND_ADDRESS}:{PORT}")
    server.start()
    logging.info("%s gRPC server listening on %s:%s, accepting calls only from %s",
                 name, BIND_ADDRESS, PORT, ", ".join([GATEWAY_IP, *PEER_IPS]))
    server.wait_for_termination()
