from unittest import mock

from husky_directory.models.pws import ListPersonsOutput
from husky_directory.services.pws import PersonWebServiceClient


def test_get_index(client):
    assert client.get("/").status_code == 200


def test_get_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["ready"] is False


def test_get_ready(client):
    response = client.get("/health?ready")
    assert response.status_code == 200
    assert response.json["ready"] is True


def test_get_search(client, injector, mock_person_data):
    pws = injector.get(PersonWebServiceClient)
    mock_list_persons = mock.patch.object(pws, "list_persons").start()
    mock_get_next = mock.patch.object(pws, "get_next").start()
    mock_list_persons.return_value = ListPersonsOutput.parse_obj(mock_person_data)
    del mock_person_data["Next"]
    mock_get_next.return_value = ListPersonsOutput.parse_obj(mock_person_data)
    response = client.get("/search/?name=foo")
    assert response.status_code == 200, response.data
    assert list(response.json.values())[0]["people"]


def test_get_login(client, injector):
    response = client.get("/saml/login")
    assert response.status_code == 302, response.data


def test_get_logout(client, injector):
    response = client.get("/saml/logout")
    assert response.status_code == 302, response.data
