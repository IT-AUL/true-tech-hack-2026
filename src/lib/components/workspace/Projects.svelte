<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { WEBUI_NAME, projects, user } from '$lib/stores';
	import { getProjects, createNewProject, deleteProjectById } from '$lib/apis/projects';

	import { capitalizeFirstLetter } from '$lib/utils';

	import DeleteConfirmDialog from '../common/ConfirmDialog.svelte';
	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import XMark from '../icons/XMark.svelte';
	import ProjectDetails from './Projects/ProjectDetails.svelte';
	import Modal from '../common/Modal.svelte';

	let loaded = false;
	let showDeleteConfirm = false;
	let selectedProject = null;
	let showDetails = false;

	let showCreateModal = false;
	let newProjectTitle = '';
	let newProjectDescription = '';
	let isCreating = false;

	let query = '';

	$: filteredItems = $projects.filter((item) =>
		item.title.toLowerCase().includes(query.toLowerCase())
	);

	const init = async () => {
		const res = await getProjects(localStorage.token).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (res) {
			projects.set(res);
		}
		loaded = true;
	};

	const openCreateModal = () => {
		newProjectTitle = '';
		newProjectDescription = '';
		showCreateModal = true;
	};

	const submitCreateProject = async () => {
		if (!newProjectTitle.trim()) {
			toast.error($i18n.t('Enter project title'));
			return;
		}

		isCreating = true;
		const res = await createNewProject(localStorage.token, newProjectTitle.trim(), newProjectDescription.trim()).catch((e) => {
			toast.error(`${e}`);
		});
		isCreating = false;

		if (res) {
			toast.success($i18n.t('Project created successfully.'));
			showCreateModal = false;
			init();
		}
	};

	const deleteHandler = async (item) => {
		const res = await deleteProjectById(localStorage.token, item.id).catch((e) => {
			toast.error(`${e}`);
		});

		if (res) {
			toast.success($i18n.t('Project deleted successfully.'));
			init();
		}
	};

	onMount(async () => {
		await init();
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Projects')} • {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		on:confirm={() => {
			deleteHandler(selectedProject);
		}}
	/>

	<Modal size="sm" bind:show={showCreateModal}>
		<div class="px-5 py-5 sm:p-6 bg-white dark:bg-gray-900 rounded-[24px]">
			<div class="flex justify-between items-center mb-6">
				<h3 class="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
					<div class="size-8 rounded-full bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center text-indigo-500">
						<Plus className="size-4" strokeWidth="2.5" />
					</div>
					Новое пространство
				</h3>
				<button 
					type="button" 
					class="p-1 rounded-full text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
					on:click={() => showCreateModal = false}
				>
					<XMark className="size-4" strokeWidth="2.5" />
				</button>
			</div>

			<form on:submit|preventDefault={submitCreateProject} class="space-y-4">
				<div>
					<label for="project-title" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
						Название
					</label>
					<input
						id="project-title"
						type="text"
						bind:value={newProjectTitle}
						placeholder="Например: Маркетинг Q3"
						class="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all placeholder:text-gray-400 text-sm"
						autofocus
					/>
				</div>

				<div>
					<label for="project-desc" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1.5">
						Описание <span class="text-gray-400 font-normal">(опционально)</span>
					</label>
					<textarea
						id="project-desc"
						bind:value={newProjectDescription}
						placeholder="Кратко опишите цель этого пространства..."
						rows="3"
						class="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all placeholder:text-gray-400 text-sm resize-none"
					></textarea>
				</div>

				<div class="pt-4 flex justify-end gap-2">
					<button
						type="button"
						class="px-4 py-2 font-medium text-sm text-gray-600 hover:text-gray-900 bg-transparent hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-800 rounded-xl transition"
						on:click={() => showCreateModal = false}
					>
						Отмена
					</button>
					<button
						type="submit"
						disabled={!newProjectTitle.trim() || isCreating}
						class="px-5 py-2 font-medium text-sm text-white bg-black hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 rounded-xl transition shadow-sm active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
					>
						{#if isCreating}
							<Spinner className="size-4" />
							Создание...
						{:else}
							Создать
						{/if}
					</button>
				</div>
			</form>
		</div>
	</Modal>

	{#if showDetails && selectedProject}
		<ProjectDetails
			project={selectedProject}
			onClose={() => {
				showDetails = false;
				selectedProject = null;
				init();
			}}
		/>
	{:else}
		<div class="flex flex-col gap-1 px-1 mt-1.5 mb-3">
			<div class="flex justify-between items-center">
				<div class="flex items-center md:self-center text-xl font-medium px-0.5 gap-2 shrink-0">
					<div>
						{$i18n.t('Projects')}
					</div>

					<div class="text-lg font-medium text-gray-500 dark:text-gray-500">
						{filteredItems.length}
					</div>
				</div>

				<div class="flex w-full justify-end gap-1.5">
					<button
						class=" px-2 py-1.5 rounded-xl bg-black text-white dark:bg-white dark:text-black transition font-medium text-sm flex items-center"
						on:click={openCreateModal}
					>
						<Plus className="size-3" strokeWidth="2.5" />
						<div class=" hidden md:block md:ml-1 text-xs">{$i18n.t('New Project')}</div>
					</button>
				</div>
			</div>
		</div>

		<div
			class="py-2 bg-white dark:bg-gray-900 rounded-3xl border border-gray-100/30 dark:border-gray-850/30 text-sm"
		>
			<div class=" flex w-full space-x-2 py-0.5 px-3.5 pb-2">
				<div class="flex flex-1">
					<div class=" self-center ml-1 mr-3">
						<Search className="size-3.5" />
					</div>
					<input
						class=" w-full text-sm py-1 rounded-r-xl outline-hidden bg-transparent"
						bind:value={query}
						aria-label={$i18n.t('Search Projects')}
						placeholder={$i18n.t('Search Projects')}
					/>
					{#if query}
						<div class="self-center pl-1.5 translate-y-[0.5px] rounded-l-xl bg-transparent">
							<button
								class="p-0.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-900 transition"
								aria-label={$i18n.t('Clear search')}
								on:click={() => {
									query = '';
								}}
							>
								<XMark className="size-3" strokeWidth="2" />
							</button>
						</div>
					{/if}
				</div>
			</div>

			{#if filteredItems.length > 0}
				<div class=" my-2 px-3 grid grid-cols-1 lg:grid-cols-2 gap-2">
					{#each filteredItems as item}
						<div
							role="button"
							tabindex="0"
							class=" flex flex-col cursor-pointer text-left w-full px-4 py-3 dark:hover:bg-gray-850/50 hover:bg-gray-50 transition rounded-2xl border border-gray-100/50 dark:border-gray-800/50"
							on:click={() => {
								selectedProject = item;
								showDetails = true;
							}}
							on:keydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									selectedProject = item;
									showDetails = true;
								}
							}}
						>
							<div class="flex justify-between items-start w-full">
								<div class="font-semibold text-base capitalize">{item.title}</div>
								<div class="flex gap-2">
									<button
										class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 rounded-lg transition"
										on:click|stopPropagation={() => {
											selectedProject = item;
											showDeleteConfirm = true;
										}}
									>
										<XMark className="size-4" />
									</button>
								</div>
							</div>
							{#if item.description}
								<div class="text-xs text-gray-500 mt-1 line-clamp-2">{item.description}</div>
							{/if}
							<div class="mt-3 flex items-center gap-2">
								<div
									class="text-[10px] bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full text-gray-500 uppercase tracking-tighter font-bold"
								>
									Project ID: {item.id.substring(0, 8)}...
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class=" w-full h-full flex flex-col justify-center items-center my-16 mb-24">
					<div class="max-w-md text-center">
						<div class=" text-3xl mb-3">📁</div>
						<div class=" text-lg font-medium mb-1">{$i18n.t('No projects found')}</div>
						<div class=" text-gray-500 text-center text-xs">
							{$i18n.t(
								'Create a project to start using long-term memory scoped to specific tasks.'
							)}
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<div class=" text-gray-500 text-xs m-2">
		ⓘ {$i18n.t('Assign chats to a project to share long-term memory context between them.')}
	</div>
{:else}
	<div class="w-full h-full flex justify-center items-center">
		<Spinner className="size-5" />
	</div>
{/if}
