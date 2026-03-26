import os
import sys
import types

import pytest


collect_ignore = [
    "test.py",
    "test1.py",
    "test-gemini.py",
    "query_tests.py",
    "batch_tests.py",
]


def install_stub_google_genai():
    google_module = sys.modules.setdefault("google", types.ModuleType("google"))
    genai_module = types.ModuleType("google.genai")

    class DummyClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.models = types.SimpleNamespace(
                generate_content=lambda *args, **kwargs: None,
                list=lambda: [],
            )

    genai_module.Client = DummyClient
    google_module.genai = genai_module
    sys.modules["google.genai"] = genai_module


def install_stub_google_auth_stack():
    google_auth_module = sys.modules.setdefault(
        "google.auth", types.ModuleType("google.auth")
    )
    transport_module = sys.modules.setdefault(
        "google.auth.transport", types.ModuleType("google.auth.transport")
    )
    requests_module = types.ModuleType("google.auth.transport.requests")

    class DummyRequest:
        pass

    requests_module.Request = DummyRequest
    transport_module.requests = requests_module
    google_auth_module.transport = transport_module
    sys.modules["google.auth.transport.requests"] = requests_module

    oauth2_module = sys.modules.setdefault(
        "google.oauth2", types.ModuleType("google.oauth2")
    )
    credentials_module = types.ModuleType("google.oauth2.credentials")

    class DummyCredentials:
        valid = False
        expired = False
        refresh_token = None

        @classmethod
        def from_authorized_user_file(cls, *args, **kwargs):
            return cls()

        def refresh(self, request):
            return None

        def to_json(self):
            return "{}"

    credentials_module.Credentials = DummyCredentials
    oauth2_module.credentials = credentials_module
    sys.modules["google.oauth2.credentials"] = credentials_module

    oauthlib_module = types.ModuleType("google_auth_oauthlib")
    flow_module = types.ModuleType("google_auth_oauthlib.flow")

    class DummyInstalledAppFlow:
        @classmethod
        def from_client_secrets_file(cls, *args, **kwargs):
            return cls()

        def run_local_server(self, **kwargs):
            return DummyCredentials()

        def run_console(self, **kwargs):
            return DummyCredentials()

    flow_module.InstalledAppFlow = DummyInstalledAppFlow
    oauthlib_module.flow = flow_module
    sys.modules["google_auth_oauthlib"] = oauthlib_module
    sys.modules["google_auth_oauthlib.flow"] = flow_module

    discovery_module = types.ModuleType("googleapiclient.discovery")
    discovery_module.build = lambda *args, **kwargs: object()
    sys.modules["googleapiclient.discovery"] = discovery_module

    errors_module = types.ModuleType("googleapiclient.errors")

    class DummyHttpError(Exception):
        def __init__(self, resp=None, content=None):
            self.resp = resp
            self.content = content
            super().__init__(content or "http error")

    errors_module.HttpError = DummyHttpError
    sys.modules["googleapiclient.errors"] = errors_module


def install_stub_psycopg2():
    psycopg2_module = types.ModuleType("psycopg2")

    class OperationalError(Exception):
        pass

    psycopg2_module.OperationalError = OperationalError
    psycopg2_module.connect = lambda *args, **kwargs: None
    sys.modules["psycopg2"] = psycopg2_module


def install_stub_optional_heavy_modules():
    bs4_module = types.ModuleType("bs4")

    class DummySoup:
        def __init__(self, html, parser):
            self.html = html

        def get_text(self, separator="\n", strip=True):
            return self.html

    bs4_module.BeautifulSoup = DummySoup
    sys.modules["bs4"] = bs4_module

    pil_module = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")
    pil_module.Image = image_module
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = image_module

    numpy_module = types.ModuleType("numpy")
    numpy_module.argsort = lambda values: sorted(
        range(len(values)), key=lambda i: values[i]
    )
    numpy_module.vstack = lambda rows: rows
    numpy_module.save = lambda *args, **kwargs: None
    numpy_module.load = lambda *args, **kwargs: []
    sys.modules["numpy"] = numpy_module

    pytesseract_module = types.ModuleType("pytesseract")
    sys.modules["pytesseract"] = pytesseract_module


def pytest_configure():
    os.environ.setdefault("GOOGLE_API_KEY", "test-key")
    os.environ.setdefault("EMAIL_EXTRACTION_MODEL", "test-model")
    install_stub_google_genai()
    install_stub_google_auth_stack()
    install_stub_psycopg2()
    install_stub_optional_heavy_modules()


@pytest.fixture
def scenario_printer():
    def _print(name, simulated_error, expected_behavior, actual_behavior):
        print(f"\nSCENARIO: {name}")
        print(f"SIMULATED ERROR: {simulated_error}")
        print(f"EXPECTED BEHAVIOR: {expected_behavior}")
        print(f"ACTUAL BEHAVIOR: {actual_behavior}")

    return _print
