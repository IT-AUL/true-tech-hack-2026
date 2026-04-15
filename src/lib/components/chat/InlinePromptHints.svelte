<script lang="ts">
	import { createEventDispatcher, onDestroy, getContext } from 'svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let inputValue = '';
	export let visible = false;
	export let fetchAutoComplete: (text: string) => Promise<string | null> = async () => null;

	let isLoading = false;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let requestId = 0;

	// Session cache for cheap local reuse.
	const suggestionCache = new Map<string, string>();
	let lastRemoteCallAt = 0;
	const REMOTE_MIN_INTERVAL_MS = 8000;
	const REMOTE_EMPTY_MATCH_INTERVAL_MS = 6000;
	const MIN_REMOTE_INPUT_LENGTH = 8;
	const MIN_REMOTE_WORDS = 2;

	// Expanded offline dataset for "clever algorithms"
	const defaultHints = [
		{ text: 'Сделай краткую выжимку по тексту', icon: Document },
		{ text: 'Напиши email коллеге о переносе встречи', icon: Document },
		{ text: 'Сгенерируй изображение логотипа для стартапа', icon: Photo },
		{ text: 'Создай реалистичную фотографию киберпанк города', icon: Photo },
		{ text: 'Напиши Python-скрипт для парсинга CSV', icon: CommandLine },
		{ text: 'Проведи рефакторинг этого кода', icon: CommandLine },
		{ text: 'Реши эту ошибку: ', icon: CommandLine },
		{ text: 'Сравни React и Vue для нового проекта', icon: GlobeAlt },
		{ text: 'Проанализируй эффективность отдела продаж', icon: ChartBar },
		{ text: 'Сделай анализ данных по этой таблице', icon: ChartBar },
		{ text: 'Придумай слоган для кофейни', icon: Sparkles },
		{ text: 'Переведи это на английский', icon: GlobeAlt },
		{ text: 'Исправь опечатки и улучши стиль', icon: Document }
	];

	let displayHints: { text: string; icon: any }[] = [];

	const normalizeText = (value: string) =>
		value
			.toLowerCase()
			.replace(/[^\p{L}\p{N}\s]/gu, ' ')
			.replace(/\s+/g, ' ')
			.trim();

	const uniqueTokens = (value: string) => [...new Set(normalizeText(value).split(' ').filter(Boolean))];

	const localSimilarityScore = (query: string, candidate: string) => {
		const q = normalizeText(query);
		const c = normalizeText(candidate);
		if (!q || !c) return 0;
		if (c.startsWith(q)) return 1;
		if (c.includes(q)) return 0.85;

		const qTokens = uniqueTokens(q);
		const cTokens = uniqueTokens(c);
		if (qTokens.length === 0 || cTokens.length === 0) return 0;

		const overlap = qTokens.filter((t) => cTokens.some((ct) => ct.startsWith(t) || ct.includes(t))).length;
		const tokenScore = overlap / Math.max(qTokens.length, 1);

		// Fast fuzzy signal: character bigram overlap.
		const toBigrams = (text: string) => {
			const out = new Set<string>();
			for (let i = 0; i < text.length - 1; i++) out.add(text.slice(i, i + 2));
			return out;
		};
		const qBi = toBigrams(q);
		const cBi = toBigrams(c);
		const intersection = [...qBi].filter((g) => cBi.has(g)).length;
		const union = Math.max(qBi.size + cBi.size - intersection, 1);
		const bigramScore = intersection / union;

		return tokenScore * 0.65 + bigramScore * 0.35;
	};

	const getLocalHints = (text: string) => {
		const ranked = defaultHints
			.map((hint) => ({ ...hint, score: localSimilarityScore(text, hint.text) }))
			.filter((hint) => hint.score > 0.35)
			.sort((a, b) => b.score - a.score);

		return {
			hints: ranked.slice(0, 3).map(({ text, icon }) => ({ text, icon })),
			bestScore: ranked.length > 0 ? ranked[0].score : 0
		};
	};

	const buildLocalContinuation = (inputText: string, localHints: { text: string; icon: any }[]) => {
		const input = inputText.trim();
		if (!input || localHints.length === 0) return null;

		const best = localHints[0].text;
		const normalizedInput = normalizeText(input);
		const normalizedBest = normalizeText(best);

		// If candidate already starts with input, use it as full inline completion.
		if (normalizedBest.startsWith(normalizedInput) && best.length > input.length + 3) {
			return best;
		}

		// Try to continue by suffix after last token.
		const tokens = uniqueTokens(input);
		const lastToken = tokens.at(-1) ?? '';
		if (!lastToken) return null;
		const idx = normalizedBest.indexOf(lastToken);
		if (idx !== -1) {
			const remainder = best.slice(Math.min(best.length, idx + lastToken.length)).trim();
			if (remainder.length >= 4) {
				return `${input}${input.endsWith(' ') ? '' : ' '}${remainder}`;
			}
		}

		return null;
	};

	const findPrefixCacheHit = (text: string) => {
		const normalized = normalizeText(text);
		if (!normalized) return null;
		let bestKey = '';
		for (const key of suggestionCache.keys()) {
			if (normalized.startsWith(key) && key.length > bestKey.length) {
				bestKey = key;
			}
		}
		return bestKey ? suggestionCache.get(bestKey) ?? null : null;
	};

	const shouldCallRemote = (text: string) => {
		const now = Date.now();
		const words = uniqueTokens(text);
		if (text.length < MIN_REMOTE_INPUT_LENGTH) return false;
		if (words.length < MIN_REMOTE_WORDS) return false;
		if (now - lastRemoteCallAt < REMOTE_MIN_INTERVAL_MS) return false;
		return true;
	};

	function mergeLlmWithTemplates(
		fullSuggestion: string,
		templateRows: { text: string; icon: any }[]
	) {
		const tail = templateRows
			.filter((h) => h.text.trim() !== fullSuggestion.trim())
			.slice(0, 2);
		return [{ text: fullSuggestion, icon: Sparkles }, ...tail];
	}

	async function triggerAutoComplete(text: string, templateRows: { text: string; icon: any }[]) {
		const thisRequestId = ++requestId;

		// 1) Exact cache hit.
		const textKey = normalizeText(text);
		if (suggestionCache.has(textKey)) {
			const fullSuggestion = text + (text.endsWith(' ') ? '' : ' ') + suggestionCache.get(textKey);
			displayHints = mergeLlmWithTemplates(fullSuggestion, templateRows);
			return;
		}

		// 2) Prefix cache hit.
		const prefixSuggestion = findPrefixCacheHit(text);
		if (prefixSuggestion) {
			const fullSuggestion = text + (text.endsWith(' ') ? '' : ' ') + prefixSuggestion;
			displayHints = mergeLlmWithTemplates(fullSuggestion, templateRows);
			return;
		}

		isLoading = true;
		try {
			const result = (await fetchAutoComplete(text)) as string | null;

			if (thisRequestId !== requestId) return; // stale request

			if (result && result.trim() !== '') {
				const suffix = result.trim();
				suggestionCache.set(textKey, suffix);
				lastRemoteCallAt = Date.now();
				const fullSuggestion = text + (text.endsWith(' ') ? '' : ' ') + suffix;
				displayHints = mergeLlmWithTemplates(fullSuggestion, templateRows);
			}
		} catch (e) {
		} finally {
			if (thisRequestId === requestId) {
				isLoading = false;
			}
		}
	}

	$: {
		if (visible) {
			if (!inputValue || inputValue.trim() === '') {
				if (debounceTimer) clearTimeout(debounceTimer);
				debounceTimer = null;
				isLoading = false;
				requestId++;
				displayHints = [...defaultHints].sort(() => Math.random() - 0.5).slice(0, 3);
			} else {
				const text = inputValue.trim();
				const { hints } = getLocalHints(text);
				const localContinuation = buildLocalContinuation(text, hints);
				const templateRowsForLlm =
					hints.length > 0
						? hints.slice(0, 2)
						: [...defaultHints].sort(() => Math.random() - 0.5).slice(0, 2);

				if (hints.length === 0) {
					// Never leave the panel empty: when no fuzzy match, show lightweight defaults.
					displayHints = [...defaultHints].sort(() => Math.random() - 0.5).slice(0, 2);
				} else if (localContinuation) {
					// Prefer continuation derived from current input over static hint templates.
					displayHints = [{ text: localContinuation, icon: Sparkles }, ...hints.slice(0, 2)];
				} else {
					displayHints = hints;
				}

				// Remote: debounced LLM continuation (not blocked by strong local fuzzy matches).
				if (debounceTimer) clearTimeout(debounceTimer);
				const remoteAllowedByRules = shouldCallRemote(text);
				const remoteAllowedForEmptyMatches =
					hints.length === 0 &&
					text.length >= 4 &&
					Date.now() - lastRemoteCallAt >= REMOTE_EMPTY_MATCH_INTERVAL_MS;

				if (remoteAllowedByRules || remoteAllowedForEmptyMatches) {
					debounceTimer = setTimeout(() => {
						triggerAutoComplete(text, templateRowsForLlm);
					}, 1000);
				}
			}
		} else {
			if (debounceTimer) clearTimeout(debounceTimer);
			debounceTimer = null;
			isLoading = false;
			displayHints = [];
		}
	}

	function selectHint(hint: { text: string; icon: any }) {
		dispatch('select', { text: hint.text });
	}

	onDestroy(() => {
		if (debounceTimer) clearTimeout(debounceTimer);
	});
