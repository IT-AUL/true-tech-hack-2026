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
	{#if $temporaryChatEnabled}
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

	{#if $selectedProjectId}
		<div class="flex justify-center mb-2">
			<div
				class="flex items-center gap-2 px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-full text-xs font-medium border border-blue-100 dark:border-blue-800"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="size-3.5"
				>
					<path
						fill-rule="evenodd"
						d="M2 4.75A2.75 2.75 0 0 1 4.75 2h10.5A2.75 2.75 0 0 1 18 4.75v10.5A2.75 2.75 0 0 1 15.25 18H4.75A2.75 2.75 0 0 1 2 15.25V4.75Zm2.75-.75a1.25 1.25 0 0 0-1.25 1.25v10.5c0 .69.56 1.25 1.25 1.25h10.5c.69 0 1.25-.56 1.25-1.25V5.25c0-.69-.56-1.25-1.25-1.25H4.75Z"
						clip-rule="evenodd"
					/>
				</svg>
				<span
					>{$i18n.t('Project')}: {$projects.find((p) => p.id === $selectedProjectId)?.title}</span
				>

				<button
					class="ml-1 hover:text-blue-800 dark:hover:text-blue-200 transition"
					on:click={() => selectedProjectId.set(null)}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="size-3.5"
					>
						<path
							d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
						/>
					</svg>
				</button>
			</div>
		</div>
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
	{:else}
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
