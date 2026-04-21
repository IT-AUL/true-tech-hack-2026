<script lang="ts">
	import { goto } from '$app/navigation';
	import { getContext } from 'svelte';
	import { projects, selectedProjectId, user, mobile, showSidebar, showSearch } from '$lib/stores';
	import Tooltip from '../../common/Tooltip.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import UserMenu from '../Sidebar/UserMenu.svelte';
	import PencilSquare from '../../icons/PencilSquare.svelte';
	import Search from '../../icons/Search.svelte';

	const i18n = getContext('i18n');

	export let onSpaceSelect: (id: string) => void = () => {};

	const colors = [
		'from-indigo-500 to-purple-600',
		'from-emerald-500 to-teal-600',
		'from-rose-500 to-pink-600',
		'from-amber-500 to-orange-600',
		'from-blue-500 to-cyan-600',
		'from-fuchsia-500 to-rose-600',
		'from-cyan-500 to-blue-600',
		'from-lime-500 to-green-600'
	];
</script>

<div class="w-[72px] h-full flex flex-col items-center py-3 bg-gray-100/80 dark:bg-gray-900/80 border-r border-gray-200/50 dark:border-gray-800/50 shrink-0 z-50">
	<!-- Home / Logo -->
	<Tooltip content={$i18n.t('Home')} placement="right">
		<button
			class="size-11 rounded-2xl flex items-center justify-center bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750 transition-all shadow-xs border border-gray-200/50 dark:border-gray-700/50 mb-1 {!$selectedProjectId ? 'ring-2 ring-indigo-500 ring-offset-2 ring-offset-gray-100 dark:ring-offset-gray-900' : ''}"
			on:click={() => {
				selectedProjectId.set(null);
				goto('/');
				if ($mobile) showSidebar.set(false);
			}}
		>
			<img src="/static/vibehub_v_icon.svg" class="size-5 invert dark:invert-0" alt="VibeHub" />
		</button>
	</Tooltip>

	<!-- Quick Actions -->
	<div class="flex flex-col items-center gap-1 mb-2">
		<Tooltip content={$i18n.t('New Chat')} placement="right">
			<button
				class="size-9 rounded-xl flex items-center justify-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-800 transition"
				on:click={() => {
					selectedProjectId.set(null);
					goto('/');
					if ($mobile) showSidebar.set(false);
				}}
			>
				<PencilSquare className="size-4" />
			</button>
		</Tooltip>
		<Tooltip content={$i18n.t('Search')} placement="right">
			<button
				class="size-9 rounded-xl flex items-center justify-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-800 transition"
				on:click={() => showSearch.set(true)}
			>
				<Search className="size-4" />
			</button>
		</Tooltip>
	</div>

	<div class="h-px w-8 bg-gray-300/60 dark:bg-gray-700/60 rounded-full mb-3"></div>

	<!-- Spaces List -->
	<div class="flex-1 overflow-y-auto scrollbar-hidden flex flex-col items-center gap-2 w-full px-2">
		{#if $projects && $projects.length > 0}
			{#each $projects as project, idx}
				{@const active = $selectedProjectId === project.id}
				<div class="relative group w-full flex justify-center">
					<!-- Active Indicator Pill -->
					<div
						class="absolute left-0 top-1/2 -translate-y-1/2 w-1 transition-all duration-300 rounded-r-full bg-gray-900 dark:bg-white
						{active ? 'h-7' : 'h-0 group-hover:h-4'}"
					></div>

					<Tooltip content={project.title} placement="right">
						<button
							class="size-11 rounded-2xl flex items-center justify-center text-white font-bold text-base shadow-xs transition-all duration-200
							{active ? 'rounded-[14px] scale-105 shadow-md' : 'opacity-75 hover:opacity-100 hover:rounded-[14px]'}
							bg-gradient-to-br {colors[idx % colors.length]}"
							on:click={() => {
								selectedProjectId.set(project.id);
								onSpaceSelect(project.id);
							}}
						>
							{(project.title || 'P')[0].toUpperCase()}
						</button>
					</Tooltip>
				</div>
			{/each}
		{/if}

		<!-- Add Space -->
		<Tooltip content="Новое пространство" placement="right">
			<button
				class="size-11 rounded-2xl flex items-center justify-center bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750 text-green-500 hover:text-green-600 transition-all shadow-xs border border-dashed border-gray-300 dark:border-gray-700"
				on:click={() => {
					goto('/workspace/projects');
					if ($mobile) showSidebar.set(false);
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
				</svg>
			</button>
		</Tooltip>
	</div>

	<!-- Expand Sidebar Toggle -->
	<div class="mt-2 mb-1">
		<Tooltip content={$showSidebar ? "Свернуть" : "Развернуть"} placement="right">
			<button
				class="size-9 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-800 transition"
				on:click={() => showSidebar.set(!$showSidebar)}
			>
				{#if $showSidebar}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
						<path stroke-linecap="round" stroke-linejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
						<path stroke-linecap="round" stroke-linejoin="round" d="M11.25 4.5l7.5 7.5-7.5 7.5m-6-15l7.5 7.5-7.5 7.5" />
					</svg>
				{/if}
			</button>
		</Tooltip>
	</div>

	<!-- User Profile -->
	<div class="pb-1">
		{#if $user !== undefined && $user !== null}
			<UserMenu role={$user?.role} profile={true} showActiveUsers={false}>
				<button class="relative size-10 rounded-full border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:scale-105 transition overflow-hidden">
					<img
						src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
						class="w-full h-full object-cover"
						alt="User"
					/>
					<div class="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-gray-100 dark:border-gray-900 rounded-full"></div>
				</button>
			</UserMenu>
		{/if}
	</div>
</div>
