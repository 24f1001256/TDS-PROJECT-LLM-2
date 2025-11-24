import pytest
from main import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_missing_fields(client):
    """Test with missing fields in the request."""
    rv = client.post('/', data=json.dumps({}), content_type='application/json')
    assert rv.status_code == 400
    json_data = rv.get_json()
    assert 'Missing required fields' in json_data['error']

def test_invalid_secret(client):
    """Test with an invalid secret."""
    rv = client.post('/', data=json.dumps({
        "email": "test@example.com",
        "secret": "wrong-secret",
        "url": "http://example.com"
    }), content_type='application/json')
    assert rv.status_code == 403
    json_data = rv.get_json()
    assert 'Invalid secret' in json_data['error']

def test_valid_request(client, monkeypatch):
    """Test a valid request."""
    # We'll mock the solve_and_submit function to avoid actual quiz solving
    def mock_solve_and_submit(email, secret, quiz_url):
        print(f"Mock solve_and_submit called with {email}, {secret}, {quiz_url}")

    monkeypatch.setattr("main.solve_and_submit", mock_solve_and_submit)

    rv = client.post('/', data=json.dumps({
        "email": "test@example.com",
        "secret": "default-secret",
        "url": "http://example.com"
    }), content_type='application/json')

    assert rv.status_code == 200
    json_data = rv.get_json()
    assert 'Quiz solving initiated' in json_data['status']
