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

	// Icons for Smart Actions
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import PencilSquare from '$lib/components/icons/PencilSquare.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import LightBulb from '$lib/components/icons/LightBulb.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import Terminal from '$lib/components/icons/Terminal.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';

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

	// Personalized greeting logic
	let greeting = 'Добрый день';

	function updateGreeting() {
		const hour = new Date().getHours();
		if (hour >= 5 && hour < 12) {
			greeting = 'Доброе утро';
		} else if (hour >= 12 && hour < 18) {
			greeting = 'Добрый день';
		} else if (hour >= 18 && hour < 23) {
			greeting = 'Добрый вечер';
		} else {
			greeting = 'Доброй ночи';
		}
	}

	const smartActions = [
		{ icon: PencilSquare, title: 'Написать текст', subtitle: 'Письмо, статья, пост', prompt: 'Помоги написать текст на тему: ', color: 'text-amber-500', bg: 'bg-amber-500' },
		{ icon: CommandLine, title: 'Написать код', subtitle: 'Python, JS, SQL, API', prompt: 'Напиши код для ', color: 'text-emerald-500', bg: 'bg-emerald-500' },
		{ icon: ChartBar, title: 'Анализ данных', subtitle: 'Тренды, метрики, отчеты', prompt: 'Помоги проанализировать данные: ', color: 'text-sky-500', bg: 'bg-sky-500' },
		{ icon: LightBulb, title: 'Придумать идею', subtitle: 'Стартап, развитие', prompt: 'Предложи креативные идеи для ', color: 'text-yellow-500', bg: 'bg-yellow-500' },
		{ icon: GlobeAlt, title: 'Найти в сети', subtitle: 'Исследование темы', prompt: 'Найди актуальную информацию о ', color: 'text-blue-500', bg: 'bg-blue-500' },
		{ icon: Document, title: 'Саммари текста', subtitle: 'Выжимка самого важного', prompt: 'Сделай краткую выжимку следующего текста: ', color: 'text-stone-500', bg: 'bg-stone-500' },
		{ icon: Terminal, title: 'Bash скрипт', subtitle: 'Автоматизация задач', prompt: 'Напиши bash скрипт который ', color: 'text-fuchsia-500', bg: 'bg-fuchsia-500' },
		{ icon: Sparkles, title: 'Улучшить стиль', subtitle: 'Редактура и улучшение', prompt: 'Сделай этот текст более профессиональным: ', color: 'text-violet-500', bg: 'bg-violet-500' },
	];

	let visibleSuggestions = [];

	function pickSuggestions() {
		const suggestions = [...smartActions];

		// Contextual injection
		if ($chats && $chats.length > 0) {
			const recentChat = $chats[0];
			if (recentChat.title && !recentChat.title.includes('Новый')) {
				suggestions.unshift({
					icon: Sparkles,
					title: 'Развить мысль',
					subtitle: `На основе «${recentChat.title}»`,
					prompt: `Основываясь на нашем последнем диалоге «${recentChat.title}», предложи следующие шаги: `,
					color: 'text-violet-600',
					bg: 'bg-violet-600'
				});
			}
		}

		if ($projects && $projects.length > 0) {
			const recentProject = $projects[0];
			suggestions.unshift({
				icon: GlobeAlt,
				title: 'План работы',
				subtitle: `Для «${recentProject.title}»`,
				prompt: `Составь пошаговый план реализации задач в пространстве «${recentProject.title}»: `,
				color: 'text-sky-600',
				bg: 'bg-sky-600'
			});
		}

		// Randomly select 4 out of the pool (prioritizing context)
		const contextual = suggestions.slice(0, 2);
		const others = suggestions.slice(2).sort(() => 0.5 - Math.random());
		visibleSuggestions = [...contextual, ...others].slice(0, 4);
	}

	export let taskMode = false;

	onMount(() => {
		updateGreeting();
		pickSuggestions();
	});
</script>

