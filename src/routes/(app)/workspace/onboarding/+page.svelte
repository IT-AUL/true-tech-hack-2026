<script lang="ts">
	import { goto } from '$app/navigation';
	import { getContext, onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { createNewProject, getProjects } from '$lib/apis/projects';
	import { getSpaceEmoji } from '$lib/utils';
	import { projects, selectedProjectId, models as _models } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	let step = 0;
	let submitting = false;
	let title = '';
	let description = '';
	let selectedRole = '';
	let autoMemory = true;
	let selectedModel = '';

	const roles = [
		{ id: 'dev', label: 'Разработка', sub: 'Код ・ Архитектура', icon: '💻', color: 'text-sky-400', bg: 'bg-sky-500/10' },
		{ id: 'product', label: 'Продакт', sub: 'Метрики ・ Roadmap', icon: '🚀', color: 'text-amber-400', bg: 'bg-amber-500/10' },
		{ id: 'design', label: 'Дизайн', sub: 'UI/UX ・ Визуал', icon: '🎨', color: 'text-fuchsia-400', bg: 'bg-fuchsia-500/10' },
		{ id: 'research', label: 'Аналитика', sub: 'Данные ・ A/B тесты', icon: '🔬', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
		{ id: 'marketing', label: 'Маркетинг', sub: 'Контент ・ SMM', icon: '📣', color: 'text-rose-400', bg: 'bg-rose-500/10' },
		{ id: 'custom', label: 'Другое', sub: 'Свой тип задачи', icon: '🧩', color: 'text-violet-400', bg: 'bg-violet-500/10' },
	];


	$: canNext = step === 0 ? title.trim().length > 0 : true;
	$: progress = ((step + 1) / 4) * 100;

	function next() {
		if (step < 3) { step += 1; if (step === 3) submit(); }
	}
	function back() { if (step > 0) step -= 1; }

	async function submit() {
		submitting = true;
		const meta = JSON.stringify({ role: selectedRole, autoMemory, defaultModel: selectedModel });
		const desc = `${description}\n<!--space-meta:${meta}-->`;

		const res = await createNewProject(localStorage.token, title, desc).catch(e => {
			toast.error(`${e}`);
			submitting = false;
			step = 2;
			return null;
		});

		if (res) {
			projects.set(await getProjects(localStorage.token));
			selectedProjectId.set(res.id);
			submitting = false;
		}
	}

	onMount(() => {
		if ($_models.length > 0) selectedModel = $_models[0].id;
	});
</script>

<svelte:head><title>Новое пространство</title></svelte:head>

<div class="w-full min-h-screen flex items-center justify-center p-6 bg-[#0f0f0f] dark:bg-[#0a0a0a]">
	<div class="w-full max-w-md">

		<!-- Progress -->
		<div class="mb-8 flex items-center gap-3">
			{#each [0, 1, 2, 3] as s}
				<div class="flex-1 h-0.5 rounded-full transition-colors duration-500 {s <= step ? 'bg-gray-900 dark:bg-white' : 'bg-gray-200 dark:bg-gray-800'}"></div>
			{/each}
		</div>

		{#key step}
		<div in:fly={{ x: 40, duration: 250, delay: 30 }} out:fly={{ x: -40, duration: 180 }}>

			<!-- Step 0: Name -->
			{#if step === 0}
				<div class="space-y-6">
					<div>
						<h1 class="text-xl font-semibold text-gray-900 dark:text-white">Назовите пространство</h1>
						<p class="text-xs text-gray-400 mt-1">Это будет контекст для всех чатов внутри</p>
					</div>

					<div class="space-y-4 pt-2">
						<div>
							<label class="block text-xs font-medium text-white/60 mb-2 ml-1 cursor-pointer">Название проекта</label>
							<div class="relative flex items-center">
								<div class="absolute left-3.5 text-white/30 text-base">✏️</div>
								<input
									type="text"
									bind:value={title}
									class="w-full pl-10 pr-3.5 py-3 rounded-xl bg-white/5 text-white border border-white/10 text-sm outline-none focus:bg-white/10 focus:border-white/30 transition-all shadow-sm placeholder:text-white/20"
									placeholder="Океан v2.0"
									autofocus
								/>
							</div>
						</div>
						<div>
							<label class="block text-xs font-medium text-white/60 mb-2 ml-1 cursor-pointer">ТЗ или фокус (опционально)</label>
							<div class="relative">
								<div class="absolute left-3.5 top-3 text-white/30 text-base">🎯</div>
								<textarea
									bind:value={description}
									class="w-full pl-10 pr-3.5 py-3 rounded-xl bg-white/5 text-white border border-white/10 text-sm outline-none focus:bg-white/10 focus:border-white/30 transition-all resize-none h-20 shadow-sm placeholder:text-white/20"
									placeholder="Опишите главные задачи пространства..."
								></textarea>
							</div>
						</div>
					</div>

					<!-- Live preview -->
					{#if title.trim()}
						<div class="flex items-center gap-3 p-3 rounded-xl bg-white/5 dark:bg-white/5 border border-white/10" in:fade={{ duration: 150 }}>
							<div class="size-10 rounded-xl bg-gray-800 flex items-center justify-center text-xl shadow-sm leading-none shrink-0 border border-white/5">
								{getSpaceEmoji(title)}
							</div>
							<div class="min-w-0">
								<div class="text-xs font-medium text-white truncate">{title}</div>
								<div class="text-[10px] text-white/50 truncate mt-0.5">{description || 'Без описания'}</div>
							</div>
						</div>
					{/if}
				</div>

			<!-- Step 1: Role -->
			{:else if step === 1}
				<div class="space-y-5">
					<div>
						<h1 class="text-xl font-semibold text-gray-900 dark:text-white">Тип задачи</h1>
						<p class="text-xs text-gray-400 mt-1">Влияет на поведение ИИ в пространстве</p>
					</div>

					<div class="grid grid-cols-2 gap-3 pt-2">
						{#each roles as r}
							<button
								class="flex items-start gap-3 p-3 rounded-xl border transition-all text-left overflow-hidden group
									{selectedRole === r.id
										? 'border-white/30 bg-white/10 text-white shadow-lg shadow-white/5'
										: 'border-white/5 hover:border-white/15 bg-[#141414] hover:bg-white/[0.04] text-white/80 shadow-xs'}"
								on:click={() => selectedRole = selectedRole === r.id ? '' : r.id}
							>
								<div class="size-8 rounded-lg {r.bg} {r.color} flex items-center justify-center text-lg shrink-0 group-hover:scale-110 transition-transform duration-300">
									{r.icon}
								</div>
								<div class="flex flex-col min-w-0">
									<span class="text-xs font-medium tracking-wide mt-0.5">{r.label}</span>
									<span class="text-[9px] mt-0.5 leading-tight truncate w-full {selectedRole === r.id ? 'text-white/70' : 'text-white/40'}">{r.sub}</span>
								</div>
							</button>
						{/each}
					</div>

					<p class="text-[10px] text-white/30 text-center uppercase tracking-widest font-medium">Можно пропустить</p>
				</div>

			<!-- Step 2: Settings -->
			{:else if step === 2}
				<div class="space-y-5">
					<div>
						<h1 class="text-xl font-semibold text-gray-900 dark:text-white">Настройка</h1>
						<p class="text-xs text-gray-400 mt-1">Тонкая настройка пространства</p>
					</div>

					<!-- Auto Memory -->
					<div class="flex items-center justify-between p-3.5 rounded-xl border border-white/10 bg-white/5 shadow-sm">
						<div>
							<div class="text-xs font-medium text-white">Автосбор фактов</div>
							<div class="text-[10px] text-white/50 mt-0.5">Mem0 извлекает факты из чатов</div>
						</div>
						<button
							class="w-9 h-5 rounded-full transition-colors duration-200 relative {autoMemory ? 'bg-white' : 'bg-white/10 border border-white/10'}"
							on:click={() => autoMemory = !autoMemory}
						>
							<div class="absolute top-0.5 size-4 rounded-full shadow-sm transition-all duration-200 {autoMemory ? 'left-[18px] bg-black' : 'left-0.5 bg-white/60'}"></div>
						</button>
					</div>

					<!-- Model -->
					<div class="p-3.5 rounded-xl border border-white/10 bg-white/5 shadow-sm">
						<div class="text-xs font-medium text-white mb-2">Модель по умолчанию</div>
						<select
							bind:value={selectedModel}
							class="w-full px-2.5 py-1.5 rounded-lg bg-black/40 border border-white/10 text-white/90 text-xs outline-none"
						>
							<option value="">Авто</option>
							{#each $_models as model}
								<option value={model.id}>{model.name || model.id}</option>
							{/each}
						</select>
					</div>
				</div>

			<!-- Step 3: Done -->
			{:else if step === 3}
				<div class="text-center py-8 space-y-4">
					{#if submitting}
						<div class="inline-flex size-10 border-2 border-white/10 border-t-white rounded-full animate-spin"></div>
						<p class="text-sm text-white/50">Создаём...</p>
					{:else}
						<div class="inline-flex size-14 rounded-xl bg-gray-800 items-center justify-center text-3xl shadow-lg border border-white/5 animate-pop">
							{spaceEmoji(title)}
						</div>
						<div>
							<h2 class="text-lg font-semibold text-white">{title}</h2>
							<p class="text-xs text-white/50 mt-1">Пространство создано. Память подключена.</p>
						</div>
						<button
							class="mt-4 px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-medium border border-white/10 transition"
							on:click={() => goto('/')}
						>
							Начать работу →
						</button>
					{/if}
				</div>
			{/if}
		</div>
		{/key}

		<!-- Nav -->
		{#if step < 3}
			<div class="flex justify-between items-center mt-8">
				{#if step > 0}
					<button class="text-xs text-white/40 hover:text-white/80 transition" on:click={back}>← Назад</button>
				{:else}
					<button class="text-xs text-white/40 hover:text-white/80 transition" on:click={() => goto('/')}>Отмена</button>
				{/if}
				<button
					class="px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-medium border border-white/10 transition disabled:opacity-30 flex items-center gap-2"
					disabled={!canNext}
					on:click={next}
				>
					{step === 2 ? 'Создать' : 'Далее →'}
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	@keyframes pop { 0% { transform: scale(0); } 60% { transform: scale(1.1); } 100% { transform: scale(1); } }
	.animate-pop { animation: pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
</style>
