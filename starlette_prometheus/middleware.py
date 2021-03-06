import time
from typing import Tuple

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, filter_unhandled_paths: bool = False, prefix: str = "") -> None:
        super().__init__(app)
        self.filter_unhandled_paths = filter_unhandled_paths

        self.requests = Counter(
            prefix + "starlette_requests_total",
            "Total count of requests by method and path.",
            ["method", "path_template"],
        )
        self.responses = Counter(
            prefix + "starlette_responses_total",
            "Total count of responses by method, path and status codes.",
            ["method", "path_template", "status_code"],
        )
        self.requests_processing_time = Histogram(
            prefix + "starlette_requests_processing_time_seconds",
            "Histogram of requests processing time by path (in seconds)",
            ["method", "path_template"],
        )
        self.exceptions = Counter(
            prefix + "starlette_exceptions_total",
            "Total count of exceptions raised by path and exception type",
            ["method", "path_template", "exception_type"],
        )
        self.requests_in_progress = Gauge(
            prefix + "starlette_requests_in_progress",
            "Gauge of requests by method and path currently being processed",
            ["method", "path_template"],
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path_template, is_handled_path = self.get_path_template(request)

        if self._is_path_filtered(is_handled_path):
            return await call_next(request)

        self.requests_in_progress.labels(method=method, path_template=path_template).inc()
        self.requests.labels(method=method, path_template=path_template).inc()
        try:
            before_time = time.perf_counter()
            response = await call_next(request)
            after_time = time.perf_counter()
        except Exception as e:
            self.exceptions.labels(method=method, path_template=path_template, exception_type=type(e).__name__).inc()
            raise e from None
        else:
            self.requests_processing_time.labels(method=method, path_template=path_template).observe(
                after_time - before_time
            )
            self.responses.labels(method=method, path_template=path_template, status_code=response.status_code).inc()
        finally:
            self.requests_in_progress.labels(method=method, path_template=path_template).dec()

        return response

    @staticmethod
    def get_path_template(request: Request) -> Tuple[str, bool]:
        for route in request.app.routes:
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                return route.path, True

        return request.url.path, False

    def _is_path_filtered(self, is_handled_path: bool) -> bool:
        return self.filter_unhandled_paths and not is_handled_path
