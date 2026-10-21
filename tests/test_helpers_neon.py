"""
Unit tests for helpers/neon.py
"""

import requests

import helpers.neon as neon
from neonUtil import N_baseURL


def _response(requests_mock, **kwargs):
    requests_mock.patch(f'{N_baseURL}/accounts/1', **kwargs)
    return requests.patch(f'{N_baseURL}/accounts/1')


def test_neon_error_summary_joins_error_list(requests_mock):
    response = _response(requests_mock, status_code=400, json=[
        {"code": "400", "message": "Invalid date of birth"},
        {"code": "400", "message": "Another problem"},
    ])
    assert neon.neonErrorSummary(response) == "400: Invalid date of birth; 400: Another problem"


def test_neon_error_summary_handles_single_error_object(requests_mock):
    response = _response(requests_mock, status_code=400, json={"code": "400", "message": "Bad"})
    assert neon.neonErrorSummary(response) == "400: Bad"


def test_neon_error_summary_falls_back_to_text_and_truncates(requests_mock):
    response = _response(requests_mock, status_code=502, text="Bad\n\tGateway " + "x" * 500)
    summary = neon.neonErrorSummary(response, limit=20)
    assert summary == "Bad Gateway xxxxxxxx..."


def test_neon_error_summary_falls_back_to_text_for_other_json(requests_mock):
    response = _response(requests_mock, status_code=500, json={"status": "error"})
    assert neon.neonErrorSummary(response) == '{"status": "error"}'


def test_neon_error_summary_handles_empty_body(requests_mock):
    response = _response(requests_mock, status_code=500, text="")
    assert neon.neonErrorSummary(response) == "(empty response body)"


def test_get_event_registrants_single_page_without_pagination(requests_mock):
    url = f'{N_baseURL}/events/5/eventRegistrations'
    mock = requests_mock.get(url, json={"eventRegistrations": [{"registrantAccountId": 1}]})

    result = neon.getEventRegistrants(5)

    assert result["eventRegistrations"] == [{"registrantAccountId": 1}]
    assert mock.call_count == 1


def test_get_event_registrants_follows_every_page(requests_mock):
    url = f'{N_baseURL}/events/5/eventRegistrations'
    for page in range(3):
        requests_mock.get(f'{url}?currentPage={page}', json={
            "eventRegistrations": [{"registrantAccountId": page}],
            "pagination": {"currentPage": page, "pageSize": 30, "totalPages": 3},
        })

    result = neon.getEventRegistrants(5)

    assert [r["registrantAccountId"] for r in result["eventRegistrations"]] == [0, 1, 2]
    assert len(requests_mock.request_history) == 3


def test_get_event_registrants_keeps_none_when_no_registrations(requests_mock):
    url = f'{N_baseURL}/events/5/eventRegistrations'
    requests_mock.get(url, json={
        "eventRegistrations": None,
        "pagination": {"currentPage": 0, "pageSize": 30, "totalPages": 0},
    })

    assert neon.getEventRegistrants(5)["eventRegistrations"] is None
