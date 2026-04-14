<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	const i18n = getContext('i18n');

	import {
		getProjectMemory,
		getProjectChats,
		wipeProjectMemory,
		deleteProjectMemoryById,
		updateProjectById
	} from '$lib/apis/projects';
	import { selectedProjectId } from '$lib/stores';
	import { goto } from '$app/navigation';

	import ChevronLeft from '../../icons/ChevronLeft.svelte';
	import GarbageBin from '../../icons/GarbageBin.svelte';
	import Spinner from '../../common/Spinner.svelte';
	import Tooltip from '../../common/Tooltip.svelte';
	import Pencil from '../../icons/Pencil.svelte';
	import Check from '../../icons/Check.svelte';
	import ChatBubble from '../../icons/ChatBubble.svelte';

	export let project;
	export let onClose: Function;

	let loaded = false;
	let memories = [];
	let projectChats = [];
	let activeTab = 'memory'; // 'memory' or 'chats'

	let editTitle = false;
	let title = project.title;
	let description = project.description;

	const init = async () => {
		loaded = false;
		
		// Load Memory
		const memRes = await getProjectMemory(localStorage.token, project.id).catch((e) => {
			toast.error(`${e}`);
			return { memories: [] };
		});
		memories = memRes?.memories || [];

		// Load Chats
		const chatRes = await getProjectChats(localStorage.token, project.id).catch((e) => {
			console.error(e);
			return [];
		});
		projectChats = chatRes || [];

		loaded = true;
	};

	const saveProject = async () => {
		const res = await updateProjectById(localStorage.token, project.id, title, description).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (res) {
			project = res;
			editTitle = false;
			toast.success($i18n.t('Project updated.'));
		}
	};

	const wipeMemoryHandler = async () => {
		if (confirm($i18n.t('Are you sure you want to wipe all memory for this project? This cannot be undone.'))) {
			const res = await wipeProjectMemory(localStorage.token, project.id).catch((e) => {
				toast.error(`${e}`);
			});

			if (res) {
				toast.success($i18n.t('Project memory wiped.'));
				init();
			}
		}
	};

	const deleteMemoryItem = async (memoryId) => {
		const res = await deleteProjectMemoryById(localStorage.token, project.id, memoryId).catch((e) => {
			toast.error(`${e}`);
		});

		if (res) {
			toast.success($i18n.t('Memory point deleted.'));
			init();
		}
	};

	onMount(async () => {
		await init();
	});
</script>

