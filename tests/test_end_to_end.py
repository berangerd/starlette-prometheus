import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from starlette_prometheus import PrometheusMiddleware, metrics


class TestCasePrometheusMiddleware:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette()
        app_.add_middleware(PrometheusMiddleware)
        app_.add_route("/metrics/", metrics)

        @app_.route("/foo/")
        def foo(request):
            return PlainTextResponse("Foo")

        @app_.route("/bar/")
        def bar(request):
            raise ValueError("bar")

        @app_.route("/foo/{bar}/")
        def foobar(request):
            return PlainTextResponse(f"Foo: {request.path_params['bar']}")

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_view_ok(self, client):
        # Do a request
        client.get("/foo/")

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: Requests
        assert 'starlette_requests_total{method="GET",path_template="/foo/"} 1.0' in metrics_text

        # Asserts: Responses
        assert 'starlette_responses_total{method="GET",path_template="/foo/",status_code="200"} 1.0' in metrics_text

        # Asserts: Requests in progress
        assert 'starlette_requests_in_progress{method="GET",path_template="/foo/"} 0.0' in metrics_text
        assert 'starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text

    def test_view_exception(self, client):
        # Do a request
        with pytest.raises(ValueError):
            client.get("/bar/")

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: Requests
        assert 'starlette_requests_total{method="GET",path_template="/bar/"} 1.0' in metrics_text

        # Asserts: Responses
        assert (
            "starlette_exceptions_total{"
            'exception_type="ValueError",method="GET",path_template="/bar/"'
            "} 1.0" in metrics_text
        )

        # Asserts: Requests in progress
        assert 'starlette_requests_in_progress{method="GET",path_template="/bar/"} 0.0' in metrics_text
        assert 'starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text

    def test_path_substituion(self, client):
        # Do a request
        client.get("/foo/baz/")

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: Requests
        assert 'starlette_requests_total{method="GET",path_template="/foo/{bar}/"} 1.0' in metrics_text

        # Asserts: Responses
        assert (
            'starlette_responses_total{method="GET",path_template="/foo/{bar}/",status_code="200"} 1.0' in metrics_text
        )

        # Asserts: Requests in progress
        assert 'starlette_requests_in_progress{method="GET",path_template="/foo/{bar}/"} 0.0' in metrics_text
        assert 'starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text

    def test_unhandled_paths(self, client):
        # Do a request
        client.get("/any/unhandled/path")

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: Requests
        assert 'starlette_requests_total{method="GET",path_template="/any/unhandled/path"} 1.0' in metrics_text

        # Asserts: Responses
        assert (
            'starlette_responses_total{method="GET",path_template="/any/unhandled/path",status_code="404"} 1.0'
            in metrics_text
        )

        # Asserts: Requests in progress
        assert 'starlette_requests_in_progress{method="GET",path_template="/any/unhandled/path"} 0.0' in metrics_text
        assert 'starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text


class TestCasePrometheusMiddlewareFilterUnhandledPaths:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette()
        app_.add_middleware(PrometheusMiddleware, filter_unhandled_paths=True)
        app_.add_route("/metrics/", metrics)

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_filter_unhandled_paths(self, client):
        # Do a request
        path = "/other/unhandled/path"
        client.get(path)

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: metric is filtered
        assert path not in metrics_text

        # Asserts: Requests in progress
        assert 'starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text


class TestCasePrometheusMiddlewareWithPrefix:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Starlette()
        app_.add_middleware(PrometheusMiddleware, prefix="test_")
        app_.add_route("/metrics/", metrics)

        @app_.route("/foo/")
        def foo(request):
            return PlainTextResponse("Foo")

        return app_

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_view_ok_with_prefix(self, client):
        # Do a request
        client.get("/foo/")

        # Get metrics
        response = client.get("/metrics/")
        metrics_text = response.content.decode()

        # Asserts: Requests
        assert 'test_starlette_requests_total{method="GET",path_template="/foo/"} 1.0' in metrics_text

        # Asserts: Responses
        assert (
            'test_starlette_responses_total{method="GET",path_template="/foo/",status_code="200"} 1.0' in metrics_text
        )

        # Asserts: Requests in progress
        assert 'test_starlette_requests_in_progress{method="GET",path_template="/foo/"} 0.0' in metrics_text
        assert 'test_starlette_requests_in_progress{method="GET",path_template="/metrics/"} 1.0' in metrics_text