</script>

{#if visible && (displayHints.length > 0 || isLoading)}
	<div
		class="w-full px-3 py-2 flex flex-col gap-0.5 border-t border-gray-100/60 dark:border-gray-800/40"
		role="listbox"
		aria-label={$i18n.t('Suggestions')}
	>
		<div class="flex items-center gap-1.5 px-1.5 py-1 text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
			{#if isLoading}
				<div class="size-3 border-2 border-gray-300 dark:border-gray-600 border-t-indigo-500 rounded-full animate-spin"></div>
			{:else}
				<Sparkles className="size-3" />
			{/if}
			{$i18n.t('Подсказки')}
		</div>

		{#if displayHints.length > 0}
			{#each displayHints as hint, idx}
				<button
					type="button"
					class="flex items-center gap-2.5 px-3 py-2 rounded-xl text-left text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-gray-200 transition-all duration-200 group"
					on:click={() => selectHint(hint)}
					role="option"
					aria-selected="false"
				>
					<span class="shrink-0 opacity-70 group-hover:opacity-100 transition-opacity flex items-center justify-center text-gray-500 dark:text-gray-400 w-4 h-4" aria-hidden="true">
						<svelte:component this={hint.icon} className="size-4" />
					</span>
					<span class="truncate">{hint.text}</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="size-3.5 ml-auto shrink-0 opacity-0 group-hover:opacity-50 transition-opacity -translate-x-1 group-hover:translate-x-0"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 19.5 15-15m0 0H8.25m11.25 0v11.25" />
					</svg>
				</button>
			{/each}
		{:else if isLoading}
			<div class="px-3 py-2 text-xs text-gray-400 dark:text-gray-500 italic">Генерирую подсказку...</div>
		{/if}
	</div>
{/if}
