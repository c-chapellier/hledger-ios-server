import gzip
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute


class GzipRequest(Request):
    """Custom Request class that decompresses gzip-encoded request bodies."""

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = await super().body()
            if "gzip" in self.headers.getlist("Content-Encoding"):
                body = gzip.decompress(body)
            self._body = body
        return self._body


class GzipRoute(APIRoute):
    """Custom APIRoute class that uses GzipRequest to handle gzip-compressed requests."""

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = GzipRequest(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler
