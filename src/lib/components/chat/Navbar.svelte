<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		WEBUI_NAME,
		banners,
		chatId,
		chatTitle,
		config,
		mobile,
		projects,
		selectedProjectId,
		settings,
		showArchivedChats,
		showSidebar,
		temporaryChatEnabled,
		user
	} from '$lib/stores';

	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { updateChatById } from '$lib/apis/chats';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import SearchModal from '../layout/SearchModal.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import Banner from '../common/Banner.svelte';
	import Sidebar from '../icons/Sidebar.svelte';
	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import ChatPlus from '../icons/ChatPlus.svelte';

	const i18n = getContext('i18n');

	export let initNewChat: Function;
	export let shareEnabled: boolean = false;
	export let scrollTop = 0;

	export let chat;
	export let history;
	export let selectedModels;
	export let showModelSelector = true;

	export let title = '';

	export let onSaveTempChat: () => {};
	export let archiveChatHandler: (id: string) => void;
	export let moveChatHandler: (id: string, folderId: string) => void;

	let closedBannerIds = [];
	let showShareChatModal = false;
	let showSearchModal = false;

	$: activeProject = $projects.find((p) => p.id === $selectedProjectId);

	// Inline editing state
	let isEditingTitle = false;
	let editTitleValue = '';
	let titleInputRef: HTMLInputElement;

	const startEditingTitle = async () => {
		if (!chat?.id || $temporaryChatEnabled) return;
		isEditingTitle = true;
		editTitleValue = title;
		await tick();
		if (titleInputRef) {
			titleInputRef.focus();
			titleInputRef.select();
		}
	};

	const saveTitle = async () => {
		if (isEditingTitle && editTitleValue.trim() !== '') {
			title = editTitleValue.trim();
			chatTitle.set(title);
			await updateChatById(localStorage.token, chat.id, { title: title });
		}
		isEditingTitle = false;
	};

	const handleTitleKeydown = (e) => {
		if (e.key === 'Enter') {
			saveTitle();
		} else if (e.key === 'Escape') {
			isEditingTitle = false;
		}
	};
	const handleSearchShortcut = (e: KeyboardEvent) => {
		if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			showSearchModal = true;
		}
	};
</script>

<svelte:window on:keydown={handleSearchShortcut} />

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />
<SearchModal bind:show={showSearchModal} />

<button
	id="new-chat-button"
	class="hidden"
	on:click={() => { initNewChat(); }}
	aria-label="New Chat"
/>

