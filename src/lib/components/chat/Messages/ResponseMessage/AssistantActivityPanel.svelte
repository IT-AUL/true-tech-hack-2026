<script>
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Photo from '$lib/components/icons/Photo.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import Eye from '$lib/components/icons/Eye.svelte';
	import Mic from '$lib/components/icons/Mic.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import PencilSquare from '$lib/components/icons/PencilSquare.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import Database from '$lib/components/icons/Database.svelte';

	/** @type {{ routing?: Record<string, unknown>; description?: string; done?: boolean } | null} */
	export let status = null;

	$: cat = status?.routing?.category ?? '';
	$: primary = status?.routing?.subtitle || status?.description || '';
	$: isDone = status?.done ?? true;

	const CATEGORY_GRADIENTS = {
		image_gen: 'from-pink-500/20 to-violet-500/20 border-pink-200/60 dark:border-pink-700/40',
		audio_gen: 'from-amber-500/20 to-orange-500/20 border-amber-200/60 dark:border-amber-700/40',
		code: 'from-emerald-500/20 to-teal-500/20 border-emerald-200/60 dark:border-emerald-700/40',
		vision: 'from-blue-500/20 to-cyan-500/20 border-blue-200/60 dark:border-blue-700/40',
		math_logic: 'from-purple-500/20 to-indigo-500/20 border-purple-200/60 dark:border-purple-700/40',
		research: 'from-sky-500/20 to-blue-500/20 border-sky-200/60 dark:border-sky-700/40',
		analytics: 'from-violet-500/20 to-purple-500/20 border-violet-200/60 dark:border-violet-700/40',
		creative: 'from-rose-500/20 to-pink-500/20 border-rose-200/60 dark:border-rose-700/40',
		document: 'from-stone-500/20 to-gray-500/20 border-stone-200/60 dark:border-stone-700/40',
		presentation: 'from-orange-500/20 to-pink-500/20 border-orange-200/60 dark:border-orange-700/40',
		memory: 'from-fuchsia-500/20 to-indigo-500/20 border-fuchsia-200/60 dark:border-fuchsia-700/40',
		fallback: 'from-gray-500/10 to-gray-500/10 border-gray-200/60 dark:border-gray-700/40',
	};

	const CATEGORY_ICON_COLORS = {
		image_gen: 'text-pink-500 dark:text-pink-400',
		audio_gen: 'text-amber-500 dark:text-amber-400',
		code: 'text-emerald-500 dark:text-emerald-400',
		vision: 'text-blue-500 dark:text-blue-400',
		math_logic: 'text-purple-500 dark:text-purple-400',
		research: 'text-sky-500 dark:text-sky-400',
		analytics: 'text-violet-500 dark:text-violet-400',
		creative: 'text-rose-500 dark:text-rose-400',
		document: 'text-stone-500 dark:text-stone-400',
		presentation: 'text-orange-500 dark:text-orange-400',
		memory: 'text-fuchsia-500 dark:text-fuchsia-400',
		fallback: 'text-gray-500 dark:text-gray-400',
	};

	$: gradient = CATEGORY_GRADIENTS[cat] || CATEGORY_GRADIENTS['fallback'];
	$: iconColor = CATEGORY_ICON_COLORS[cat] || CATEGORY_ICON_COLORS['fallback'];
</script>

<style>
	.step-pulse {
		animation: stepPulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}
	@keyframes stepPulse {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.5; transform: scale(0.9); }
	}
</style>

<div class="flex flex-col gap-1.5 px-3.5 py-3 bg-white/50 dark:bg-[#141414] rounded-[14px] border border-gray-200/50 dark:border-white/[0.04] w-fit max-w-full shadow-sm text-sm mb-2 relative group overflow-hidden">
	{#if !isDone}
		<!-- Animated subtle glow for active tasks -->
		<div class="absolute inset-0 bg-gradient-to-r {gradient} opacity-20 step-pulse pointer-events-none"></div>
	{/if}

	<div class="flex items-center gap-2.5 relative z-10 w-full justify-between">
		<div class="flex items-center gap-2 min-w-0">
			<!-- Icon -->
			<div class="shrink-0 flex items-center justify-center p-1.5 rounded-md bg-white/50 dark:bg-white/5 border border-gray-100 dark:border-white/5 {iconColor}" aria-hidden="true">
				{#if cat === 'image_gen'}<Photo className="w-3.5 h-3.5" />
				{:else if cat === 'code'}<CommandLine className="w-3.5 h-3.5" />
				{:else if cat === 'vision'}<Eye className="w-3.5 h-3.5" />
				{:else if cat === 'audio_gen'}<Mic className="w-3.5 h-3.5" />
				{:else if cat === 'math_logic'}<ChartBar className="w-3.5 h-3.5" />
				{:else if cat === 'research'}<GlobeAlt className="w-3.5 h-3.5" />
				{:else if cat === 'analytics'}<ChartBar className="w-3.5 h-3.5" />
				{:else if cat === 'creative'}<PencilSquare className="w-3.5 h-3.5" />
				{:else if cat === 'document'}<Document className="w-3.5 h-3.5" />
				{:else if cat === 'presentation'}<span class="text-[13px] leading-none" aria-hidden="true">🎞️</span>
				{:else if cat === 'memory'}<Database className="w-3.5 h-3.5" />
				{:else if cat === 'fallback'}<Bolt className="w-3.5 h-3.5" />
				{:else}<Sparkles className="w-3.5 h-3.5" />
				{/if}
			</div>

			<!-- Title -->
			<div class="font-medium text-[13px] text-gray-800 dark:text-gray-200 leading-snug line-clamp-1 truncate tracking-wide" title={primary}>
				{primary || $i18n.t('Processing...')}
			</div>
		</div>

		<!-- Status Indicator -->
		<div class="shrink-0 pl-3 flex items-center justify-center">
			{#if isDone}
				<svg class="w-4 h-4 text-emerald-500/80 drop-shadow-[0_0_8px_rgba(16,185,129,0.3)]" viewBox="0 0 20 20" fill="currentColor">
					<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
				</svg>
			{:else}
				<div class="size-3.5 rounded-full border-2 border-gray-200 dark:border-gray-700 border-t-gray-500 dark:border-t-gray-300 animate-spin"></div>
			{/if}
		</div>
	</div>

	<!-- Reasoning / Description below -->
	{#if status?.routing?.reasoning || status?.description}
		<div class="relative z-10 w-full">
			<div class="text-[12px] text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed whitespace-pre-wrap font-mono text-opacity-90">
				{status?.routing?.reasoning || status?.description}
			</div>
		</div>
	{/if}
</div>
