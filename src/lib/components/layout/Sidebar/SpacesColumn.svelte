<script lang="ts">
	import { goto } from '$app/navigation';
	import { getContext } from 'svelte';
	import { projects, selectedProjectId, user, mobile, showSidebar, showSearch, chats, chatId } from '$lib/stores';
	import Tooltip from '../../common/Tooltip.svelte';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import UserMenu from '../Sidebar/UserMenu.svelte';

	const i18n = getContext('i18n');

	export let onSpaceSelect: (id: string) => void = () => {};

	$: spaceChats = $selectedProjectId && $chats
		? $chats.filter(c => c.project_id === $selectedProjectId).slice(0, 10)
		: [];

	import { getSpaceEmoji } from '$lib/utils';
</script>

<div class="w-[68px] h-full flex flex-col items-center py-2.5 bg-white/50 dark:bg-gray-950/50 backdrop-blur-sm border-r border-gray-200/40 dark:border-gray-800/40 shrink-0 z-50">

	<!-- Logo / Home -->
	<button
		class="size-10 rounded-[13px] flex items-center justify-center shrink-0 transition-all duration-200
			{!$selectedProjectId ? 'bg-gray-900 dark:bg-white shadow-md' : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'}"
		on:click={() => { selectedProjectId.set(null); goto('/'); }}
	>
		<img
			src="{WEBUI_BASE_URL}/static/vibehub_logo_short.svg"
			class="size-5"
			style="filter: {$selectedProjectId ? 'brightness(0)' : 'none'};"
			alt="VibeHub"
		/>
	</button>

	<div class="w-6 h-px bg-gray-200 dark:bg-gray-800 rounded-full my-2.5 shrink-0"></div>

	<!-- Spaces -->
	<div class="flex-1 overflow-y-auto scrollbar-hidden flex flex-col items-center gap-1.5 w-full px-2 pt-0.5">
		{#if $projects && $projects.length > 0}
			{#each $projects as project, idx}
				{@const active = $selectedProjectId === project.id}
				<div class="relative group w-full flex justify-center">
					<div
						class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full transition-all duration-300
						{active ? 'h-5 bg-gray-900 dark:bg-white' : 'h-0 group-hover:h-3 bg-gray-400 dark:bg-gray-500'}"
					></div>

					<Tooltip content={project.title} placement="right">
						<button
							class="size-10 rounded-[13px] flex items-center justify-center transition-all duration-200 text-lg
							bg-gray-100 dark:bg-gray-800/80
							{active ? 'shadow-md ring-2 ring-violet-500/30 dark:ring-violet-400/30 scale-[1.05]' : 'opacity-60 hover:opacity-100 hover:scale-[1.02] hover:bg-gray-200 dark:hover:bg-gray-700'}"
							on:click={() => {
								selectedProjectId.set(project.id);
								onSpaceSelect(project.id);
								goto('/');
							}}
						>
							{getSpaceEmoji(project.title)}
						</button>
					</Tooltip>
				</div>
			{/each}
		{/if}

		<!-- Add Space -->
		<Tooltip content="Новое пространство" placement="right">
			<button
				class="size-10 rounded-[13px] flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800/60 border border-dashed border-gray-300/60 dark:border-gray-700/60 transition-all"
				on:click={() => { goto('/workspace/onboarding'); }}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
				</svg>
			</button>
		</Tooltip>
	</div>

	<!-- Space chats mini-nav -->
	{#if $selectedProjectId && spaceChats.length > 0}
		<div class="w-6 h-px bg-gray-200 dark:bg-gray-800 rounded-full my-1.5"></div>
		<div class="flex flex-col items-center gap-1 max-h-[160px] overflow-y-auto scrollbar-hidden px-2 w-full">
			<Tooltip content="Дашборд" placement="right">
				<button
					class="size-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition"
					on:click={() => goto('/')}
				>
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor" class="size-3.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
					</svg>
				</button>
			</Tooltip>
			{#each spaceChats as chat}
				<Tooltip content={chat.title} placement="right">
					<button
						class="size-7 rounded-lg flex items-center justify-center text-[9px] font-semibold transition-all
							{$chatId === chat.id
								? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900'
								: 'bg-gray-100 dark:bg-gray-800/60 text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-200'}"
						on:click={() => goto(`/c/${chat.id}`)}
					>
						{(chat.title || '?')[0].toUpperCase()}
					</button>
				</Tooltip>
			{/each}
		</div>
	{/if}

	<!-- Sidebar toggle (only when no space selected) -->
	{#if !$selectedProjectId}
		<div class="my-1">
			<button
				class="size-8 rounded-lg flex items-center justify-center text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 transition"
				on:click={() => showSidebar.set(!$showSidebar)}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-3.5">
					{#if $showSidebar}
						<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
					{:else}
						<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
					{/if}
				</svg>
			</button>
		</div>
	{/if}

	<!-- User -->
	<div class="mt-auto pb-0.5">
		{#if $user}
			<UserMenu role={$user?.role} profile={true} showActiveUsers={false}>
				<button class="relative size-9 rounded-full border border-gray-200 dark:border-gray-800 hover:scale-105 transition overflow-hidden">
					<img src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`} class="w-full h-full object-cover" alt="" />
				</button>
			</UserMenu>
		{/if}
	</div>
</div>
