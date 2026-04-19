<script lang="ts">
	import { createEventDispatcher, onDestroy, getContext } from 'svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let inputValue = '';
	export let visible = false;
	export let fetchAutoComplete: (text: string) => Promise<string | null> = async () => null;

	// ── State ──
	let isLoading = false;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let abortController: AbortController | null = null;
	let requestId = 0;

	// Simple LRU-ish cache (last 20 suggestions)
	const cache = new Map<string, string[]>();
	const CACHE_MAX = 20;

	// ── Config ──
	const DEBOUNCE_MS = 400;       // 400ms debounce (responsive but not spammy)
	const MIN_INPUT_LENGTH = 2;    // Start suggesting after 2 chars
	const MAX_SUGGESTIONS = 3;     // Show max 3 hint rows

	let displayHints: string[] = [];

	// ── Cache helpers ──
	function cacheKey(text: string): string {
		return text.toLowerCase().trim();
	}

	function cacheSet(key: string, hints: string[]) {
		if (cache.size >= CACHE_MAX) {
			// Delete oldest entry
			const firstKey = cache.keys().next().value;
			if (firstKey) cache.delete(firstKey);
		}
		cache.set(key, hints);
	}

	function cacheLookup(text: string): string[] | null {
		const key = cacheKey(text);
		if (cache.has(key)) return cache.get(key)!;
		// Try prefix match: if "напиши к" is cached, reuse for "напиши ко"
		for (const [k, v] of cache) {
			if (key.startsWith(k) && key.length - k.length <= 5) {
				return v;
			}
		}
		return null;
	}

	// ── Core: fetch suggestions ──
	async function fetchSuggestions(text: string) {
		const thisId = ++requestId;

		// Check cache first
		const cached = cacheLookup(text);
		if (cached) {
			displayHints = cached;
			return;
		}

		isLoading = true;

		try {
			const result = await fetchAutoComplete(text);

			if (thisId !== requestId) return; // Stale

			if (result && result.trim()) {
				// Strip <think> reasoning blocks
				let cleanResult = result.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
				cleanResult = cleanResult.replace(/<think>[\s\S]*/gi, '').trim();
				
				if (!cleanResult) return;

				const bannedPrefixes = ['конечно', 'сгенерировано', 'понял', 'вот', 'хорошо', 'да,', 'ок,', 'я могу', 'изображение', 'без проблем', 'готово', 'я', 'сейчас'];
				
				// Parse: API может вернуть одну строку или несколько через \n
				const lines = cleanResult
					.split('\n')
					.map((l) => l.trim())
					.filter((l) => {
						if (l.length === 0 || l.startsWith('<')) return false;
						// Anti-hallucination check: model answered instead of completing
						const lowerL = l.toLowerCase();
						return !bannedPrefixes.some(prefix => lowerL.startsWith(prefix));
					})
					.slice(0, MAX_SUGGESTIONS);

				if (lines.length > 0) {
					// Build full suggestion lines
					const suggestions = lines.map((line) => {
						// If line already starts with the input, use as-is
						const normalLine = line.toLowerCase();
						const normalInput = text.toLowerCase().trim();
						if (normalLine.startsWith(normalInput)) return line;
						// Otherwise prepend user input
						return `${text.trim()} ${line}`;
					});

					displayHints = suggestions;
					cacheSet(cacheKey(text), suggestions);
				}
			}
		} catch {
			// Silently fail — hints are non-critical
		} finally {
			if (thisId === requestId) {
				isLoading = false;
			}
		}
	}

	// ── Reactive: watch input changes ──
	$: {
		if (visible && inputValue) {
			const text = inputValue.trim();
			if (text.length >= MIN_INPUT_LENGTH) {
				// Debounce
				if (debounceTimer) clearTimeout(debounceTimer);
				
				// Immediately show cached results
				const cached = cacheLookup(text);
				if (cached) {
					displayHints = cached;
				}
				
				// Schedule remote fetch
				debounceTimer = setTimeout(() => {
					fetchSuggestions(text);
				}, DEBOUNCE_MS);
			} else {
				// Too short — clear
				displayHints = [];
				isLoading = false;
				if (debounceTimer) clearTimeout(debounceTimer);
			}
		} else if (visible && !inputValue) {
			// Empty input — clear hints
			displayHints = [];
			isLoading = false;
			if (debounceTimer) clearTimeout(debounceTimer);
		} else {
			// Not visible — clean up
			displayHints = [];
			isLoading = false;
			if (debounceTimer) clearTimeout(debounceTimer);
		}
	}

	function selectHint(hint: string) {
		dispatch('select', { text: hint });
	}

	onDestroy(() => {
		if (debounceTimer) clearTimeout(debounceTimer);
		requestId++; // Cancel any in-flight
	});
</script>

{#if visible && (displayHints.length > 0 || isLoading)}
	<div
		class="w-full px-2 py-1 flex flex-col gap-0.5"
		role="listbox"
		aria-label="Подсказки"
	>
		{#if isLoading && displayHints.length === 0}
			<div class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-gray-400 dark:text-gray-500">
				<div class="size-2 border-[1.5px] border-gray-300 dark:border-gray-600 border-t-indigo-400 rounded-full animate-spin"></div>
				<span>Подбираю варианты...</span>
			</div>
		{:else}
			{#each displayHints as hint, idx}
				<button
					type="button"
					class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left text-[13px] text-gray-500 dark:text-gray-400
						hover:bg-white/60 dark:hover:bg-gray-800/50
						hover:text-gray-800 dark:hover:text-gray-200
						active:scale-[0.998]
						transition-all duration-100 group cursor-pointer"
					on:click={() => selectHint(hint)}
					role="option"
					aria-selected="false"
				>
					<Sparkles className="size-3 shrink-0 opacity-40 group-hover:opacity-80 transition-opacity text-indigo-400" />
					<span class="truncate flex-1">{hint}</span>
					<kbd class="text-[9px] text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 font-mono">Tab</kbd>
				</button>
			{/each}
		{/if}
	</div>
{/if}
