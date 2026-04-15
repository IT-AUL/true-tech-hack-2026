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
		<div class="text-sm flex flex-col w-full gap-1.5" role="region" aria-label={$i18n.t('Status')}>
			{#if history.length === 1}
				<div class="flex items-start gap-2 w-full">
					<StatusItem status={history[0]} />
				</div>
			{:else if !showHistory}
				<div class="flex items-start gap-2 w-full">
					<StatusItem {status} />
				</div>
				<button
					type="button"
					class="text-left text-[11px] text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 py-0.5 flex items-center gap-1 group"
					aria-expanded={false}
					aria-label={$i18n.t('Toggle status history')}
					on:click={() => {
						showHistory = true;
					}}
				>
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3 transition-transform group-hover:translate-y-0.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
					</svg>
					{$i18n.t('Show steps')} ({history.length})
				</button>
			{:else}
				<button
					type="button"
					class="text-left text-[11px] text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 py-0.5 mb-1 flex items-center gap-1 group"
					aria-expanded={true}
					aria-label={$i18n.t('Toggle status history')}
					on:click={() => {
						showHistory = false;
					}}
				>
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3 transition-transform group-hover:-translate-y-0.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
					</svg>
					{$i18n.t('Hide steps')}
				</button>
				<div class="flex flex-row pl-0.5">
					<div class="w-full">
						{#each history as stepStatus, idx (idx)}
							<div class="flex items-stretch gap-2 mb-1.5 last:mb-0">
								<div class="flex flex-col items-center w-3 shrink-0">
									<div class="pt-2">
										{#if idx === history.length - 1}
											<span class="flex size-2 rounded-full bg-emerald-400 dark:bg-emerald-500 ring-2 ring-emerald-400/30"></span>
										{:else}
											<span class="flex size-1.5 rounded-full bg-gray-300 dark:bg-gray-600"></span>
										{/if}
									</div>
									{#if idx !== history.length - 1}
										<div class="w-px flex-1 min-h-[12px] bg-gradient-to-b from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-700"></div>
									{/if}
								</div>
								<div class="min-w-0 flex-1 pb-0.5">
									<StatusItem status={stepStatus} done={true} />
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}
{/if}
