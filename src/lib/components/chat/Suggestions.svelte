<script lang="ts">
	import { getContext } from 'svelte';

	import Document from '$lib/components/icons/Document.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

	const i18n = getContext('i18n');

	export let suggestionPrompts = []; // Keep props to avoid breaking consumers
	export let className = '';
	export let inputValue = '';
	export let onSelect = (e) => {};

	// Cool VibeHub Action cards to replace the boring pill suggestions
	const coolActions = [
		{
			title: 'Сделать сводку',
			subtitle: 'Обзор длинного текста',
			prompt: 'Сделай краткую выжимку по тексту: ',
			icon: Document,
			color: 'text-emerald-500 dark:text-emerald-400',
			bg: 'bg-emerald-50 dark:bg-emerald-500/10',
			border: 'border-emerald-100 dark:border-emerald-500/20'
		},
		{
			title: 'Анализ данных',
			subtitle: 'Поиск инсайтов',
			prompt: 'Проанализируй эти данные и выдели ключевое: ',
			icon: ChartBar,
			color: 'text-indigo-500 dark:text-indigo-400',
			bg: 'bg-indigo-50 dark:bg-indigo-500/10',
			border: 'border-indigo-100 dark:border-indigo-500/20'
		},
		{
			title: 'Оптимизация кода',
			subtitle: 'Рефакторинг и фиксы',
			prompt: 'Проведи рефакторинг следующего кода: ',
			icon: CommandLine,
			color: 'text-amber-500 dark:text-amber-400',
			bg: 'bg-amber-50 dark:bg-amber-500/10',
			border: 'border-amber-100 dark:border-amber-500/20'
		},
		{
			title: 'Генерация идей',
			subtitle: 'Для проекта и бизнеса',
			prompt: 'Предложи 5 прорывных идей на тему: ',
			icon: Sparkles,
			color: 'text-purple-500 dark:text-purple-400',
			bg: 'bg-purple-50 dark:bg-purple-500/10',
			border: 'border-purple-100 dark:border-purple-500/20'
		}
	];
</script>

<div class="flex flex-col gap-2 w-full mt-2 {className}">
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3 w-full">
		{#each coolActions as action, idx (idx)}
			<button
				class="flex flex-col items-start gap-2 p-3.5 rounded-2xl border {action.border} bg-white dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all duration-200 text-left group shadow-sm hover:shadow"
				on:click={() => {
					onSelect(action.prompt);
				}}
			>
				<div class="flex items-center justify-center size-8 rounded-xl {action.bg} {action.color} mb-0.5">
					<svelte:component this={action.icon} className="size-4" />
				</div>
				<div>
					<div class="text-sm font-semibold text-gray-800 dark:text-gray-200 group-hover:text-black dark:group-hover:text-white transition-colors">{action.title}</div>
					<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5 line-clamp-1 truncate">{action.subtitle}</div>
				</div>
			</button>
		{/each}
	</div>
</div>