<style>
	.step-pulse {
		animation: stepPulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}
	@keyframes stepPulse {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.5; transform: scale(0.98); }
	}

	.nodes-bg {
		background-image: radial-gradient(circle at 1px 1px, rgba(139, 92, 246, 0.05) 1px, transparent 0);
		background-size: 40px 40px;
	}

	.floating-node {
		position: absolute;
		border-radius: 50%;
		background: linear-gradient(to bottom right, rgba(139, 92, 246, 0.1), rgba(56, 189, 248, 0.1));
		filter: blur(4px);
		animation: float 20s infinite linear;
		z-index: 0;
		pointer-events: none;
	}

	@keyframes float {
		0% { transform: translate(0, 0) rotate(0deg); }
		33% { transform: translate(100px, 100px) rotate(120deg); }
		66% { transform: translate(-50px, 200px) rotate(240deg); }
		100% { transform: translate(0, 0) rotate(360deg); }
	}
</style>

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
						<div class="absolute -inset-1.5 bg-gradient-to-r from-violet-500/15 via-indigo-500/15 to-sky-500/15 dark:from-violet-500/10 dark:via-indigo-500/10 dark:to-sky-500/10 rounded-3xl blur-xl opacity-0 hover:opacity-100 transition-opacity duration-500"></div>
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
	<div class="w-full h-full flex flex-col bg-slate-50 dark:bg-[#080808] relative overflow-hidden" in:fade={{ duration: 200 }}>

		<!-- AI BRAIN / NODES BACKGROUND -->
		<div class="absolute inset-0 z-0 pointer-events-none nodes-bg opacity-40 dark:opacity-20"></div>
		<div class="absolute inset-0 z-0 pointer-events-none overflow-hidden">
			<!-- Soft background blobs -->
			<div class="absolute top-[-10%] right-[-5%] w-[40vw] h-[40vw] rounded-full bg-violet-400/10 dark:bg-violet-600/5 blur-[100px]"></div>
			<div class="absolute bottom-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-sky-400/10 dark:bg-sky-600/5 blur-[120px]"></div>

			<!-- Animated nodes -->
			<div class="floating-node w-[300px] h-[300px] top-[10%] left-[20%]" style="animation-duration: 25s; opacity: 0.3;"></div>
			<div class="floating-node w-[200px] h-[200px] bottom-[20%] right-[25%]" style="animation-duration: 18s; animation-delay: -5s; opacity: 0.2;"></div>
			<div class="floating-node w-[400px] h-[400px] top-[40%] right-[10%]" style="animation-duration: 35s; animation-delay: -12s; opacity: 0.1;"></div>
		</div>

		<div class="relative z-10 w-full flex-1 flex flex-col items-center justify-center px-4 overflow-y-auto">
			<div class="w-full max-w-5xl flex flex-col items-center py-12">
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
					<!-- Logo + Greeting (AI Core Visual) -->
					<div class="mb-10 text-center z-10" in:fade={{ duration: 250 }}>
						<div id="tour-logo" class="relative inline-block mb-6">
							<div class="absolute -inset-10 bg-gradient-to-r from-violet-500/10 via-fuchsia-500/10 to-sky-500/10 rounded-full blur-3xl animate-pulse" style="animation-duration: 4s;"></div>
							<img
								src="{WEBUI_BASE_URL}/static/vibehub_logo.svg"
								class="h-20 w-auto drop-shadow-xl transition-transform duration-700 hover:scale-105 dark:brightness-100 brightness-0"
								alt="VibeHub Logo"
							/>
						</div>
						<h1 class="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white/90">
							{greeting}{$user?.name ? ', ' + $user.name.split(' ')[0] : ''}!
						</h1>
						<p class="text-sm text-gray-500 dark:text-white/40 mt-2 font-medium tracking-wide">
							{#if $chats && $chats.length > 0}
								Ваш ИИ-ассистент к вашим услугам. Продолжить работу?
							{:else}
								Чем я могу помочь вам сегодня?
							{/if}
						</p>
					</div>
				{/if}

				<!-- Input -->
				<div id="tour-message-input" class="w-full max-w-2xl {atSelectedModel ? 'mt-2' : ''}" in:fade={{ duration: 250, delay: 100 }}>
					<div class="relative group">
						<div class="absolute -inset-1.5 bg-gradient-to-r from-violet-500/15 via-sky-500/15 to-indigo-500/15 dark:from-violet-500/10 dark:via-sky-500/10 dark:to-indigo-500/10 rounded-3xl blur-xl opacity-0 hover:opacity-100 transition-opacity duration-500"></div>
						<div class="absolute -inset-[1px] bg-gradient-to-r from-violet-500/30 to-sky-500/30 dark:from-violet-500/30 dark:to-sky-500/30 rounded-3xl opacity-60 z-0"></div>
						<div class="relative z-10 bg-white/95 dark:bg-black/90 backdrop-blur-xl rounded-[23px] shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] dark:shadow-none border border-white/50 dark:border-white/5">
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

					<!-- Selected Model & Insights Stats -->
					<div id="tour-ai-insights" class="flex flex-wrap justify-center gap-4 mt-6 mb-2">
						{#if models.length > 0 && models[selectedModelIdx]}
							<div class="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/40 dark:bg-white/[0.03] border border-gray-200/50 dark:border-white/[0.05] shadow-sm backdrop-blur-md opacity-80 hover:opacity-100 transition-opacity">
								<div class="size-2 rounded-full bg-violet-500 animate-pulse"></div>
								<span class="text-[11px] font-bold text-gray-400 dark:text-white/30 uppercase tracking-wider">Модель:</span>
								<span class="text-[12px] font-semibold text-gray-700 dark:text-white/80">{models[selectedModelIdx].name || models[selectedModelIdx].id}</span>
							</div>
						{/if}

						<div class="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/40 dark:bg-white/[0.03] border border-gray-200/50 dark:border-white/[0.05] shadow-sm backdrop-blur-md opacity-80 hover:opacity-100 transition-opacity">
							<span class="text-[11px] font-bold text-gray-400 dark:text-white/30 uppercase tracking-wider">Активность:</span>
							<span class="text-[12px] font-semibold text-gray-700 dark:text-white/80">{$chats?.length || 0} диалогов</span>
						</div>

						<div class="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/40 dark:bg-white/[0.03] border border-gray-200/50 dark:border-white/[0.05] shadow-sm backdrop-blur-md opacity-80 hover:opacity-100 transition-opacity">
							<span class="text-[11px] font-bold text-gray-400 dark:text-white/30 uppercase tracking-wider">Среда:</span>
							<span class="text-[12px] font-semibold text-gray-700 dark:text-white/80">{$projects?.length || 0} пространств</span>
						</div>
					</div>
				</div>

				{#if $selectedFolder}
					<div class="w-full px-4 md:max-w-3xl md:px-6 font-primary min-h-62 mt-4" in:fade={{ duration: 200, delay: 200 }}>
						<FolderPlaceholder folder={$selectedFolder} />
					</div>
				{:else}
					<!-- MINIMALIST SMART ACTIONS GRID -->
					<div id="tour-smart-actions" class="w-full max-w-2xl mt-10" in:fade={{ duration: 300, delay: 200 }}>
						<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
							{#each visibleSuggestions as card, idx}
								<button
									class="group relative flex items-center gap-3.5 p-4 rounded-2xl text-left
										bg-white/40 dark:bg-white/[0.02] backdrop-blur-sm
										border border-gray-200/60 dark:border-white/[0.04]
										hover:bg-white dark:hover:bg-white/[0.04]
										hover:border-transparent dark:hover:border-transparent
										active:scale-[0.98]
										transition-all duration-300 cursor-pointer select-none overflow-hidden
										shadow-sm hover:shadow-xl"
									style="animation: fadeInUpScale {200 + idx * 80}ms cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0;"
									on:click={() => {
										messageInput?.setText(card.prompt);
									}}
								>
									<!-- Icon Box -->
									<div class={`relative shrink-0 flex items-center justify-center size-10 rounded-xl bg-white dark:bg-black/50 border border-gray-100/80 dark:border-white/[0.05] shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)] dark:shadow-none group-hover:scale-110 transition-all duration-300 ${card.color}`}>
										<svelte:component this={card.icon} className="size-5 drop-shadow-sm" />
									</div>

									<!-- Texts -->
									<div class="flex flex-col min-w-0 z-10 relative">
										<span class="text-[13px] font-semibold tracking-wide text-gray-800 dark:text-white/90 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">{card.title}</span>
										<span class="text-[11px] font-medium tracking-wide text-gray-400 dark:text-white/30 truncate mt-0.5">{card.subtitle}</span>
									</div>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
