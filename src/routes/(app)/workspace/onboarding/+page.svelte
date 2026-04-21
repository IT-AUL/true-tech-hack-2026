<script lang="ts">
	import { goto } from '$app/navigation';
	import { getContext } from 'svelte';
	import { createNewProject, getProjects } from '$lib/apis/projects';
	import { projects, selectedProjectId } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	let title = '';
	let description = '';
	let role = '';
	let isSubmitting = false;

	const roles = [
		{ id: 'dev', name: 'Разработчик', desc: 'Код, архитектура, дебаг', icon: 'M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5' },
		{ id: 'product', name: 'Продакт', desc: 'PRD, Аналитика, Метрики', icon: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z' },
		{ id: 'design', name: 'Дизайнер', desc: 'UI/UX, Брендбук, Ассеты', icon: 'M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42' }
	];

	const handleSubmit = async () => {
		if (!title.trim()) {
			toast.error('Введите название пространства');
			return;
		}
		isSubmitting = true;

		const roleText = roles.find(r => r.id === role)?.name || '';
		const fullDescription = roleText ? `Роль: ${roleText}. ${description}` : description;

		const res = await createNewProject(localStorage.token, title, fullDescription).catch((e) => {
			toast.error(`${e}`);
			isSubmitting = false;
			return null;
		});

		if (res) {
			const loadedProjects = await getProjects(localStorage.token);
			projects.set(loadedProjects);
			selectedProjectId.set(res.id);
			toast.success('Пространство создано!');
			goto('/');
		}
	};
</script>

<div class="w-full h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 p-4">
	<div class="max-w-xl w-full bg-white dark:bg-gray-900 rounded-3xl shadow-xl border border-gray-100 dark:border-gray-800 p-8 overflow-hidden relative">

		<!-- Decorative Background -->
		<div class="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 dark:opacity-20"></div>
		<div class="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 bg-emerald-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 dark:opacity-20"></div>

		<div class="relative z-10">
			<div class="text-center mb-8">
				<div class="inline-flex items-center justify-center size-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl shadow-lg mb-4">
					<img src="/static/vibehub_v_icon.svg" class="size-7 invert" alt="VibeHub" />
				</div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-1">Создайте первое Пространство</h1>
				<p class="text-gray-500 dark:text-gray-400 text-sm">ИИ будет накапливать контекст внутри пространства, создавая долгосрочную память.</p>
			</div>

			<form on:submit|preventDefault={handleSubmit} class="space-y-5">
				<!-- Role Selection -->
				<div>
					<label class="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Ваша роль (опционально)</label>
					<div class="grid grid-cols-3 gap-2">
						{#each roles as r}
							<button
								type="button"
								class="flex flex-col items-center p-3 rounded-xl border-2 transition-all {role === r.id ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20' : 'border-gray-100 dark:border-gray-800 hover:border-gray-200 dark:hover:border-gray-700'}"
								on:click={() => role = role === r.id ? '' : r.id}
							>
								<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6 mb-1.5 {role === r.id ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400'}">
									<path stroke-linecap="round" stroke-linejoin="round" d={r.icon} />
								</svg>
								<span class="font-medium text-xs text-gray-900 dark:text-white">{r.name}</span>
								<span class="text-[9px] text-gray-400 text-center mt-0.5">{r.desc}</span>
							</button>
						{/each}
					</div>
				</div>

				<!-- Workspace Info -->
				<div class="space-y-3">
					<div>
						<label for="title" class="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">Название</label>
						<input
							type="text"
							id="title"
							bind:value={title}
							class="w-full px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition text-sm"
							placeholder="Frontend Релиз v2.0"
							required
						/>
					</div>

					<div>
						<label for="desc" class="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">Описание (опционально)</label>
						<textarea
							id="desc"
							bind:value={description}
							class="w-full px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition resize-none h-20 text-sm"
							placeholder="Опишите задачи и контекст проекта..."
						></textarea>
					</div>
				</div>

				<button
					type="submit"
					disabled={isSubmitting || !title.trim()}
					class="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white rounded-xl font-semibold transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2 text-sm"
				>
					{#if isSubmitting}
						<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
						Создаем...
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
						</svg>
						Создать пространство
					{/if}
				</button>
			</form>

			<div class="mt-4 text-center">
				<button class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition" on:click={() => goto('/')}>
					Пропустить →
				</button>
			</div>
		</div>
	</div>
</div>
