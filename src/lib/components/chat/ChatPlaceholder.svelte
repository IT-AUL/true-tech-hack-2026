<script lang="ts">
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { marked } from 'marked';

	import { config, user, models as _models, temporaryChatEnabled } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	import { blur, fade } from 'svelte/transition';

	import Suggestions from './Suggestions.svelte';
	import { sanitizeResponseContent } from '$lib/utils';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Mic from '$lib/components/icons/Mic.svelte';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';

	const i18n = getContext('i18n');

	export let modelIds = [];
	export let models = [];
	export let atSelectedModel;

	export let onSelect = (e) => {};

	let mounted = false;
	let selectedModelIdx = 0;

	$: if (modelIds.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = modelIds.map((id) => $_models.find((m) => m.id === id));

	// Quick action cards - premium, clean layout
	const quickActions = [
		{
			icon: ChatBubble,
			title: 'Написать текст',
			subtitle: 'Письмо, статья, пост',
			prompt: 'Напиши мне '
		},
		{
			icon: Photo,
			title: 'Создать картинку',
			subtitle: 'Иллюстрация, дизайн',
			prompt: 'Сгенерируй изображение '
		},
		{
			icon: CommandLine,
			title: 'Написать код',
			subtitle: 'Python, JS, SQL',
			prompt: 'Напиши код на Python: '
		},
		{
			icon: GlobeAlt,
			title: 'Найти информацию',
			subtitle: 'Анализ, исследование',
			prompt: 'Найди и проанализируй информацию о '
		},
		{
			icon: Document,
			title: 'Разобрать документ',
			subtitle: 'Резюме, анализ',
			prompt: 'Проанализируй документ и выдели ключевые моменты: '
		},
		{
			icon: Mic,
			title: 'Создать аудио',
			subtitle: 'Музыка, озвучка',
			prompt: 'Сгенерируй музыку в стиле '
		}
	];

	function getGreeting() {
		const hour = new Date().getHours();
		if (hour < 6) return 'Доброй ночи';
		if (hour < 12) return 'Доброе утро';
		if (hour < 18) return 'Добрый день';
		return 'Добрый вечер';
	}

	onMount(() => {
		mounted = true;
	});
</script>

<style>
	.clean-card-hover {
		transition: all 0.2s ease-out;
	}
	.clean-card-hover:hover {
		background-color: rgba(243, 244, 246, 1); /* Tailwind gray-100 */
		border-color: rgba(229, 231, 235, 1); /* Tailwind gray-200 */
	}
	:global(.dark) .clean-card-hover:hover {
		background-color: rgba(31, 41, 55, 1); /* Tailwind gray-800 */
		border-color: rgba(55, 65, 81, 1); /* Tailwind gray-700 */
	}
	@keyframes fadeInUpScale {
		0% { opacity: 0; transform: translateY(10px) scale(0.98); }
		100% { opacity: 1; transform: translateY(0) scale(1); }
	}
</style>

{#key mounted}
	<div class="m-auto w-full max-w-4xl px-6 lg:px-12 flex flex-col items-center justify-center min-h-[55vh] pb-16">
		<div class="flex flex-col items-center justify-center text-center w-full">
			{#if $temporaryChatEnabled}
				<Tooltip
					content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
					className="flex justify-center mb-4"
					placement="top"
				>
					<div class="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-full text-gray-600 dark:text-gray-300 text-xs font-medium border border-gray-200 dark:border-gray-700">
						<EyeSlash strokeWidth="2.5" className="size-3.5" />{$i18n.t('Temporary Chat')}
					</div>
				</Tooltip>
			{/if}

			<div class="mt-2 mb-8 flex flex-col items-center gap-3 font-primary w-full" in:fade={{ duration: 400, delay: 100 }}>
				<div class="w-16 h-16 mb-2 rounded-2xl bg-gray-50 dark:bg-gray-800 flex items-center justify-center border border-gray-100 dark:border-gray-700/50 shadow-sm">
					<svg class="size-8 text-black dark:text-white" viewBox="0 0 24 24" fill="currentColor">
						<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-2-5.5h4v1.5h-4zM9 13.5h6v1.5H9zM10.5 11h3v1.5h-3z" opacity="0.3"/>
						<path d="M11.645 20.91l-.007-.003-.022-.012a15.247 15.247 0 01-.383-.218 25.18 25.18 0 01-4.244-3.17C4.688 15.36 2.25 12.174 2.25 8.25 2.25 5.322 4.714 3 7.688 3A5.5 5.5 0 0112 5.052 5.5 5.5 0 0116.313 3c2.973 0 5.437 2.322 5.437 5.25 0 3.925-2.438 7.111-4.739 9.256a25.175 25.175 0 01-4.244 3.17 15.247 15.247 0 01-.383.219l-.022.012-.007.004-.003.001a.752.752 0 01-.704 0l-.003-.001z"/>
					</svg>
				</div>
				<h1 class="text-3xl md:text-4xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
					{getGreeting()}
				</h1>
				<p class="text-base text-gray-500 dark:text-gray-400 font-normal max-w-lg">
					Чем могу помочь вам сегодня?
				</p>
			</div>
		</div>

		<!-- Quick Action Cards - minimalist grid -->
		<div class="w-full max-w-3xl mb-4" in:fade={{ duration: 400, delay: 200 }}>
			<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
				{#each quickActions as action, idx}
					<button
						class="clean-card-hover flex flex-col items-start gap-2 p-3.5 rounded-xl bg-transparent border border-gray-100/80 dark:border-gray-800/80 text-left group cursor-pointer"
						style="animation: fadeInUpScale {200 + idx * 50}ms cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0;"
						on:click={() => onSelect({ type: 'prompt', data: action.prompt })}
					>
						<div class="flex items-center gap-2">
							<span class="text-gray-500 dark:text-gray-400 opacity-80" aria-hidden="true">
								<svelte:component this={action.icon} className="size-5" />
							</span>
							<span class="text-sm font-medium text-gray-700 dark:text-gray-300">
								{action.title}
							</span>
						</div>
						<div class="text-[11px] text-gray-400 dark:text-gray-500 line-clamp-1">
							{action.subtitle}
						</div>
					</button>
				{/each}
			</div>
		</div>

		<!-- Model suggestion prompts (if configured) -->
		{#if (atSelectedModel?.info?.meta?.suggestion_prompts ?? models[selectedModelIdx]?.info?.meta?.suggestion_prompts ?? $config?.default_prompt_suggestions ?? []).length > 0}
			<div class="w-full font-primary max-w-3xl opacity-80 hover:opacity-100 transition-opacity duration-300 mt-2" in:fade={{ duration: 400, delay: 450 }}>
				<Suggestions
					className="grid grid-cols-1 md:grid-cols-2 gap-3"
					suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
						models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
						$config?.default_prompt_suggestions ??
						[]}
					{onSelect}
				/>
			</div>
		{/if}
	</div>
{/key}
