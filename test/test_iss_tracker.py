import requests
from geopy import Nominatim
import pytest


def test_epochs_route():
    res = requests.get('http://localhost:5000/epochs')
    assert res.status_code == 200
    assert res.text[2:7] == 'EPOCH'
    res = requests.get('http://localhost:5000/epochs?limit=10&offset=10')
    assert len(res.json()['EPOCH']) == 10
    res = requests.get('http://localhost:5000/epochs?offset=100000')
    assert res.text == 'Error: Offset cannot be greater than length of records.\n'
    res = requests.get('http://localhost:5000/epochs?offset=-10&limit=30')
    assert res.text == 'Error: Limit must be less than the absolute value of offset when offset is negative.\n'
    res = requests.get('http://localhost:5000/epochs?offset=hello')
    assert res.text == 'Error: Could not convert offset to a number.\n'


@pytest.mark.parametrize('epoch', ['2024-066T12:32:00.000Z'])
def test_single_epoch(epoch):
    res = requests.get(f'http://localhost:5000/epochs/{epoch}')
    assert res.status_code == 200
    assert isinstance(res.json(), dict)
    res = requests.get('http://localhost:5000/epochs/BS_epoch')
    assert res.text[:12] == 'Error: Epoch'


@pytest.mark.parametrize('epoch', ['2024-066T12:32:00.000Z'])
def test_speed(epoch):
    res = requests.get(f'http://localhost:5000/epochs/{epoch}/speed')
    assert res.status_code == 200
    assert 'speed' in res.json()


@pytest.mark.parametrize('epoch', ['2024-066T12:32:00.000Z'])
def test_location(epoch):
    res = requests.get(f'http://localhost:5000/epochs/{epoch}/location')
    assert res.status_code == 200
    payload = res.json()
    assert 'geoloc' in payload
    assert payload['geoloc'] == loc.address if (loc := Nominatim(user_agent="test_iss_tracker").reverse(f"{payload['latitude']}, {payload['longitude']}", zoom=15, language='en')) else 'Nearest city unavailable - perhaps over ocean'


def test_now():
    res = requests.get('http://localhost:5000/now')
    assert res.status_code == 200
    assert isinstance(res.json(), dict)


if __name__ == '__main__':
    test_epochs_route()
    test_single_epoch('2024-066T12:32:00.000Z')
    test_speed('2024-066T12:32:00.000Z')
    test_location('2024-066T12:32:00.000Z')
    test_now()