<div class="flex flex-col gap-4">
	<div class="flex items-center gap-2">
		<button
			class="p-2 hover:bg-gray-100 dark:hover:bg-gray-850 rounded-full transition"
			on:click={onClose}
		>
			<ChevronLeft className="size-5" />
		</button>
		<div class="flex-1">
			{#if editTitle}
				<div class="flex gap-2 w-full max-w-lg">
					<input
						class="text-xl font-medium bg-transparent border-b border-gray-500 outline-hidden w-full"
						bind:value={title}
					/>
					<button class="p-1 hover:text-green-500" on:click={saveProject}>
						<Check className="size-5" />
					</button>
				</div>
			{:else}
				<div class="flex items-center gap-2">
					<h2 class="text-xl font-medium capitalize">{project.title}</h2>
					<button
						class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
						on:click={() => (editTitle = true)}
					>
						<Pencil className="size-4" />
					</button>
				</div>
			{/if}
			<div class="text-xs text-gray-500 font-mono mt-1">ID: {project.id}</div>
		</div>

		<div class="flex items-center gap-2">
			<button
				class="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition shadow-sm"
				on:click={async () => {
					selectedProjectId.set(project.id);
					await goto('/');
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="size-3.5"
				>
					<path
						fill-rule="evenodd"
						d="M10 2c-2.236 0-4.43.18-6.57.532a.75.75 0 0 0-.626.629C2.49 4.23 2 5.922 2 7.75c0 1.258.232 2.463.654 3.575a.75.75 0 0 0 .546.467c1.173.235 2.378.396 3.606.483l.113 1.584c.026.36.273.66.613.77a6.67 6.67 0 0 0 4.936 0 .8.8 0 0 0 .612-.77l.113-1.584c1.228-.087 2.433-.248 3.606-.483a.75.75 0 0 0 .546-.467c.422-1.112.654-2.317.654-3.575 0-1.828-.49-3.52-1.304-4.589a.75.75 0 0 0-.626-.63C14.43 2.18 12.236 2 10 2ZM6.345 5.71a.75.75 0 0 1 .71-.787c.404-.016.804-.047 1.198-.093a.75.75 0 1 1 .174 1.49c-.324.038-.652.064-.985.078a.75.75 0 0 1-.797-.69Zm5.397.61a.75.75 0 1 0 .174-1.49 14.59 14.59 0 0 0-1.198.093.75.75 0 1 0 .174 1.49c.28-.033.565-.059.85-.078Z"
						clip-rule="evenodd"
					/>
				</svg>
				{$i18n.t('Start Chat')}
			</button>

			<button
				class="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition"
				on:click={wipeMemoryHandler}
			>
				<GarbageBin className="size-3.5" />
				{$i18n.t('Wipe Memory')}
			</button>
		</div>
	</div>

	<!-- Tabs Navigation -->
	<div class="flex gap-4 border-b border-gray-100 dark:border-gray-850 px-2 mt-2">
		<button 
			class="pb-2 text-sm font-medium transition-colors {activeTab === 'memory' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
			on:click={() => activeTab = 'memory'}
		>
			{$i18n.t('Long-Term Memory')}
		</button>
		<button 
			class="pb-2 text-sm font-medium transition-colors {activeTab === 'chats' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
			on:click={() => activeTab = 'chats'}
		>
			{$i18n.t('Project Chats')} ({projectChats.length})
		</button>
	</div>

	<div class="grid grid-cols-1">
		{#if activeTab === 'memory'}
			<div class="p-4 bg-white dark:bg-gray-900 rounded-b-3xl border-x border-b border-gray-100/30 dark:border-gray-850/30">
				<div class="flex justify-between items-center mb-4 px-2">
					<h3 class="font-medium text-sm flex items-center gap-2">
						{$i18n.t('Extracted Knowledge')}
						<span class="text-[10px] bg-blue-100 dark:bg-blue-900/40 text-blue-600 px-1.5 py-0.5 rounded-full uppercase">Mem0</span>
					</h3>
					<div class="text-xs text-gray-500">
						{memories.length} {$i18n.t('facts')}
					</div>
				</div>

				{#if !loaded}
					<div class="flex justify-center py-10">
						<Spinner className="size-5" />
					</div>
				{:else if memories.length > 0}
					<div class="flex flex-col gap-2">
						{#each memories as memory}
							<div class="group flex justify-between items-center bg-gray-50 dark:bg-gray-850/30 p-3 rounded-2xl border border-gray-100/10 dark:border-gray-800/10">
								<div class="text-sm flex-1 pr-4">
									{memory.text || memory.memory || 'No fact description'}
								</div>
								<div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition">
									<button class="p-1.5 hover:text-red-500 rounded-lg transition" on:click={() => deleteMemoryItem(memory.id)}>
										<GarbageBin className="size-3.5" />
									</button>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center py-12 text-gray-500">
						<div class="text-2xl mb-2">🧠</div>
						<div class="text-xs font-medium">{$i18n.t('No facts extracted yet.')}</div>
						<div class="text-[10px] text-center mt-1 px-10">
							{$i18n.t('Start chatting in this project and the AI will automatically store facts about your work.')}
						</div>
					</div>
				{/if}
			</div>
		{:else}
			<div class="p-4 bg-white dark:bg-gray-900 rounded-b-3xl border-x border-b border-gray-100/30 dark:border-gray-850/30">
				{#if !loaded}
					<div class="flex justify-center py-10">
						<Spinner className="size-5" />
					</div>
				{:else if projectChats.length > 0}
					<div class="flex flex-col gap-2">
						{#each projectChats as chat}
							<button 
								class="flex items-center gap-3 bg-gray-50 dark:bg-gray-850/30 p-3 rounded-2xl border border-gray-100/10 dark:border-gray-800/10 hover:bg-gray-100 dark:hover:bg-gray-800 transition text-left"
								on:click={() => goto(`/c/${chat.id}`)}
							>
								<ChatBubble className="size-4 text-gray-400" />
								<div class="flex-1 min-w-0">
									<div class="text-sm font-medium truncate">{chat.title}</div>
									<div class="text-[10px] text-gray-500">{new Date(chat.updated_at * 1000).toLocaleString()}</div>
								</div>
							</button>
						{/each}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center py-12 text-gray-500">
						<div class="text-2xl mb-2">💬</div>
						<div class="text-xs font-medium">{$i18n.t('No chats in this project yet.')}</div>
						<button 
							class="mt-4 px-4 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition"
							on:click={() => {
								selectedProjectId.set(project.id);
								goto('/');
							}}
						>
							+ {$i18n.t('Create First Chat')}
						</button>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
