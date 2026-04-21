<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { getProjectMemory, deleteProjectById } from '$lib/apis/projects';
	import { goto } from '$app/navigation';
	import { selectedProjectId, projects, showSettings } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	export let project = null;

	const i18n = getContext('i18n');

	let memory = [];
	let loadingMemory = false;

	$: if (project) {
		loadMemory();
	}

	const loadMemory = async () => {
		if (!project) return;
		loadingMemory = true;
		const res = await getProjectMemory(localStorage.token, project.id).catch((e) => {
			console.error(e);
			return null;
		});
		if (res) {
			memory = res.data || res || [];
		}
		loadingMemory = false;
	};

	const removeProject = async () => {
		if (confirm('Вы уверены, что хотите удалить это пространство? Все привязанные данные памяти будут потеряны.')) {
			await deleteProjectById(localStorage.token, project.id);
			selectedProjectId.set(null);
			$projects = $projects.filter(p => p.id !== project.id);
			toast.success('Пространство удалено');
			goto('/');
		}
	};

	const deselectSpace = () => {
		selectedProjectId.set(null);
	};

	const openSettings = () => {
		goto('/workspace/projects');
	};
</script>

{#if project}
	<div class="w-full max-w-4xl mx-auto h-full px-6 py-8 flex flex-col overflow-y-auto scrollbar-hidden">
		<!-- Header -->
		<div class="mb-8">
			<div class="flex items-center gap-3 mb-4">
				<div class="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-xl text-xs font-semibold border border-indigo-100 dark:border-indigo-800/30">
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.981 0 13.789M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
					</svg>
					<span>Активное Пространство</span>
				</div>
			</div>

			<div class="flex justify-between items-start">
				<div>
					<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-1">{project.title}</h1>
					{#if project.description}
						<p class="text-gray-500 dark:text-gray-400 text-sm max-w-xl">{project.description}</p>
					{/if}
				</div>

				<div class="flex gap-2 shrink-0">
					<button
						class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition"
						on:click={openSettings}
						title="Настройки пространства"
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
							<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
						</svg>
					</button>
					<button
						class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition"
						on:click={deselectSpace}
						title="Выйти из пространства"
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
					<button
						class="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition"
						on:click={removeProject}
						title="Удалить пространство"
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
						</svg>
					</button>
				</div>
			</div>
		</div>

		<!-- Stats Cards -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
			<!-- Memory Stats -->
			<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
				<div class="flex items-center gap-3 mb-3">
					<div class="p-2 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-500 rounded-xl">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
						</svg>
					</div>
					<span class="text-sm font-medium text-gray-500 dark:text-gray-400">Память (Mem0)</span>
				</div>
				<div class="text-3xl font-bold text-gray-900 dark:text-white">{Array.isArray(memory) ? memory.length : 0}</div>
				<p class="text-xs text-gray-400 mt-1">фактов запомнено</p>
			</div>

			<!-- Chats Count -->
			<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
				<div class="flex items-center gap-3 mb-3">
					<div class="p-2 bg-blue-50 dark:bg-blue-900/20 text-blue-500 rounded-xl">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
						</svg>
					</div>
					<span class="text-sm font-medium text-gray-500 dark:text-gray-400">Чаты</span>
				</div>
				<div class="text-3xl font-bold text-gray-900 dark:text-white">—</div>
				<p class="text-xs text-gray-400 mt-1">привязано к пространству</p>
			</div>

			<!-- Status -->
			<div class="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
				<div class="flex items-center gap-3 mb-3">
					<div class="p-2 bg-violet-50 dark:bg-violet-900/20 text-violet-500 rounded-xl">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
						</svg>
					</div>
					<span class="text-sm font-medium text-gray-500 dark:text-gray-400">Статус</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
					<span class="text-sm font-semibold text-green-600 dark:text-green-400">Активно</span>
				</div>
				<p class="text-xs text-gray-400 mt-1">память подключена</p>
			</div>
		</div>

		<!-- Quick Start CTA -->
		<div class="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-6 text-white shadow-lg relative overflow-hidden mb-8">
			<div class="absolute -top-10 -right-10 size-40 bg-white/10 rounded-full blur-2xl"></div>
			<div class="absolute -bottom-10 -left-10 size-32 bg-white/5 rounded-full blur-xl"></div>
			<div class="relative z-10">
				<div class="flex items-center gap-3 mb-2">
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-6">
						<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
					</svg>
					<h3 class="text-xl font-bold">Начни работу в этом пространстве</h3>
				</div>
				<p class="text-white/80 text-sm max-w-md">Напишите запрос в поле ввода внизу — ИИ будет автоматически учитывать весь накопленный контекст этого пространства.</p>
			</div>
		</div>

		<!-- Notes / Artifacts (Placeholder) -->
		<div>
			<h3 class="font-semibold text-gray-900 dark:text-gray-100 mb-3 px-1 flex items-center gap-2">
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
					<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
				</svg>
				Артефакты пространства
			</h3>
			<div class="bg-gray-50 dark:bg-gray-900/50 rounded-2xl border border-dashed border-gray-200 dark:border-gray-800 p-8 flex flex-col items-center justify-center text-center">
				<div class="size-10 bg-white dark:bg-gray-800 rounded-xl shadow-xs flex items-center justify-center mb-3">
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-gray-400">
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
					</svg>
				</div>
				<p class="text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">Здесь появятся заметки и документы</p>
				<p class="text-xs text-gray-400 max-w-[280px]">Прикрепляйте документы, ссылки и заметки к пространству для долгосрочного контекста.</p>
			</div>
		</div>
	</div>
{/if}
