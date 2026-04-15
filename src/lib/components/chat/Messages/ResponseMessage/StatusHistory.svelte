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
					class="text-left text-[11px] text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 py-0.5"
					aria-expanded={false}
					aria-label={$i18n.t('Toggle status history')}
					on:click={() => {
						showHistory = true;
					}}
				>
					{$i18n.t('Show steps')} ({history.length})
				</button>
			{:else}
				<button
					type="button"
					class="text-left text-[11px] text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 py-0.5 mb-1"
					aria-expanded={true}
					aria-label={$i18n.t('Toggle status history')}
					on:click={() => {
						showHistory = false;
					}}
				>
					{$i18n.t('Hide steps')}
				</button>
				<div class="flex flex-row pl-0.5">
					<div class="w-full">
						{#each history as stepStatus, idx (idx)}
							<div class="flex items-stretch gap-2 mb-1.5 last:mb-0">
								<div class="flex flex-col items-center w-2 shrink-0">
									<div class="pt-2">
										<span class="flex size-1.5 rounded-full bg-gray-400 dark:bg-gray-500"></span>
									</div>
									{#if idx !== history.length - 1}
										<div class="w-px flex-1 min-h-[12px] bg-gray-300 dark:bg-gray-600"></div>
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
