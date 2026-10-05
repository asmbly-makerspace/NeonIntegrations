import logging

from openPathUtil import deleteAllCredentialsForId, O_baseURL


ALTA_ID = 456


def test_delete_all_credentials_skips_malformed_credential(requests_mock, caplog):
    # A credential without an "id" is logged and skipped; the others are still deleted.
    requests_mock.get(
        f'{O_baseURL}/users/{ALTA_ID}/credentials',
        json={"data": [{"id": 1}, {"credentialType": {"name": "card"}}, {"id": 3}]},
    )
    delete_1 = requests_mock.delete(f'{O_baseURL}/users/{ALTA_ID}/credentials/1', status_code=204)
    delete_3 = requests_mock.delete(f'{O_baseURL}/users/{ALTA_ID}/credentials/3', status_code=204)

    with caplog.at_level(logging.WARNING):
        deleteAllCredentialsForId(ALTA_ID)

    assert delete_1.call_count == 1
    assert delete_3.call_count == 1
    assert f"Malformed credential in stale OpenPath user {ALTA_ID}" in caplog.text
