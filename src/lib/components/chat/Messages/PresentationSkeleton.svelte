<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');
</script>

<div
	class="my-2 w-full max-w-xl rounded-2xl shimmer-block border border-gray-100/80 dark:border-gray-700/50 bg-gray-50/90 dark:bg-gray-850/50 px-4 py-3.5 flex flex-col gap-3"
	aria-busy="true"
>
	<div class="flex items-center gap-2.5">
		<div
			class="size-9 rounded-full bg-white/60 dark:bg-gray-700/40 flex items-center justify-center"
		>
			<span class="text-base">🎞️</span>
		</div>
		<span class="text-[11px] text-gray-500 dark:text-gray-400 font-medium tracking-wide uppercase">
			{$i18n.t('Building presentation...')}
		</span>
	</div>

	<div class="grid grid-cols-3 gap-2">
		{#each Array(6) as _, i}
			<div
				class="aspect-[16/9] rounded-lg bg-gray-200/70 dark:bg-gray-700/40 animate-pulse"
				style={`animation-delay: ${i * 120}ms`}
			></div>
		{/each}
	</div>
</div>
