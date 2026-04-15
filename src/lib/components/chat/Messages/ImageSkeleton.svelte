<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');
</script>

<div
	class="my-2 w-72 max-w-full aspect-[4/3] rounded-2xl shimmer-block flex flex-col items-center justify-center gap-2.5 border border-gray-100/80 dark:border-gray-700/50 bg-gray-50/90 dark:bg-gray-850/50"
>
	<div
		class="size-10 rounded-full bg-white/60 dark:bg-gray-700/40 flex items-center justify-center"
	>
		<span class="text-lg">🎨</span>
	</div>
	<span class="text-[11px] text-gray-400 dark:text-gray-500 font-medium tracking-wide uppercase">
		{$i18n.t('Generating image...')}
	</span>
</div>
