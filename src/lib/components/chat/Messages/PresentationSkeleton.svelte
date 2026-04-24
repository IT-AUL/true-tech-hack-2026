<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');
</script>

<div
	class="my-2.5 w-full max-w-[280px] rounded-[16px] border border-gray-100 dark:border-white/[0.03] bg-white/30 dark:bg-[#181818]/60 backdrop-blur-md px-4 py-3.5 flex flex-col shadow-sm"
>
	<div class="flex items-center gap-3 mb-3">
		<div class="size-8 rounded-lg bg-gray-100 dark:bg-white/[0.04] flex items-center justify-center text-gray-400 dark:text-gray-500">
			<svg class="size-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0119.5 16.5h-2.25m-9 0h9l-3 3m-3-3l-3 3" /></svg>
		</div>
		<div class="flex flex-col">
			<span class="text-[12px] text-gray-700 dark:text-gray-300 font-semibold tracking-tight">
				{$i18n.t('Presentation')}
			</span>
			<span class="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-widest mt-0.5">
				{$i18n.t('Building Slides...')}
			</span>
		</div>
	</div>

	<div class="grid grid-cols-2 gap-2">
		{#each Array(4) as _}
			<div class="aspect-[16/10] rounded-lg bg-gray-100/50 dark:bg-white/[0.02] border border-gray-50 dark:border-white/[0.02] animate-pulse">
				<div class="mt-2 ml-2 w-1/2 h-0.5 rounded-full bg-gray-300/50 dark:bg-white/10"></div>
				<div class="mt-1 ml-2 w-1/3 h-0.5 rounded-full bg-gray-300/30 dark:bg-white/5"></div>
			</div>
		{/each}
	</div>
</div>
