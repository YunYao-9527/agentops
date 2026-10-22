import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_api.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src.main import app
    import src.main as main
    from src.db import get_db
    from src.db.models import Base
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def initialize():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dependency():
        async with factory() as session:
            yield session

    monkeypatch.setattr(main, "init_db", initialize)
    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def test_evaluation_executes_and_persists_traces(client):
    assert client.get('/evaluations').status_code == 200
    for asset in ['tailwind.css', 'htmx.min.js', 'alpine.min.js']:
        assert client.get('/static/vendor/' + asset).status_code == 200
    dataset = client.post('/api/v1/datasets', json={'name': 'regression'}).json()['id']
    response = client.post(f'/api/v1/datasets/{dataset}/items/bulk', json=[
        {'input': {'query': 'hello'}, 'expected_output': {'content': 'hello'}},
        {'input': {'query': 'wrong'}, 'expected_output': {'content': 'expected'}},
    ])
    assert response.status_code == 200
    response = client.post('/api/v1/evaluations/run', json={
        'name': 'real scoring', 'dataset_id': dataset, 'config': {'task': 'echo'},
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status'] == 'completed'
    assert result['aggregate_scores']['overall_score'] == 0.5
    assert len(result['trace_ids']) == 2
    saved = client.get('/api/v1/evaluations/' + result['id']).json()
    assert saved['completed_items'] == 2
    assert saved['aggregate_scores']['overall_score'] == 0.5
    assert client.get('/api/v1/traces/' + result['trace_ids'][0]).status_code == 200


def test_invalid_tasks_are_rejected_before_creating_experiment(client, monkeypatch):
    dataset = client.post('/api/v1/datasets', json={'name': 'invalid task'}).json()['id']
    client.post(f'/api/v1/datasets/{dataset}/items', json={'input': {'query': 'x'}})
    response = client.post('/api/v1/evaluations/run', json={
        'name': 'invalid', 'dataset_id': dataset, 'config': {'task': '__import__'},
    })
    assert response.status_code == 400
    from src.config import get_settings
    monkeypatch.setattr(get_settings().llm, 'openai_api_key', 'unit-test')
    monkeypatch.setenv('PUBLIC_DEMO', '1')
    for _ in range(3):
        client.post(f'/api/v1/datasets/{dataset}/items', json={'input': {'query': 'x'}})
    response = client.post('/api/v1/evaluations/run', json={
        'name': 'oversized model batch', 'dataset_id': dataset, 'config': {'task': 'llm'},
    })
    assert response.status_code == 400
    assert 'at most 3' in response.json()['detail']
