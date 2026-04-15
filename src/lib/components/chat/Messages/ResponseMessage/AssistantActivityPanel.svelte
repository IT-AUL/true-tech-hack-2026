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

	/** @type {{ routing?: Record<string, unknown>; description?: string } | null} */
	export let status = null;

	$: cat = status?.routing?.category ?? '';
	$: primary = status?.routing?.subtitle || status?.description || '';
</script>

<div
	class="rounded-2xl border border-gray-100/80 dark:border-gray-700/50 bg-gray-50/90 dark:bg-gray-850/50 px-3 py-2.5 w-full max-w-2xl"
>
	<div class="flex gap-2.5 items-start">
		<div class="shrink-0 mt-0.5 w-5 h-5 text-gray-500 dark:text-gray-400" aria-hidden="true">
			{#if cat === 'image_gen'}
				<Photo className="w-5 h-5" />
			{:else if cat === 'code'}
				<CommandLine className="w-5 h-5" />
			{:else if cat === 'vision'}
				<Eye className="w-5 h-5" />
			{:else if cat === 'audio_gen'}
				<Mic className="w-5 h-5" />
			{:else if cat === 'math_logic'}
				<ChartBar className="w-5 h-5" />
			{:else if cat === 'research'}
				<GlobeAlt className="w-5 h-5" />
			{:else if cat === 'analytics'}
				<ChartBar className="w-5 h-5" />
			{:else if cat === 'creative'}
				<PencilSquare className="w-5 h-5" />
			{:else if cat === 'document'}
				<Document className="w-5 h-5" />
			{:else if cat === 'fallback'}
				<Bolt className="w-5 h-5" />
			{:else}
				<Sparkles className="w-5 h-5" />
			{/if}
		</div>
		<div class="min-w-0 flex-1 flex flex-col gap-1">
			<div
				class="text-sm font-medium text-gray-900 dark:text-gray-100 leading-snug line-clamp-2"
				title={primary}
			>
				{primary}
			</div>
			{#if status?.routing?.reasoning}
				<p
					class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed whitespace-pre-wrap line-clamp-6"
				>
					{status.routing.reasoning}
				</p>
			{/if}
			{#if status?.routing && (status.routing.stage != null || status.routing.confidence !== undefined || status.routing.method)}
				<details
					class="group mt-0.5 text-[11px] text-gray-500 dark:text-gray-500 [&_summary]:cursor-pointer [&_summary]:list-none [&_summary::-webkit-details-marker]:hidden"
				>
					<summary
						class="inline-flex items-center gap-1 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100/80 dark:hover:bg-gray-800/80"
					>
						<span class="border-b border-dotted border-gray-400 dark:border-gray-500">
							{$i18n.t('Technical details')}
						</span>
					</summary>
					<div
						class="mt-1.5 pl-0 space-y-0.5 font-mono text-[10px] text-gray-500 dark:text-gray-600"
					>
						{#if status.routing.method}
							<div>method: {status.routing.method}</div>
						{/if}
						{#if status.routing.stage}
							<div>stage: {status.routing.stage}</div>
						{/if}
						{#if status.routing.confidence !== undefined && status.routing.confidence !== null}
							<div>confidence: {Number(status.routing.confidence).toFixed(2)}</div>
						{/if}
						{#if status.routing.model_id}
							<div class="truncate">model: {status.routing.model_id}</div>
						{/if}
					</div>
				</details>
			{/if}
		</div>
	</div>
</div>
