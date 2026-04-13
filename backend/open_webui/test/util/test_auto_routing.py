"""Tests for the hybrid auto-routing pipeline."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from open_webui.utils.auto_routing import (
    RequestFeatures,
    RoutingDecision,
    _classify_with_regex,
    _classify_with_rules,
    _cosine_similarity,
    _detect_lang,
    _estimate_complexity,
    _infer_kind,
    _infer_tier,
    _routing_cache,
    build_model_registry,
    extract_features,
    get_auto_routed_route,
    get_router_model,
    process_auto_routing,
    resolve_model_for_route,
    select_model,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MODELS = {
    'mts-anya': {'id': 'mts-anya', 'name': 'MTS Anya', 'urlIdx': 0},
    'kodify-2.0': {'id': 'kodify-2.0', 'name': 'Kodify 2.0', 'urlIdx': 0},
    'qwen2.5-vl-7b-instruct': {'id': 'qwen2.5-vl-7b-instruct', 'name': 'Qwen 2.5 VL 7B', 'urlIdx': 0},
    'gpt-5.2': {'id': 'gpt-5.2', 'name': 'GPT 5.2', 'urlIdx': 1},
    'flux': {'id': 'flux', 'name': 'Flux Image Gen', 'urlIdx': 0},
    'bge-m3': {'id': 'bge-m3', 'name': 'BGE M3 Embedding', 'urlIdx': 0},
    'whisper-turbo-local-preview': {'id': 'whisper-turbo-local-preview', 'name': 'Whisper Turbo', 'urlIdx': 0},
    'deepseek-reasoner': {'id': 'deepseek-reasoner', 'name': 'DeepSeek Reasoner', 'urlIdx': 0},
    'qwen-turbo': {'id': 'qwen-turbo', 'name': 'Qwen Turbo', 'urlIdx': 0},
    'auto': {'id': 'auto', 'name': 'Auto (Intelligent Routing)', 'urlIdx': 0},
}


class FakeFile:
    def __init__(self, content_type: str):
        self.meta = {'content_type': content_type}
        self.data = {}
        self.path = 'fake-path'
        self.filename = 'fixture.bin'


def make_request_with_models(models):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(OPENAI_MODELS=models)))


# =========================================================================
# Model Registry Tests
# =========================================================================


class TestModelRegistry:
    def test_build_registry_from_dict(self):
        registry = build_model_registry(SAMPLE_MODELS)
        ids = {m.id for m in registry}
        assert 'mts-anya' in ids
        assert 'auto' not in ids

    def test_build_registry_from_list(self):
        models = list(SAMPLE_MODELS.values())
        registry = build_model_registry(models)
        assert len(registry) == len(SAMPLE_MODELS) - 1  # minus 'auto'

    def test_build_registry_empty(self):
        assert build_model_registry(None) == []
        assert build_model_registry({}) == []

    def test_infer_kind_image_gen(self):
        assert _infer_kind('flux image gen') == 'image_gen'
        assert _infer_kind('sd3 sdxl z-image') == 'image_gen'

    def test_infer_kind_code(self):
        assert _infer_kind('kodify-2.0 kodify') == 'code'
        assert _infer_kind('deepseek-coder something') == 'code'

    def test_infer_kind_vlm(self):
        assert _infer_kind('qwen2.5-vl-7b some') == 'vlm'
        assert _infer_kind('gpt-5.2 premium') == 'vlm'

    def test_infer_kind_embedding(self):
        assert _infer_kind('bge-m3 embedding') == 'embedding'

    def test_infer_kind_stt(self):
        assert _infer_kind('whisper-turbo-local-preview') == 'stt'

    def test_infer_kind_text_default(self):
        assert _infer_kind('mts-anya chat model') == 'text'

    def test_infer_tier_premium(self):
        assert _infer_tier('deepseek-reasoner') == 'premium'
        assert _infer_tier('gpt-5.2') == 'premium'

    def test_infer_tier_cheap(self):
        assert _infer_tier('mts-anya something') == 'cheap'
        assert _infer_tier('gpt-3.5-turbo') == 'cheap'
        assert _infer_tier('qwen-turbo fast') == 'cheap'

    def test_infer_tier_mid_default(self):
        assert _infer_tier('qwen-max plus') == 'mid'


class TestGetRouterModel:
    def test_picks_cheap_text(self):
        registry = build_model_registry(SAMPLE_MODELS)
        router = get_router_model(registry)
        assert router is not None
        assert router.tier == 'cheap'
        assert router.kind == 'text'
        assert 'anya' in router.search_text

    def test_empty_registry(self):
        assert get_router_model([]) is None


# =========================================================================
# Feature Extractor Tests
# =========================================================================


class TestFeatureExtractor:
    def test_text_only(self):
        payload = {'messages': [{'role': 'user', 'content': 'Расскажи про Python'}]}
        features = extract_features(payload)
        assert features.text == 'Расскажи про Python'
        assert not features.has_image
        assert not features.has_audio
        assert features.lang == 'ru'

    def test_with_image(self):
        payload = {
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'What is this?'},
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,...'}},
                    ],
                }
            ]
        }
        features = extract_features(payload)
        assert features.has_image
        assert features.lang == 'en'

    def test_code_block_detection(self):
        payload = {'messages': [{'role': 'user', 'content': '```python\ndef foo(): pass\n```'}]}
        features = extract_features(payload)
        assert features.has_code_block

    def test_trivial_message(self):
        payload = {'messages': [{'role': 'user', 'content': 'Привет'}]}
        features = extract_features(payload)
        assert features.is_trivial

    def test_non_trivial_with_pattern(self):
        payload = {'messages': [{'role': 'user', 'content': 'нарисуй'}]}
        features = extract_features(payload)
        assert not features.is_trivial

    def test_empty_messages(self):
        features = extract_features({'messages': []})
        assert features.is_trivial
        assert features.text == ''

    def test_detect_lang_ru(self):
        assert _detect_lang('Привет мир') == 'ru'

    def test_detect_lang_en(self):
        assert _detect_lang('Hello world') == 'en'

    def test_estimate_complexity(self):
        assert _estimate_complexity(10) == 'low'
        assert _estimate_complexity(500) == 'medium'
        assert _estimate_complexity(5000) == 'high'


# =========================================================================
# Rule Engine Tests (Stage 1)
# =========================================================================


class TestRuleEngine:
    def test_trivial_message_does_not_short_circuit_rules(self):
        features = RequestFeatures(
            text='Привет',
            text_len=6,
            has_image=False,
            has_audio=False,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='ru',
            is_trivial=True,
        )
        result = _classify_with_rules(features)
        assert result is None

    def test_image_routes_to_vision(self):
        features = RequestFeatures(
            text='Что на картинке?',
            text_len=16,
            has_image=True,
            has_audio=False,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='ru',
            is_trivial=False,
        )
        result = _classify_with_rules(features)
        assert result is not None
        assert result.category == 'vision'

    def test_image_gen_keyword_overrides_vision(self):
        features = RequestFeatures(
            text='нарисуй кота',
            text_len=12,
            has_image=True,
            has_audio=False,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='ru',
            is_trivial=False,
        )
        result = _classify_with_rules(features)
        assert result is not None
        assert result.category == 'image_gen'

    def test_audio_routes_to_audio_gen(self):
        features = RequestFeatures(
            text='Check this',
            text_len=10,
            has_image=False,
            has_audio=True,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='en',
            is_trivial=False,
        )
        result = _classify_with_rules(features)
        assert result is not None
        assert result.category == 'audio_gen'

    def test_code_block(self):
        features = RequestFeatures(
            text='```python\nprint("hi")\n```',
            text_len=25,
            has_image=False,
            has_audio=False,
            has_files=False,
            has_code_block=True,
            has_url=False,
            lang='en',
            is_trivial=False,
        )
        result = _classify_with_rules(features)
        assert result is not None
        assert result.category == 'code'

    def test_no_match_returns_none(self):
        features = RequestFeatures(
            text='Расскажи мне что-нибудь интересное об истории',
            text_len=46,
            has_image=False,
            has_audio=False,
            has_files=False,
            has_code_block=False,
            has_url=False,
            lang='ru',
            is_trivial=False,
        )
        result = _classify_with_rules(features)
        assert result is None


# =========================================================================
# Regex Safety Net Tests (Stage 4)
# =========================================================================


class TestRegexClassifier:
    def test_image_gen_ru(self):
        result = _classify_with_regex('нарисуй мне кота', False)
        assert result.category == 'image_gen'

    def test_image_gen_ru_create_picture(self):
        result = _classify_with_regex('создай картинку кота', False)
        assert result.category == 'image_gen'

    def test_code_en(self):
        result = _classify_with_regex('write me a python script', False)
        assert result.category == 'code'

    def test_math(self):
        result = _classify_with_regex('реши уравнение 2x+3=7', False)
        assert result.category == 'math_logic'

    def test_fallback(self):
        result = _classify_with_regex('Привет, как дела?', False)
        assert result.category == 'fallback'

    def test_vision_with_image(self):
        result = _classify_with_regex('What is this?', True)
        assert result.category == 'vision'


# =========================================================================
# Scored Model Selection Tests
# =========================================================================


class TestSelectModel:
    def setup_method(self):
        self.registry = build_model_registry(SAMPLE_MODELS)

    def test_code_prefers_kodify(self):
        model_id, fallback = select_model('code', 'medium', self.registry)
        assert model_id == 'kodify-2.0'
        assert not fallback

    def test_image_gen_picks_flux(self):
        model_id, fallback = select_model('image_gen', 'low', self.registry)
        assert model_id == 'flux'
        assert not fallback

    def test_vision_picks_vlm(self):
        model_id, fallback = select_model('vision', 'low', self.registry)
        assert model_id is not None
        meta = next(m for m in self.registry if m.id == model_id)
        assert meta.kind == 'vlm'

    def test_high_complexity_prefers_premium(self):
        model_id, _ = select_model('research', 'high', self.registry)
        assert model_id is not None
        meta = next(m for m in self.registry if m.id == model_id)
        assert meta.tier == 'premium'

    def test_fallback_when_no_specific_model(self):
        minimal = {'generic-text': {'id': 'generic-text', 'name': 'Generic Text LLM', 'urlIdx': 0}}
        registry = build_model_registry(minimal)
        model_id, fallback = select_model('image_gen', 'low', registry)
        assert model_id == 'generic-text'
        assert fallback

    def test_excludes_embedding_and_stt(self):
        model_id, _ = select_model('fallback', 'low', self.registry)
        assert model_id not in ('bge-m3', 'whisper-turbo-local-preview')

    def test_legacy_resolve_model_for_route(self):
        model_id, used_fallback = resolve_model_for_route('code', SAMPLE_MODELS)
        assert model_id == 'kodify-2.0'
        assert not used_fallback


# =========================================================================
# Cache Tests
# =========================================================================


class TestCache:
    def setup_method(self):
        _routing_cache.clear()

    def test_put_and_get(self):
        decision = RoutingDecision('code', 'medium', method='rules')
        _routing_cache.put('key1', decision)
        assert _routing_cache.get('key1') is not None
        assert _routing_cache.get('key1').category == 'code'

    def test_miss(self):
        assert _routing_cache.get('nonexistent') is None

    def test_lru_eviction(self):
        from open_webui.utils.auto_routing import _TTLCache

        small_cache = _TTLCache(maxsize=2, ttl=60)
        small_cache.put('a', RoutingDecision('code', 'low'))
        small_cache.put('b', RoutingDecision('vision', 'low'))
        small_cache.put('c', RoutingDecision('fallback', 'low'))
        assert small_cache.get('a') is None
        assert small_cache.get('b') is not None
        assert small_cache.get('c') is not None


# =========================================================================
# Cosine Similarity Tests
# =========================================================================


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 1.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


# =========================================================================
# Orchestrator Integration Tests
# =========================================================================


class TestOrchestrator:
    def setup_method(self):
        _routing_cache.clear()

    @pytest.mark.asyncio
    async def test_trivial_message_uses_regex_fallback_without_short_circuit(self):
        payload = {'messages': [{'role': 'user', 'content': 'Да'}]}
        decision = await get_auto_routed_route(payload)
        assert decision.category == 'fallback'
        assert decision.method == 'regex_fallback'

    @pytest.mark.asyncio
    async def test_short_image_request_routes_to_image_generation(self):
        payload = {'messages': [{'role': 'user', 'content': 'создай картинку кота'}]}
        decision = await get_auto_routed_route(payload)
        assert decision.category == 'image_gen'
        assert decision.method == 'rules'

    @pytest.mark.asyncio
    async def test_rules_catch_code(self):
        payload = {'messages': [{'role': 'user', 'content': '```python\nprint("hello")\n```'}]}
        decision = await get_auto_routed_route(payload)
        assert decision.category == 'code'
        assert decision.method == 'rules'

    @pytest.mark.asyncio
    async def test_cache_hit_on_repeat(self):
        payload = {'messages': [{'role': 'user', 'content': 'нарисуй мне кота в шляпе'}]}
        await get_auto_routed_route(payload)
        d2 = await get_auto_routed_route(payload)
        assert d2.cache_hit

    @pytest.mark.asyncio
    async def test_cache_hit_isolated_from_returned_decision_mutation(self):
        payload = {'messages': [{'role': 'user', 'content': 'Напиши код на python для API клиента'}]}

        first = await get_auto_routed_route(payload)
        first.category = 'fallback'
        first.model_id = 'broken-model'
        first.used_model_fallback = True

        second = await get_auto_routed_route(payload)
        assert second.cache_hit
        assert second.category == 'code'
        assert second.model_id is None
        assert not second.used_model_fallback

        second.category = 'fallback'

        third = await get_auto_routed_route(payload)
        assert third.cache_hit
        assert third.category == 'code'

    @pytest.mark.asyncio
    async def test_regex_fallback_for_ambiguous(self):
        payload = {'messages': [{'role': 'user', 'content': 'реши уравнение x^2 + 2x - 3 = 0'}]}
        decision = await get_auto_routed_route(payload)
        assert decision.category == 'math_logic'


# =========================================================================
# Process Auto Routing Integration Tests
# =========================================================================


class TestProcessAutoRouting:
    @pytest.mark.asyncio
    async def test_text_fallback_when_image_data_missing(self):
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
            model_id, updated_payload, decision = await process_auto_routing(
                make_request_with_models(available_models),
                payload,
                SimpleNamespace(),
                available_models=available_models,
            )
        assert model_id == 'mws.qwen/qwen3.6-plus'

    @pytest.mark.asyncio
    async def test_resolves_vision_model(self):
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
            model_id, updated_payload, decision = await process_auto_routing(
                make_request_with_models(available_models),
                payload,
                SimpleNamespace(),
                available_models=available_models,
            )
        assert model_id == 'mws.google/gemini-2.5-flash'

    @pytest.mark.asyncio
    async def test_falls_back_when_route_specific_missing(self):
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
        model_id, _, decision = await process_auto_routing(
            make_request_with_models(available_models),
            payload,
            SimpleNamespace(),
            available_models=available_models,
        )
        assert model_id == 'mws.gpt/gpt-4.1-mini'

    @pytest.mark.asyncio
    async def test_empty_messages_returns_fallback(self):
        payload = {'messages': []}
        available_models = {
            'some-model': {'id': 'some-model', 'name': 'Some Model'},
        }
        model_id, _, decision = await process_auto_routing(
            make_request_with_models(available_models),
            payload,
            SimpleNamespace(),
            available_models=available_models,
        )
        assert model_id == 'some-model'
