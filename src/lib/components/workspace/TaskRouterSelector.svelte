<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';

	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let mode: 'auto' | 'chat' | 'code' | 'research' | 'vision' = 'auto';

	const modes = [
		{ id: 'auto', label: 'Авто', icon: Sparkles },
		{ id: 'chat', label: 'Чат', icon: ChatBubble },
		{ id: 'code', label: 'Код', icon: CommandLine },
		{ id: 'research', label: 'Поиск', icon: GlobeAlt },
		{ id: 'vision', label: 'Фото', icon: Photo }
	];

	function selectMode(newMode) {
		mode = newMode;
		dispatch('change', { mode: newMode });
	}

</script>

<div class="flex items-center gap-1.5 px-1.5 py-1.5 w-fit rounded-[14px] text-xs font-medium bg-gray-50/50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-800/50">
	{#each modes as m}
		<button
			type="button"
			class="flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] transition-all duration-200 {mode ===
				m.id
					? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm border border-gray-200/60 dark:border-gray-700 font-semibold'
					: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100/50 dark:hover:bg-gray-800/80 border border-transparent'}"
			on:click={() => selectMode(m.id)}
			aria-label={m.label}
		>
			<svelte:component this={m.icon} className="size-3.5" />
			<span class="hidden sm:inline">{m.label}</span>
		</button>
	{/each}
</div>
