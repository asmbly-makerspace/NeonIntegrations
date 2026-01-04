from unittest.mock import patch

import pytest
import requests_mock


@pytest.fixture(autouse=True)
def _no_network():
    with patch("socket.socket", side_effect=RuntimeError("Network disabled in tests")):
        yield


@pytest.fixture
def neon_api_mock():
    """
    Provide a requests_mock adapter for mocking NeonCRM API calls.

    This fixture allows tests to mock HTTP responses from the NeonCRM API
    without duplicating business logic. Use with neon_mocker module
    to build realistic API responses.

    Example:
        def test_something(neon_api_mock):
            from tests.neon_mocker import NeonMock

            builder = NeonMock(account_id=123)
            builder.add_regular_membership('2025-01-01', '2025-12-31', fee=100.0)

            neon_api_mock.get(
                'https://api.neoncrm.com/v2/accounts/123/memberships',
                json=builder.build()
            )

            # Now call code that uses neonUtil.appendMemberships()
    """
    with requests_mock.Mocker() as m:
        yield m



