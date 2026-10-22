from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.experiment_service import build_task


@pytest.mark.asyncio
async def test_llm_task_uses_configured_compatible_endpoint(monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO', '0')
    settings = SimpleNamespace(llm=SimpleNamespace(
        openai_api_key='unit-test', openai_base_url='https://api.deepseek.com', openai_model='deepseek-flash',
    ))
    monkeypatch.setattr('src.core.experiment_service.get_settings', lambda: settings)
    create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='OK'))], model='deepseek-flash',
    ))
    captured = {}
    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr('openai.AsyncOpenAI', FakeClient)
    result = await build_task({'task': 'llm'})({'query': 'Only reply OK'})
    assert result == {'content': 'OK', 'model': 'deepseek-flash'}
    assert captured['base_url'] == 'https://api.deepseek.com'
    assert captured['max_retries'] == 0
    assert create.call_args.kwargs['max_tokens'] == 512
    assert create.call_args.kwargs['extra_body']['thinking']['type'] == 'disabled'
