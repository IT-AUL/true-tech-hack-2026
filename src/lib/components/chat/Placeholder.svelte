<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';

	import { onMount, getContext, tick, createEventDispatcher } from 'svelte';
	import { blur, fade } from 'svelte/transition';

	const dispatch = createEventDispatcher();

	import { getChatList } from '$lib/apis/chats';
	import { updateFolderById } from '$lib/apis/folders';

	import {
		config,
		user,
		models as _models,
		temporaryChatEnabled,
		selectedFolder,
		chats,
		currentChatPage,
		projects,
		selectedProjectId
	} from '$lib/stores';
	import { sanitizeResponseContent, extractCurlyBraceWords, getSpaceEmoji } from '$lib/utils';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import FolderPlaceholder from './Placeholder/FolderPlaceholder.svelte';
	import FolderTitle from './Placeholder/FolderTitle.svelte';
	import SpaceDashboard from '$lib/components/workspace/SpaceDashboard.svelte';

	const i18n = getContext('i18n');

	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined;
	export let selectedModels: [''];

	export let history;

	export let prompt = '';
	export let files = [];
	export let messageInput = null;

	export let selectedToolIds = [];
	export let selectedFilterIds = [];
	export let pendingOAuthTools = [];

	export let showCommands = false;

	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let webSearchEnabled = false;

	export let onUpload: Function = (e) => {};
	export let onSelect = (e) => {};
	export let onChange = (e) => {};

	export let toolServers = [];

	export let dragged = false;

	let models = [];
	let selectedModelIdx = 0;

	$: if (selectedModels.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = selectedModels.map((id) => $_models.find((m) => m.id === id));

	const allSuggestions = [
		{ icon: '✍', title: 'Написать текст', subtitle: 'Письмо, статья, пост', prompt: 'Напиши ' },
		{ icon: '💻', title: 'Написать код', subtitle: 'Python, JS, SQL, API, скрипт', prompt: 'Напиши код: ' },
		{ icon: '📧', title: 'Написать письмо', subtitle: 'Деловое, личное, follow-up', prompt: 'Напиши деловое письмо: ' },
		{ icon: '🚀', title: 'Придумать идею', subtitle: 'Стартап, контент, проект', prompt: 'Придумай идею для ' },
	];

	let visibleSuggestions = [];

	function pickSuggestions() {
		visibleSuggestions = allSuggestions.slice(0, 4);
	}

	export let taskMode = false;

	onMount(() => {
		pickSuggestions();
	});
</script>

{#if $selectedProjectId}
	{@const currentProject = $projects.find((p) => p.id === $selectedProjectId)}
	{#if currentProject}
		<div class="w-full h-full flex flex-col bg-slate-50 dark:bg-[#080808]">
			<!-- Dashboard takes full space and we pass the prompt via slot -->
			<SpaceDashboard project={currentProject}>
				<div slot="prompt" class="w-full max-w-4xl mx-auto mb-6 mt-2 relative section-animation z-20">
					<!-- Greeting inside dashboard context -->
					<div class="flex items-center justify-between mb-4">
						<h2 class="text-xl font-bold text-gray-800 dark:text-white/90 tracking-tight flex items-center gap-2">
							<span class="text-violet-500 dark:text-violet-400 shrink-0">
								<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-6">
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 20.25c4.97 0 9-3.694 9-8.25s-4.03-8.25-9-8.25S3 7.444 3 12c0 2.104.859 4.023 2.273 5.48.432.447.74 1.04.586 1.641a4.483 4.483 0 01-.923 1.785A5.969 5.969 0 006 21c1.282 0 2.47-.402 3.445-1.087.81.22 1.668.337 2.555.337z" />
								</svg>
							</span>
							Новый диалог в пространстве
						</h2>
					</div>
					<!-- Input with glow -->
					<div class="relative group">
						<div class="absolute -inset-1.5 bg-gradient-to-r from-violet-500/15 via-indigo-500/15 to-sky-500/15 dark:from-violet-500/10 dark:via-indigo-500/10 dark:to-sky-500/10 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
						<div class="absolute -inset-[1px] bg-gradient-to-r from-violet-500/30 to-indigo-500/30 dark:from-violet-500/20 dark:to-indigo-500/20 rounded-3xl opacity-50 z-0"></div>
						<div class="relative z-10 bg-white/90 dark:bg-black/80 backdrop-blur-md rounded-[23px] shadow-sm">
							<MessageInput
								bind:this={messageInput}
								{history}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:selectedFilterIds
								bind:imageGenerationEnabled
								bind:codeInterpreterEnabled
								bind:webSearchEnabled
								bind:atSelectedModel
								bind:showCommands
								bind:dragged
								bind:taskMode
								{pendingOAuthTools}
								{toolServers}
								{stopResponse}
								{createMessagePair}
								transparentBackground={true}
								placeholder={`Задайте вопрос или поставьте задачу для «${currentProject.title}»...`}
								{onChange}
								{onUpload}
								on:submit={(e) => {
									dispatch('submit', e.detail);
								}}
							/>
						</div>
					</div>
				</div>
			</SpaceDashboard>
		</div>
	{/if}
{:else}
	<!-- Homepage -->
	<div class="w-full h-full flex flex-col bg-slate-50 dark:bg-[#080808]" in:fade={{ duration: 200 }}>
		<!-- Soft background blobs (same as dashboard) -->
		<div class="absolute inset-0 z-0 pointer-events-none overflow-hidden">
			<div class="absolute top-[-10%] right-[-5%] w-[40vw] h-[40vw] rounded-full bg-violet-400/10 dark:bg-violet-600/5 blur-[100px]"></div>
			<div class="absolute bottom-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-sky-400/10 dark:bg-sky-600/5 blur-[120px]"></div>
		</div>

		<div class="relative z-10 w-full flex-1 flex flex-col items-center justify-center px-4">
			<div class="w-full max-w-2xl flex flex-col items-center -mt-10">
				{#if $temporaryChatEnabled}
					<Tooltip
						content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
						className="w-full flex justify-center mb-2"
						placement="top"
					>
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-2 w-fit">
							<EyeSlash strokeWidth="2.5" className="size-4" />{$i18n.t('Temporary Chat')}
						</div>
					</Tooltip>
				{/if}

				{#if $selectedFolder}
					<FolderTitle
						folder={$selectedFolder}
						onUpdate={async (folder) => {
							await chats.set(await getChatList(localStorage.token, $currentChatPage));
							currentChatPage.set(1);
						}}
						onDelete={async () => {
							await chats.set(await getChatList(localStorage.token, $currentChatPage));
							currentChatPage.set(1);
							selectedFolder.set(null);
						}}
					/>
				{:else}
					<!-- Logo + Greeting -->
					<div class="mb-8 text-center" in:fade={{ duration: 250 }}>
						<img
							src="{WEBUI_BASE_URL}/static/vibehub_logo_short.svg"
							class="size-10 mx-auto mb-4 opacity-20 dark:opacity-15 dark:invert-0"
							style="filter: {document.documentElement.classList.contains('dark') ? 'none' : 'brightness(0)'};"
							alt=""
						/>
						<h1 class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white/90">
							Чем могу помочь?
						</h1>
						<p class="text-xs text-gray-400 dark:text-white/25 mt-1.5 font-medium tracking-wide uppercase">Создайте пространство или начните диалог</p>
					</div>
				{/if}

				<!-- Input -->
				<div class="w-full {atSelectedModel ? 'mt-2' : ''}" in:fade={{ duration: 250, delay: 100 }}>
					<div class="relative group">
						<div class="absolute -inset-1.5 bg-gradient-to-r from-violet-500/15 via-sky-500/15 to-indigo-500/15 dark:from-violet-500/10 dark:via-sky-500/10 dark:to-indigo-500/10 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
						<div class="absolute -inset-[1px] bg-gradient-to-r from-violet-500/30 to-sky-500/30 dark:from-violet-500/20 dark:to-sky-500/20 rounded-3xl opacity-50 z-0"></div>
						<div class="relative z-10 bg-white/90 dark:bg-black/80 backdrop-blur-md rounded-[23px] shadow-sm">
							<MessageInput
								bind:this={messageInput}
								{history}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:selectedFilterIds
								bind:imageGenerationEnabled
								bind:codeInterpreterEnabled
								bind:webSearchEnabled
								bind:atSelectedModel
								bind:showCommands
								bind:dragged
								bind:taskMode
								{pendingOAuthTools}
								{toolServers}
								{stopResponse}
								{createMessagePair}
								transparentBackground={true}
								placeholder={'Спросите что угодно, вставьте ссылку или файл...'}
								{onChange}
								{onUpload}
								on:submit={(e) => {
									dispatch('submit', e.detail);
								}}
							/>
						</div>
					</div>
				</div>

				{#if $selectedFolder}
					<div class="w-full px-4 md:max-w-3xl md:px-6 font-primary min-h-62 mt-4" in:fade={{ duration: 200, delay: 200 }}>
						<FolderPlaceholder folder={$selectedFolder} />
					</div>
				{:else}
					<!-- Recent Spaces / Suggestions -->
					<div class="w-full mt-8" in:fade={{ duration: 300, delay: 200 }}>
						{#if $projects && $projects.length > 0}
							<div class="flex items-center justify-between mb-3 px-1">
								<h2 class="text-xs font-bold tracking-widest text-gray-500 dark:text-white/40 uppercase">Ваши пространства</h2>
							</div>
							<div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
								{#each $projects.slice(0, 4) as proj, idx}
									<button
										class="group relative flex flex-col items-center justify-center p-4 rounded-2xl text-center
											bg-white/60 dark:bg-white/[0.02] 
											border border-gray-200/50 dark:border-white/[0.04]
											hover:bg-white dark:hover:bg-white/[0.05]
											hover:border-violet-300 dark:hover:border-violet-500/30
											hover:shadow-lg hover:shadow-violet-500/10 dark:hover:shadow-violet-500/10
											active:scale-[0.98] transition-all duration-300 select-none overflow-hidden"
										style="animation: fadeInUpScale {200 + idx * 60}ms cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0;"
										on:click={() => {
											selectedProjectId.set(proj.id);
										}}
									>
										<!-- Subtle glow inside on hover -->
										<div class="absolute inset-0 bg-gradient-to-br from-violet-500/0 to-sky-500/0 group-hover:from-violet-500/5 group-hover:to-sky-500/5 transition-colors duration-500"></div>
										<div class="relative size-12 mb-3 rounded-xl bg-gray-100 dark:bg-black/40 flex items-center justify-center text-2xl shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 group-hover:scale-110 transition-transform duration-300">
											{getSpaceEmoji(proj.title)}
										</div>
										<span class="relative text-sm font-semibold text-gray-900 dark:text-white/90 truncate w-full">{proj.title}</span>
									</button>
								{/each}
							</div>
						{:else}
							<div class="grid grid-cols-2 gap-2">
								{#each visibleSuggestions as card, idx}
									<button
										class="group flex items-center gap-3 px-4 py-3 rounded-xl text-left
											bg-white/60 dark:bg-white/[0.02]
											border border-gray-200/50 dark:border-white/[0.04]
											hover:bg-white dark:hover:bg-white/[0.05]
											hover:border-gray-300/60 dark:hover:border-white/[0.08]
											active:scale-[0.98]
											transition-all duration-200 cursor-pointer select-none"
										style="animation: fadeInUpScale {250 + idx * 80}ms cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0;"
										on:click={() => {
											messageInput?.setText(card.prompt);
										}}
									>
										<span class="text-base leading-none opacity-50 group-hover:opacity-80 transition-opacity shrink-0">{card.icon}</span>
										<div class="flex flex-col min-w-0">
											<span class="text-sm font-medium text-gray-700 dark:text-white/70 group-hover:text-gray-900 dark:group-hover:text-white/90 transition-colors">{card.title}</span>
											<span class="text-[10px] text-gray-400 dark:text-white/20 truncate">{card.subtitle}</span>
										</div>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
