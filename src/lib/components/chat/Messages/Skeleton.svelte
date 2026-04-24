<script lang="ts">
	export let size = 'md';
</script>

<div class="flex items-center gap-1.5 px-3 py-2.5 w-fit rounded-2xl bg-white/30 dark:bg-[#181818]/80 border border-gray-100 dark:border-white/[0.03] shadow-sm backdrop-blur-md">
	{#if size === 'xs'}
		<div class="size-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite]"></div>
		<div class="size-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite_0.2s]"></div>
		<div class="size-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite_0.4s]"></div>
	{:else}
		<div class="size-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite]"></div>
		<div class="size-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite_0.2s]"></div>
		<div class="size-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-[bounce_1.5s_infinite_0.4s]"></div>
	{/if}
</div>
