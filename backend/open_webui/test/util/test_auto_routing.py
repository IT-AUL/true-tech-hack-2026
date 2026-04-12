from types import SimpleNamespace
from unittest.mock import patch

import pytest
from open_webui.utils.auto_routing import process_auto_routing, resolve_model_for_route


class FakeFile:
    def __init__(self, content_type: str):
        self.meta = {'content_type': content_type}
        self.data = {}
        self.path = 'fake-path'
        self.filename = 'fixture.bin'


def make_request_with_models(models):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(OPENAI_MODELS=models)))


@pytest.mark.asyncio
async def test_process_auto_routing_uses_text_fallback_when_image_data_is_missing():
    payload = {
        'messages': [
            {
                'role': 'user',
                'content': 'Расскажи про доку',
                'files': [{'id': 'file-1'}],
            }
        ]
    }
    available_models = {
        'mws.qwen/qwen3.6-plus': {'id': 'mws.qwen/qwen3.6-plus', 'name': 'Qwen 3.6 Plus'},
    }

    with (
        patch('open_webui.models.files.Files.get_file_by_id', return_value=FakeFile('image/png')),
        patch('open_webui.utils.files.get_image_base64_from_file_id', return_value=None),
    ):
        model_id, updated_payload = await process_auto_routing(
            make_request_with_models(available_models),
            payload,
            SimpleNamespace(),
            available_models=available_models,
        )

    assert model_id == 'mws.qwen/qwen3.6-plus'
    assert updated_payload['messages'][0]['content'] == [{'type': 'text', 'text': 'Расскажи про доку'}]


@pytest.mark.asyncio
async def test_process_auto_routing_resolves_available_vision_model():
    payload = {
        'messages': [
            {
                'role': 'user',
                'content': 'Расскажи про доку',
                'files': [{'id': 'file-1'}],
            }
        ]
    }
    available_models = {
        'mws.qwen/qwen3.6-plus': {'id': 'mws.qwen/qwen3.6-plus', 'name': 'Qwen 3.6 Plus'},
        'mws.google/gemini-2.5-flash': {
            'id': 'mws.google/gemini-2.5-flash',
            'name': 'Gemini 2.5 Flash Vision',
        },
    }

    with (
        patch('open_webui.models.files.Files.get_file_by_id', return_value=FakeFile('image/png')),
        patch('open_webui.utils.files.get_image_base64_from_file_id', return_value='ZmFrZS1pbWFnZQ=='),
    ):
        model_id, updated_payload = await process_auto_routing(
            make_request_with_models(available_models),
            payload,
            SimpleNamespace(),
            available_models=available_models,
        )

    assert model_id == 'mws.google/gemini-2.5-flash'
    assert updated_payload['messages'][0]['content'][-1] == {
        'type': 'image_url',
        'image_url': {'url': 'data:image/png;base64,ZmFrZS1pbWFnZQ=='},
    }


@pytest.mark.asyncio
async def test_process_auto_routing_falls_back_when_route_specific_model_is_missing():
    payload = {
        'messages': [
            {
                'role': 'user',
                'content': 'Напиши код на python для API клиента',
            }
        ]
    }
    available_models = {
        'mws.gpt/gpt-4.1-mini': {'id': 'mws.gpt/gpt-4.1-mini', 'name': 'GPT 4.1 Mini'},
    }

    model_id, _ = await process_auto_routing(
        make_request_with_models(available_models),
        payload,
        SimpleNamespace(),
        available_models=available_models,
    )

    assert model_id == 'mws.gpt/gpt-4.1-mini'


def test_resolve_model_for_route_marks_generic_text_fallback():
    available_models = {
        'mws.gpt/gpt-4.1-mini': {'id': 'mws.gpt/gpt-4.1-mini', 'name': 'GPT 4.1 Mini'},
    }

    model_id, used_fallback = resolve_model_for_route('code', available_models)

    assert model_id == 'mws.gpt/gpt-4.1-mini'
    assert used_fallback is True
