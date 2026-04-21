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
	import { sanitizeResponseContent, extractCurlyBraceWords } from '$lib/utils';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import FolderPlaceholder from './Placeholder/FolderPlaceholder.svelte';
	import FolderTitle from './Placeholder/FolderTitle.svelte';

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

	// Suggestion cards pool — randomized 4 shown per session
	const allSuggestions = [
		{ icon: '✍️', title: 'Написать текст', subtitle: 'Письмо, статья, пост, описание', prompt: 'Напиши ' },
		{ icon: '🎨', title: 'Создать изображение', subtitle: 'Логотип, иллюстрация, арт', prompt: 'Сгенерируй изображение: ' },
		{ icon: '💻', title: 'Написать код', subtitle: 'Python, JS, SQL, API, скрипт', prompt: 'Напиши код: ' },
		{ icon: '📊', title: 'Анализ данных', subtitle: 'Графики, выводы, тренды', prompt: 'Проанализируй данные и выдели ключевое: ' },
		{ icon: '🔍', title: 'Найти информацию', subtitle: 'Факты, исследования, сравнения', prompt: 'Найди информацию о ' },
		{ icon: '📝', title: 'Сделать резюме', subtitle: 'Сократить текст до главного', prompt: 'Сделай краткую выжимку: ' },
		{ icon: '🌐', title: 'Перевести', subtitle: 'С/на любой язык мира', prompt: 'Переведи на английский: ' },
		{ icon: '🧠', title: 'Объяснить тему', subtitle: 'Простыми словами о сложном', prompt: 'Объясни простыми словами: ' },
		{ icon: '📧', title: 'Написать письмо', subtitle: 'Деловое, личное, follow-up', prompt: 'Напиши деловое письмо: ' },
		{ icon: '🚀', title: 'Придумать идею', subtitle: 'Стартап, контент, проект', prompt: 'Придумай идею для ' },
		{ icon: '🐛', title: 'Найти баг в коде', subtitle: 'Дебаг, оптимизация, ревью', prompt: 'Найди ошибку в этом коде: ' },
		{ icon: '📋', title: 'Составить план', subtitle: 'Проект, обучение, мероприятие', prompt: 'Составь подробный план: ' },
	];

	let visibleSuggestions = [];

	// shuffle and pick 4
	function pickSuggestions() {
		const shuffled = [...allSuggestions].sort(() => Math.random() - 0.5);
		visibleSuggestions = shuffled.slice(0, 4);
	}

	onMount(() => {
		pickSuggestions();
	});
</script>

