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
		class="w-full px-3 py-2 flex flex-col gap-1 border-t border-gray-100 dark:border-white/[0.04]"
		role="listbox"
		aria-label="Подсказки"
	>
		{#if isLoading && displayHints.length === 0}
			<div class="flex items-center gap-2 px-3 py-2 text-xs text-gray-400 dark:text-gray-500 font-medium">
				<div class="size-3 border-[2px] border-gray-200 dark:border-gray-700 border-t-violet-500 dark:border-t-violet-400 rounded-full animate-spin"></div>
				<span>Анализирую контекст...</span>
			</div>
		{:else}
			{#each displayHints as hint, idx}
				<button
					type="button"
					class="group relative flex items-center gap-2.5 px-3 py-2 rounded-xl text-left text-[13px] text-gray-600 dark:text-gray-300
						hover:shadow-sm overflow-hidden
						active:scale-[0.99]
						transition-all duration-300 cursor-pointer"
					on:click={() => selectHint(hint)}
					role="option"
					aria-selected="false"
				>
					<div class="absolute inset-0 bg-gradient-to-r from-violet-500/0 via-violet-500/[0.03] to-indigo-500/[0.08] dark:from-violet-500/0 dark:via-violet-500/[0.05] dark:to-indigo-500/[0.1] opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
					<div class="absolute inset-x-0 bottom-0 h-[1px] bg-gradient-to-r from-transparent via-violet-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
					
					<Sparkles className="relative z-10 size-3.5 shrink-0 text-violet-400/70 dark:text-violet-500/60 group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors" />
					<span class="relative z-10 truncate flex-1 font-medium group-hover:text-gray-900 dark:group-hover:text-white transition-all transform group-hover:translate-x-0.5 duration-300">{hint}</span>
					<kbd class="relative z-10 hidden sm:inline-flex items-center justify-center h-5 px-1.5 text-[9px] font-bold text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-white/5 rounded border border-gray-200 dark:border-white/10 opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-x-1 group-hover:translate-x-0 font-mono tracking-wider">TAB</kbd>
				</button>
			{/each}
		{/if}
	</div>
{/if}
