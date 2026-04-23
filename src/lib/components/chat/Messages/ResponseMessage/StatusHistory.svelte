<script>
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import StatusItem from './StatusHistory/StatusItem.svelte';
	export let statusHistory = [];
	export let expand = false;

	let showHistory = false;

	$: if (expand) {
		showHistory = true;
	}

	let history = [];
	let status = null;

	// Prefer the auto-routing card (reasoning) over generic tails like "Image created".
	$: if (history && history.length > 0) {
		const routing = [...history].reverse().find((s) => s?.action === 'auto_routing');
		status = routing ?? history.at(-1);
	}

	$: if (
		statusHistory.length !== history.length ||
		JSON.stringify(statusHistory) !== JSON.stringify(history)
	) {
		history = statusHistory;
	}
</script>

{#if history && history.length > 0}
	{#if status?.hidden !== true}
		<div class="text-sm flex flex-col w-full gap-2" role="region" aria-label={$i18n.t('Status')}>
			{#if history.length === 1}
				<div class="flex items-start gap-2 w-full">
					<StatusItem status={history[0]} />
				</div>
			{:else if !showHistory}
				<div class="relative group w-fit cursor-pointer" on:click={() => showHistory = true}>
					<div class="flex items-start gap-2 w-full hover:opacity-80 transition-opacity">
						<StatusItem {status} />
					</div>
					<!-- Overlaid subtle prompt to expand -->
					<div class="absolute -bottom-2 -right-2 flex">
						<button
							type="button"
							class="text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100/80 dark:bg-white/[0.06] backdrop-blur-md px-2 py-0.5 rounded-lg shadow-sm border border-gray-200/50 dark:border-white/5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity translate-y-1 group-hover:translate-y-0"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-3">
								<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
							</svg>
							{$i18n.t('View all steps')} <span class="opacity-50">({history.length})</span>
						</button>
					</div>
				</div>
			{:else}
				<button
					type="button"
					class="text-left text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 py-1.5 px-3 rounded-lg bg-gray-100/50 dark:bg-white/[0.04] border border-gray-200/50 dark:border-white/5 transition flex items-center gap-1.5 w-fit group mb-2"
					aria-expanded={true}
					aria-label={$i18n.t('Toggle status history')}
					on:click={() => {
						showHistory = false;
					}}
				>
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-3 transition-transform group-hover:-translate-y-0.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 15.75 12 8.25l-7.5 7.5" />
					</svg>
					{$i18n.t('Hide steps')}
				</button>
				
				<div class="flex flex-col ml-1">
					{#each history as stepStatus, idx (idx)}
						<div class="flex items-stretch gap-3 relative mb-2 last:mb-0">
							<!-- Timeline line -->
							<div class="flex flex-col items-center w-3 shrink-0">
								<div class="pt-2 z-10">
									{#if idx === history.length - 1}
										<span class="flex size-2 rounded-full bg-emerald-400 dark:bg-emerald-500 ring-2 ring-emerald-400/30"></span>
									{:else}
										<span class="flex size-[5px] rounded-full bg-gray-300 dark:bg-gray-600"></span>
									{/if}
								</div>
								{#if idx !== history.length - 1}
									<div class="w-[1.5px] flex-1 min-h-[16px] bg-gradient-to-b from-gray-200 to-gray-100 dark:from-white/10 dark:to-transparent mt-1"></div>
								{/if}
							</div>
							
							<div class="min-w-0 flex-1 pb-1">
								<StatusItem status={stepStatus} done={true} />
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
{/if}