<div class="m-auto w-full max-w-6xl px-2 @2xl:px-20 translate-y-6 py-24 text-center">
	{#if $selectedProjectId}
		{@const currentProject = $projects.find((p) => p.id === $selectedProjectId)}
		{#if currentProject}
			<div class="flex justify-center mb-3">
				<div
					class="flex items-center gap-2 px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-xl text-xs font-semibold border border-indigo-100 dark:border-indigo-800/30"
				>
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.981 0 13.789M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
					</svg>
					<span>Пространство активно · Память подключена</span>
					<button
						class="ml-1 hover:text-indigo-800 dark:hover:text-indigo-200 transition"
						on:click={() => selectedProjectId.set(null)}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-3.5">
							<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
						</svg>
					</button>
				</div>
			</div>
		{/if}
	{:else if $temporaryChatEnabled}
		<Tooltip
			content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-2 text-gray-500 text-base my-2 w-fit">
				<EyeSlash strokeWidth="2.5" className="size-4" />{$i18n.t('Temporary Chat')}
			</div>
		</Tooltip>
	{/if}

	<div
		class="w-full text-3xl text-gray-800 dark:text-gray-100 text-center flex items-center gap-4 font-primary"
	>
		<div class="w-full flex flex-col justify-center items-center">
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
			{:else if $selectedProjectId}
				{@const currentProject = $projects.find((p) => p.id === $selectedProjectId)}
				{#if currentProject}
					<div class="flex flex-col items-center gap-2 w-full max-w-2xl" in:fade={{ duration: 200 }}>
						<h2 class="text-2xl @sm:text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
							{currentProject.title}
						</h2>
						{#if currentProject.description}
							<p class="text-sm text-gray-500 dark:text-gray-400 max-w-md">{currentProject.description}</p>
						{/if}

						<div class="grid grid-cols-3 gap-3 w-full mt-4 text-left">
							<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-xl p-3">
								<div class="flex items-center gap-2 mb-1.5">
									<div class="p-1 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-500 rounded-lg">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
										</svg>
									</div>
									<span class="text-[10px] font-medium text-gray-400 uppercase tracking-wider">Память</span>
								</div>
								<div class="text-lg font-bold text-gray-900 dark:text-white">Mem0</div>
								<p class="text-[10px] text-gray-400">активна</p>
							</div>
							<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-xl p-3">
								<div class="flex items-center gap-2 mb-1.5">
									<div class="p-1 bg-blue-50 dark:bg-blue-900/20 text-blue-500 rounded-lg">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
										</svg>
									</div>
									<span class="text-[10px] font-medium text-gray-400 uppercase tracking-wider">Контекст</span>
								</div>
								<div class="text-lg font-bold text-gray-900 dark:text-white">Проект</div>
								<p class="text-[10px] text-gray-400">изолирован</p>
							</div>
							<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-xl p-3">
								<div class="flex items-center gap-2 mb-1.5">
									<div class="p-1 bg-violet-50 dark:bg-violet-900/20 text-violet-500 rounded-lg">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
										</svg>
									</div>
									<span class="text-[10px] font-medium text-gray-400 uppercase tracking-wider">Статус</span>
								</div>
								<div class="flex items-center gap-1.5">
									<div class="w-1.5 h-1.5 rounded-full bg-green-500"></div>
									<span class="text-sm font-semibold text-green-600 dark:text-green-400">Готово</span>
								</div>
								<p class="text-[10px] text-gray-400">к работе</p>
							</div>
						</div>
					</div>
				{/if}
			{:else}
				<div class="flex flex-col items-center gap-1" in:fade={{ duration: 200 }}>
					<div
						class="text-2xl @sm:text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
					>
						Чем могу помочь?
					</div>
				</div>
			{/if}

			<div class="text-base font-normal @md:max-w-3xl w-full py-3 {atSelectedModel ? 'mt-2' : ''}">
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
					{pendingOAuthTools}
					{toolServers}
					{stopResponse}
					{createMessagePair}
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
		<div
			class="mx-auto px-4 md:max-w-3xl md:px-6 font-primary min-h-62"
			in:fade={{ duration: 200, delay: 200 }}
		>
			<FolderPlaceholder folder={$selectedFolder} />
		</div>
	{:else if !$selectedProjectId}
		<div class="mx-auto max-w-2xl font-primary mt-2" in:fade={{ duration: 300, delay: 150 }}>
			<div class="grid grid-cols-2 gap-3 px-4">
				{#each visibleSuggestions as card, idx}
					<button
						class="group flex flex-col items-start gap-1 p-4 rounded-2xl text-left
							bg-white/50 dark:bg-gray-800/30
							border border-gray-200/70 dark:border-gray-800/60
							hover:bg-white dark:hover:bg-gray-800/60
							hover:border-gray-300 dark:hover:border-gray-700
							hover:shadow-md dark:hover:shadow-gray-900/30
							active:scale-[0.98]
							transition-all duration-200 cursor-pointer select-none"
						style="animation: fadeInUpScale {250 + idx * 80}ms cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0;"
						on:click={() => {
							messageInput?.setText(card.prompt);
						}}
					>
						<div class="flex items-center gap-2">
							<span class="text-lg leading-none opacity-80 group-hover:opacity-100 transition-opacity">{card.icon}</span>
							<span class="text-sm font-medium text-gray-800 dark:text-gray-200 group-hover:text-black dark:group-hover:text-white transition-colors">{card.title}</span>
						</div>
						<span class="text-xs text-gray-400 dark:text-gray-500 group-hover:text-gray-500 dark:group-hover:text-gray-400 transition-colors line-clamp-1">{card.subtitle}</span>
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>
