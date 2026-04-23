<script lang="ts">
	export let size = 'md';
</script>

<div class="flex items-center gap-[5px] min-h-[24px] py-1">
	{#if size === 'xs'}
		<div class="size-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-pulse"></div>
		<div class="size-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-pulse delay-75"></div>
		<div class="size-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-pulse delay-150"></div>
	{:else}
		<div class="size-2.5 rounded-full bg-violet-500/80 dark:bg-violet-400/90 shadow-[0_0_8px_rgba(139,92,246,0.5)] animate-bounce" style="animation-duration: 1s;"></div>
		<div class="size-2.5 rounded-full bg-sky-500/80 dark:bg-sky-400/90 shadow-[0_0_8px_rgba(14,165,233,0.5)] animate-bounce" style="animation-delay: 0.15s; animation-duration: 1s;"></div>
		<div class="size-2.5 rounded-full bg-cyan-500/80 dark:bg-cyan-400/90 shadow-[0_0_8px_rgba(6,182,212,0.5)] animate-bounce" style="animation-delay: 0.3s; animation-duration: 1s;"></div>
	{/if}
</div>

<style>
	/* Use tailwind's bounce or built in pulse */
</style>
