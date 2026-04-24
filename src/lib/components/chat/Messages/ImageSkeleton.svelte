<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');
</script>

<div
	class="my-2 w-56 max-w-full aspect-[4/3] rounded-[14px] flex flex-col items-center justify-center gap-3 border border-gray-100 dark:border-white/[0.03] bg-white/30 dark:bg-[#181818]/60 backdrop-blur-md shadow-sm"
>
	<div class="relative size-10 flex items-center justify-center text-gray-400 dark:text-gray-500">
		<svg class="size-6 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M15 7.5a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z" /></svg>
	</div>

	<div class="flex items-center gap-1.5">
		<span class="text-[10px] text-gray-500 dark:text-gray-400 font-medium uppercase tracking-[0.15em]">
			{$i18n.t('Generating Image...')}
		</span>
	</div>
</div>