<nav class="relative z-30 w-full shrink-0">
	<div class="flex items-center h-12 px-3 justify-between">

		<!-- Left: Breadcrumbs / Routing -->
		<div class="flex-1 flex items-center min-w-0 pr-4 max-w-[40%]">
			{#if !$showSidebar}
				<button
					id="tour-sidebar-toggle"
					class="flex items-center justify-center size-8 mr-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition shrink-0"
					on:click={() => showSidebar.set(!$showSidebar)}
				>
					<Sidebar className="size-4" />
				</button>
			{/if}

			<div class="flex items-center space-x-1 min-w-0 w-full">
				<!-- Project Breadcrumb -->
				{#if activeProject}
					<!-- We make the project badge clickable. It unselects the project (returning home) or opens project dashboard -->
					<Tooltip content={$i18n.t('Go to project dashboard')} placement="bottom">
						<button 
							class="flex items-center gap-1.5 px-2 py-1 bg-gray-100/50 hover:bg-gray-200/50 dark:bg-gray-800/30 dark:hover:bg-gray-700/50 rounded-md shrink-0 transition"
							on:click={() => {
								goto('/'); // Simplest way to view project
							}}
						>
							<span class="size-1.5 rounded-full bg-emerald-400 shrink-0"></span>
							<span class="text-xs font-medium text-gray-600 dark:text-gray-300 truncate max-w-[140px]">{activeProject.title}</span>
						</button>
					</Tooltip>
					<span class="text-gray-300 dark:text-gray-600 px-1 select-none shrink-0">/</span>
				{/if}

				<!-- Chat Title (Inline Editable) -->
				{#if chat?.id && title}
					{#if isEditingTitle}
						<input
							bind:this={titleInputRef}
							bind:value={editTitleValue}
							on:blur={saveTitle}
							on:keydown={handleTitleKeydown}
							class="text-sm font-medium bg-transparent border-b border-gray-300 dark:border-gray-600 outline-none w-full max-w-[200px] text-gray-900 dark:text-gray-100 focus:border-black dark:focus:border-white transition-colors"
						/>
					{:else}
						<Tooltip content={$i18n.t('Rename chat')} placement="bottom">
							<button 
								class="text-sm font-medium text-gray-600 dark:text-gray-300 truncate hover:text-gray-900 dark:hover:text-white transition cursor-text px-1 -mx-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800/50 block text-left max-w-[150px]"
								on:click={startEditingTitle}
							>
								{title}
							</button>
						</Tooltip>
					{/if}
				{/if}
			</div>
		</div>

		<!-- Center: Global Command Palette Trigger -->
		<div class="flex items-center justify-center shrink-0 min-w-[250px]">
			<!-- Temporary mock global search button. Could link to a search modal later. -->
			<button 
				class="hidden md:flex items-center gap-3 px-3 py-1.5 w-full max-w-[300px] bg-gray-50 hover:bg-gray-100 dark:bg-gray-800/30 dark:hover:bg-gray-800/60 border border-gray-200/60 dark:border-gray-700/50 rounded-lg text-sm text-gray-400 transition-colors group"
				on:click={() => {
					showSearchModal = true;
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5 group-hover:text-gray-500 transition">
					<path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
				</svg>
				<span class="flex-1 text-left font-medium">{$i18n.t('Search...')}</span>
				<div class="flex gap-0.5 items-center">
					<kbd class="font-sans text-[10px] bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded border border-gray-200 dark:border-gray-600 shadow-sm leading-none opacity-70 group-hover:opacity-100 transition">⌘</kbd>
					<kbd class="font-sans text-[10px] bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded border border-gray-200 dark:border-gray-600 shadow-sm leading-none opacity-70 group-hover:opacity-100 transition">K</kbd>
				</div>
			</button>
			<button 
				class="md:hidden flex items-center justify-center size-8 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition shrink-0"
				on:click={() => { showSearchModal = true; }}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
					<path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
				</svg>
			</button>
		</div>

		<!-- Right: Quick Actions -->
		<div class="flex-1 flex items-center justify-end gap-1 min-w-0 max-w-[40%]">
			<!-- Quick action: New Chat override (visible on mobile only to save space) -->
			{#if $mobile && chat && chat.id}
				<button
					class="flex items-center justify-center size-8 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition"
					on:click={() => { initNewChat(); }}
					aria-label="New Chat"
				>
					<ChatPlus className="size-4" strokeWidth="1.5" />
				</button>
			{/if}

			{#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
				<!-- Quick action: Share -->
				<Tooltip content={$i18n.t('Share chat')} placement="bottom">
					<button
						class="flex items-center justify-center size-8 rounded-lg text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition"
						on:click={() => { showShareChatModal = !showShareChatModal; }}
						aria-label="Share Chat"
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor" class="size-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
						</svg>
					</button>
				</Tooltip>

				<!-- Existing Ellipsis Menu -->
				<Menu
					{chat}
					{shareEnabled}
					shareHandler={() => { showShareChatModal = !showShareChatModal; }}
					archiveChatHandler={() => { archiveChatHandler(chat.id); }}
					{moveChatHandler}
				>
					<button
						class="flex items-center justify-center size-8 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60 transition"
						id="chat-context-menu-button"
					>
						<EllipsisHorizontal className="size-4" strokeWidth="1.5" />
					</button>
				</Menu>
			{/if}
		</div>
	</div>

	<!-- Banners (inline) -->
	{#if !history.currentId && !$chatId && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial' || (($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats))}
		<div class="px-3 pb-1 flex flex-col gap-1">
			{#if ($config?.license_metadata?.type ?? null) === 'trial'}
				<Banner banner={{ type: 'info', title: 'Trial License', content: $i18n.t('You are currently using a trial license. Please contact support to upgrade your license.') }} />
			{/if}

			{#if ($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats}
				<Banner banner={{ type: 'error', title: 'License Error', content: $i18n.t('Exceeded the number of seats in your license. Please contact support to increase the number of seats.') }} />
			{/if}

			{#each $banners.filter((b) => ![...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]'), ...closedBannerIds].includes(b.id)) as banner (banner.id)}
				<Banner
					{banner}
					on:dismiss={(e) => {
						const bannerId = e.detail;
						if (banner.dismissible) {
							localStorage.setItem('dismissedBannerIds', JSON.stringify([bannerId, ...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]')].filter((id) => $banners.find((b) => b.id === id))));
						} else {
							closedBannerIds = [...closedBannerIds, bannerId];
						}
					}}
				/>
			{/each}
		</div>
	{/if}
</nav>
