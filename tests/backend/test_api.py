from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
def test_health():
    assert client.get('/health').json() == {'status': 'ok'}
def test_short_chat_clarifies():
    data = client.post('/chat', json={'message': 'laptop'}).json()
    assert data['clarification'] == 'What is your budget?'
