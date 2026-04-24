<script lang="ts">
	import { getContext, onMount, onDestroy } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { getProjectMemory, getProjectChats, getProjectFiles, wipeProjectMemory, deleteProjectMemoryById } from '$lib/apis/projects';
	import { goto } from '$app/navigation';
	import { selectedProjectId, projects, showSidebar, mobile } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import ChatGraph from './ChatGraph.svelte';
	import Sidebar from '../icons/Sidebar.svelte';

	export let project = null;

	const i18n = getContext('i18n');

	let memory = [];
	let projectChats = [];
	let projectFiles = [];
	let loading = true;
	let memorySearch = '';
	let fileSearch = '';
	
	let memCount = 0;
	let chatCount = 0;
	let fileCount = 0;
	
	let showGraphFullscreen = false;
	let newFactText = '';

	import { getSpaceEmoji } from '$lib/utils';


	// Graph modal controls
	let graphSearch = '';
	let graphShowChats = true;
	let graphShowMemory = true;
	let graphColorRecency = true;

	// Portal: render modal outside component tree so it's not clipped by parent overflow/z-index
	let portalTarget: HTMLDivElement | null = null;
	function createPortal() {
		if (portalTarget) return;
		portalTarget = document.createElement('div');
		portalTarget.id = 'graph-modal-portal';
		document.body.appendChild(portalTarget);
	}
	function destroyPortal() {
		if (portalTarget) { portalTarget.remove(); portalTarget = null; }
	}
	function portal(node: HTMLElement) {
		createPortal();
		portalTarget!.appendChild(node);
		return {
			destroy() { node.remove(); destroyPortal(); }
		};
	}
	onDestroy(destroyPortal);

	// Close graph modal when switching spaces
	$: if (project) {
		showGraphFullscreen = false;
		loadAll();
	}

	async function loadAll() {
		loading = true;
		const [memRes, chatRes, fileRes] = await Promise.all([
			getProjectMemory(localStorage.token, project.id).catch(() => null),
			getProjectChats(localStorage.token, project.id).catch(() => []),
			getProjectFiles(localStorage.token, project.id).catch(() => [])
		]);
		memory = Array.isArray(memRes?.memories) ? memRes.memories : Array.isArray(memRes) ? memRes : [];
		projectChats = Array.isArray(chatRes) ? chatRes : [];
		projectFiles = Array.isArray(fileRes) ? fileRes : [];
		loading = false;
		
		memCount = memory.length;
		chatCount = projectChats.length;
		fileCount = projectFiles.length;
	}

	$: filteredMemory = memory.filter(m => {
		if (!memorySearch) return true;
		return ((m.text || m.memory || '') as string).toLowerCase().includes(memorySearch.toLowerCase());
	});

	async function wipeMemory() {
		if (!confirm('Вы уверены, что хотите полностью стереть базу знаний пространства? Отменить нельзя.')) return;
		await wipeProjectMemory(localStorage.token, project.id).catch(e => toast.error(`${e}`));
		toast.success('База знаний пространства очищена');
		loadAll();
	}

	async function deleteFact(id: string) {
		await deleteProjectMemoryById(localStorage.token, project.id, id).catch(e => toast.error(`${e}`));
		memory = memory.filter(m => m.id !== id);
	}

	async function handleAddFact(e) {
		if (e.key === 'Enter' && newFactText.trim()) {
			toast.success('Mock: Факт добавлен в память (Backend API в разработке)');
			memory = [{ id: Math.random().toString(), text: newFactText, updated_at: Date.now()/1000 }, ...memory];
			newFactText = '';
		}
	}

	function getLastActivityStr(chats) {
		if (!chats || chats.length === 0) return 'Активности нет';
		const dates = chats.map(c => safeDate(c.updated_at)).filter(Boolean) as Date[];
		if (dates.length === 0) return 'Активности нет';
		const latest = Math.max(...dates.map(d => d.getTime()));
		const diffHours = Math.round((Date.now() - latest) / 3600000);
		if (diffHours < 1) return `только что`;
		if (diffHours < 24) return `${diffHours}ч назад`;
		return `${Math.round(diffHours/24)}д назад`;
	}

	// CRITICAL FIX: Reactivity relies on parameters
	function getGroupedChats(chats) {
		const groups = { today: [], week: [], older: [] };
		if (!chats) return groups;
		const now = Date.now() / 1000;
		chats.forEach(chat => {
			const d = safeDate(chat.updated_at);
			const diff = d ? (Date.now() - d.getTime()) / 1000 : 999999;
			if (diff < 86400) groups.today.push(chat);
			else if (diff < 86400 * 7) groups.week.push(chat);
			else groups.older.push(chat);
		});
		return groups;
	}

	$: groupedChats = getGroupedChats(projectChats);
	$: lastActiveStr = getLastActivityStr(projectChats);

	function isStale(timestamp) {
		const d = safeDate(timestamp);
		if (!d) return false;
		const thirtyDays = 30 * 24 * 3600 * 1000;
		return (Date.now() - d.getTime()) > thirtyDays;
	}

	function safeDate(val: any): Date | null {
		if (!val) return null;
		// Try as unix seconds (number < 2e10)
		if (typeof val === 'number' && val < 2e10) {
			const d = new Date(val * 1000);
			return isNaN(d.getTime()) ? null : d;
		}
		// Try as unix milliseconds
		if (typeof val === 'number') {
			const d = new Date(val);
			return isNaN(d.getTime()) ? null : d;
		}
		// Try as ISO string
		const d = new Date(val);
		return isNaN(d.getTime()) ? null : d;
	}

	function formatDate(val: any): string {
		const d = safeDate(val);
		if (!d) return '—';
		return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
	}

</script>

{#if project}
<div class="relative w-full flex-1 flex flex-col bg-slate-50 dark:bg-[#080808] text-gray-900 dark:text-white overflow-hidden font-sans transition-colors duration-300" in:fade={{ duration: 150 }}>
	
	<!-- Premium Subtle Background Effects -->
	<div class="absolute inset-0 z-0 pointer-events-none overflow-hidden">
		<!-- Light soft blobs -->
		<div class="absolute top-[-10%] right-[-5%] w-[40vw] h-[40vw] rounded-full bg-violet-400/20 dark:bg-violet-600/10 blur-[100px]"></div>
		<div class="absolute bottom-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-sky-400/20 dark:bg-sky-600/10 blur-[120px]"></div>
	</div>

	<!-- Header -->
	<div id="tour-space-header" class="relative z-10 w-full px-8 py-5 border-b border-gray-200/50 dark:border-white/[0.04] flex items-center justify-between bg-white/40 dark:bg-black/20 backdrop-blur-3xl transition-colors">
		<div class="flex items-center gap-4">
			{#if $mobile && !$showSidebar}
				<button class="text-gray-500 hover:text-gray-900 dark:text-white/60 dark:hover:text-white transition" on:click={() => showSidebar.set(!$showSidebar)}>
					<Sidebar className="size-5" />
				</button>
			{/if}
			
			<div class="size-11 rounded-xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-2xl shadow-sm">
				{getSpaceEmoji(project.title)}
			</div>
			
			<div>
				<h1 class="text-xl font-bold tracking-tight text-gray-900 dark:text-white/95">{project.title}</h1>
				<div class="flex items-center gap-3 mt-0.5">
					<span class="text-[11px] text-gray-400 dark:text-white/30 font-medium">{chatCount} чатов · {memCount} фактов · {fileCount} файлов · обновлено {lastActiveStr}</span>
				</div>
			</div>
		</div>

		<button id="tour-space-mindmap" class="flex items-center gap-2 px-4 py-2 font-medium text-xs text-white bg-gray-900 hover:bg-gray-800 dark:bg-white/[0.06] dark:hover:bg-white/[0.1] dark:text-white/80 rounded-xl border border-gray-800 dark:border-white/[0.08] transition-all shadow-sm" on:click={() => showGraphFullscreen = true}>
			<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6zM13.5 10.5H21a7.5 7.5 0 00-7.5-7.5v7.5z" /></svg>
			Карта знаний
		</button>
	</div>

	<!-- Main Stage -->
	<div class="relative z-10 flex-1 flex min-h-0 bg-transparent">
		
		<!-- Left: Chat Stream (65%) -->
		<div id="tour-space-chats" class="flex-1 min-w-0 px-8 py-6 overflow-y-auto scrollbar-hidden">
			<div class="max-w-4xl max-w-[850px] mx-auto flex flex-col h-full">
				<!-- Slot for the Prompt Input -->
				<slot name="prompt"></slot>
				
				<div class="flex items-center justify-between mb-8">
					<h2 class="text-lg font-bold text-gray-900 dark:text-white/90 font-mono tracking-tight uppercase"><span class="text-violet-500 dark:text-violet-400 mr-2">/</span>Чаты проекта</h2>
					<div class="text-[10px] font-bold tracking-widest text-gray-400 dark:text-white/40 uppercase">{chatCount} активных</div>
				</div>

				{#if loading}
					<div class="space-y-4">
						<div class="h-28 bg-white dark:bg-white/[0.02] border border-gray-200 dark:border-white/[0.05] rounded-2xl animate-pulse"></div>
						<div class="h-28 bg-white dark:bg-white/[0.02] border border-gray-200 dark:border-white/[0.05] rounded-2xl animate-pulse opacity-70"></div>
					</div>
				{:else if projectChats.length > 0}
					<div class="space-y-12">
						{#if groupedChats.today.length > 0}
							<div>
								<h3 class="text-xs font-bold text-gray-400 dark:text-white/30 uppercase tracking-[0.2em] mb-4 pl-1">Сегодня</h3>
								<div class="space-y-3">
									{#each groupedChats.today as chat, idx}
										<div class="group relative w-full p-6 rounded-2xl border border-gray-200 dark:border-white/[0.08] bg-white dark:bg-white/[0.03] drop-shadow-sm dark:drop-shadow-none hover:shadow-lg dark:hover:bg-white/[0.06] dark:hover:border-white/[0.15] transition-all duration-300 cursor-pointer overflow-hidden backdrop-blur-sm" on:click={() => goto(`/c/${chat.id}`)}>
											<div class="absolute inset-0 bg-gradient-to-r from-violet-500 to-indigo-600 opacity-0 group-hover:opacity-[0.03] transition-opacity duration-500"></div>
											<div class="relative z-10 flex flex-col gap-3">
												<div class="flex items-start justify-between gap-4">
													<div class="text-lg font-bold text-gray-900 dark:text-white truncate pr-6 group-hover:text-black dark:group-hover:text-white transition-colors">{chat.title}</div>
													{#if idx === 0}
														<span class="shrink-0 text-[11px] font-bold uppercase tracking-wider bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300 px-3 py-1.5 rounded-lg border border-violet-200 dark:border-violet-500/30">Продолжить</span>
													{/if}
												</div>
													<div class="flex items-center justify-between mt-1">
													<div class="flex gap-2">
														{#if chat.tags && chat.tags.length > 0}
															{#each chat.tags.slice(0,3) as tag}
																<span class="text-[10px] font-medium text-gray-500 dark:text-white/60 bg-gray-100 dark:bg-white/5 px-2 py-0.5 rounded-md border border-gray-200 dark:border-white/10">{tag.name || tag}</span>
															{/each}
														{:else}
															<span class="text-[10px] font-medium text-gray-400 dark:text-white/30 bg-gray-50 dark:bg-white/[0.02] px-2 py-0.5 rounded-md border border-gray-200 dark:border-white/[0.05]">Общий</span>
														{/if}
													</div>
													<div class="text-[10px] font-medium text-gray-400 dark:text-white/30 bg-gray-50 dark:bg-white/5 px-2 py-1 rounded-md">{safeDate(chat.updated_at)?.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'}) ?? '—'}</div>
												</div>
											</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						{#if groupedChats.week.length > 0}
							<div>
								<h3 class="text-xs font-bold text-gray-400 dark:text-white/30 uppercase tracking-[0.2em] mb-4 pl-1">На этой неделе</h3>
								<div class="space-y-3 opacity-90 dark:opacity-80 group-hover/list:opacity-100 transition-opacity">
									{#each groupedChats.week as chat}
										<div class="group relative w-full p-5 rounded-xl border border-gray-300/80 dark:border-white/[0.06] bg-white dark:bg-white/[0.02] hover:bg-white dark:hover:bg-white/[0.05] hover:border-gray-400 dark:hover:border-white/[0.12] transition-all cursor-pointer backdrop-blur-sm shadow-sm" on:click={() => goto(`/c/${chat.id}`)}>
											<div class="flex items-center justify-between gap-4">
												<div class="text-base font-semibold text-gray-800 dark:text-white/90 truncate group-hover:text-gray-900 dark:group-hover:text-white transition-colors">{chat.title}</div>
												<div class="flex items-center gap-3">
													<div class="flex gap-1.5 hidden sm:flex">
														{#if chat.tags}
															{#each chat.tags.slice(0,2) as tag}
																<span class="text-[9px] text-gray-400 dark:text-white/40 bg-gray-50 dark:bg-white/5 px-1.5 py-0.5 rounded border border-gray-100 dark:border-white-10/5">{tag.name || tag}</span>
															{/each}
														{/if}
													</div>
													<div class="text-[10px] text-gray-400 dark:text-white/30 font-medium">{safeDate(chat.updated_at)?.toLocaleDateString('ru-RU', {weekday: 'short'}) ?? '—'}</div>
												</div>
											</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center py-32 text-center">
						<div class="p-6 rounded-3xl bg-gray-100 dark:bg-white/[0.01] border border-gray-200 dark:border-white/[0.03] shadow-md dark:shadow-2xl mb-5">
							<svg class="size-10 text-gray-400 dark:text-white/20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4m18-4l-8.5-8.5a1.5 1.5 0 0 0-2 0L3 11"/></svg>
						</div>
						<h3 class="text-xl font-bold text-gray-900 dark:text-white/90 mb-2">Здесь появятся рабочие обсуждения</h3>
						<p class="text-gray-500 dark:text-white/40 max-w-sm mx-auto mb-8 font-medium">Создайте первый чат, чтобы начать собирать контекст пространства.</p>
						<button class="px-8 py-3 bg-violet-600 hover:bg-violet-700 text-white font-bold rounded-2xl shadow-lg shadow-violet-500/20 transition active:scale-95" on:click={() => {
							const input = document.getElementById('tour-chat-input');
							if (input) input.scrollIntoView({ behavior: 'smooth' });
						}}>Новый чат</button>
					</div>
				{/if}
			</div>
		</div>

			<!-- Right: Knowledge Base -->
		<div id="tour-space-memory" class="w-[380px] shrink-0 border-l border-gray-200/60 dark:border-white/[0.04] bg-white/40 dark:bg-white/[0.01] flex flex-col h-full backdrop-blur-md">
			<div class="px-5 py-4 border-b border-gray-200/60 dark:border-white/[0.03]">
				<div class="flex items-center justify-between mb-3">
					<h2 class="text-xs font-bold text-gray-900 dark:text-white/90 tracking-widest uppercase flex items-center gap-2">
						<svg class="size-3.5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/></svg>
						Память и артефакты
						<span class="text-gray-400 dark:text-white/30 text-[10px] font-medium">· {filteredMemory.length + projectFiles.length}</span>
					</h2>
					<button class="text-[9px] uppercase font-bold tracking-widest text-red-500/60 hover:text-red-600 dark:text-red-500/40 dark:hover:text-red-400 px-2 py-0.5 rounded hover:bg-red-50 dark:hover:bg-red-500/5 transition" on:click={wipeMemory}>Очистить</button>
				</div>
				<div class="flex gap-2">
					<input type="text" class="flex-1 bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/[0.08] focus:border-emerald-500/50 rounded-lg pl-3 pr-3 py-2 text-xs text-gray-900 dark:text-white/90 placeholder:text-gray-400 dark:placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-emerald-500/20 transition-all" placeholder="Добавить факт..." bind:value={newFactText} on:keydown={handleAddFact} />
					<button class="px-2.5 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg text-emerald-600 dark:text-emerald-400 transition" on:click={() => { if (newFactText.trim()) handleAddFact({ key: 'Enter' }); }}>
						<svg class="size-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
					</button>
				</div>
				{#if memory.length > 3}
					<div class="mt-2 relative">
						<input type="text" class="w-full bg-gray-50 dark:bg-white/[0.02] border border-gray-200/60 dark:border-white/[0.05] rounded-lg pl-7 pr-3 py-1.5 text-[11px] text-gray-700 dark:text-white/70 placeholder:text-gray-400 dark:placeholder:text-white/20 focus:outline-none focus:border-gray-300 dark:focus:border-white/10 transition" placeholder="Поиск..." bind:value={memorySearch} />
						<svg class="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-gray-400 dark:text-white/20" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
					</div>
				{/if}
			</div>
			<div class="flex-1 overflow-y-auto scrollbar-hidden px-4 py-3">
				{#if loading}
					<div class="space-y-2.5">
						<div class="h-14 bg-gray-100 dark:bg-white/[0.02] rounded-lg animate-pulse"></div>
						<div class="h-16 bg-gray-100 dark:bg-white/[0.02] rounded-lg animate-pulse opacity-60"></div>
					</div>
				{:else if filteredMemory.length > 0 || projectFiles.length > 0}
					<div class="space-y-4">
						{#if projectFiles.length > 0}
							<div class="space-y-1.5 pt-1">
								<h3 class="text-[10px] font-bold text-gray-400 dark:text-white/20 uppercase tracking-widest mb-2 px-1">Файлы и документы</h3>
								{#each projectFiles as file}
									<div class="group flex items-center gap-3 p-3 rounded-[14px] border border-gray-200 dark:border-white/[0.04] bg-white/40 dark:bg-[#111111]/40 hover:bg-white dark:hover:bg-[#1a1a1a] hover:border-violet-500/30 transition-all duration-300 cursor-pointer shadow-sm" on:click={() => {
										window.open(`${WEBUI_API_BASE_URL}/files/${file.id}/content?token=${localStorage.token}&attachment=true`, '_blank');
									}}>
										<div class="size-9 rounded-xl bg-violet-100 dark:bg-violet-500/10 flex items-center justify-center shrink-0 text-lg shadow-inner">
											{#if file.meta?.content_type?.startsWith('image/')}
												🖼️
											{:else if file.filename.endsWith('.pptx') || file.filename.endsWith('.ppt')}
												🎞️
											{:else if file.filename.endsWith('.pdf')}
												📄
											{:else}
												📁
											{/if}
										</div>
										<div class="flex-1 min-w-0">
											<div class="text-[13px] font-semibold text-gray-900 dark:text-gray-200 truncate group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors uppercase tracking-tight">{file.filename}</div>
											<div class="flex items-center gap-2 mt-0.5">
												<span class="text-[10px] font-bold text-gray-400 dark:text-white/20 uppercase tracking-widest">{file.meta?.content_type?.split('/')?.[1] || 'DOC'}</span>
												<span class="text-[10px] text-gray-300 dark:text-white/10 uppercase tracking-tighter">· {formatDate(file.created_at)}</span>
											</div>
										</div>
										<div class="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-gray-50 dark:bg-white/5 text-gray-400 dark:text-white/40">
											<svg class="size-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 12l4.5 4.5m0 0l4.5-4.5M12 3v13.5" /></svg>
										</div>
									</div>
								{/each}
							</div>
						{/if}

						{#if memory.length > 0}
							<div class="space-y-1.5">
								<h3 class="text-[10px] font-bold text-gray-400 dark:text-white/20 uppercase tracking-widest mb-2 px-1">База знаний</h3>
								{#each filteredMemory as fact, idx}
									<div class="group relative flex items-start gap-2.5 px-3.5 py-3 rounded-xl border border-transparent hover:border-gray-200 dark:hover:border-white/[0.06] hover:bg-white/80 dark:hover:bg-white/[0.03] transition-all" in:fly={{ y: 3, duration: 120, delay: idx * 15 }}>
										<div class="size-[7px] rotate-45 bg-emerald-500 dark:bg-emerald-400 shrink-0 mt-[7px] rounded-[1px] opacity-60"></div>
										<div class="flex-1 min-w-0">
											<p class="text-sm text-gray-900 dark:text-white/90 leading-[1.6] break-words {isStale(fact.updated_at) ? 'opacity-40' : ''}">{fact.text || fact.memory || '—'}</p>
											<span class="text-[10px] text-gray-400 dark:text-white/25 mt-1 block">{formatDate(fact.updated_at)}{#if isStale(fact.updated_at)} · <span class="text-amber-500/60">устарело?</span>{/if}</span>
										</div>
										<button class="text-gray-300 dark:text-white/10 hover:text-red-500 dark:hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 p-1 rounded shrink-0 mt-0.5" on:click|stopPropagation={() => deleteFact(fact.id)}>
											<svg class="size-3" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
										</button>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center h-full opacity-50 px-6 text-center">
						<svg class="size-8 text-gray-300 dark:text-white/10 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/></svg>
						<p class="text-xs text-gray-400 dark:text-white/30 font-bold uppercase tracking-wider">AI пока ничего не запомнил</p>
						<p class="text-[10px] text-gray-300 dark:text-white/15 mt-2 leading-relaxed">Добавьте первый факт вручную или начните чат — важные знания будут появляться здесь автоматически.</p>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<!-- Graph Modal Fullscreen Overhaul -->
{#if showGraphFullscreen}
	<div use:portal class="fixed inset-0 z-[9999] flex items-center justify-center backdrop-blur-2xl bg-white/60 dark:bg-black/80 transition-all font-sans" in:fade={{ duration: 300 }}>
		<div class="absolute inset-0 z-0" on:click={() => showGraphFullscreen = false}></div>
		<div class="relative z-10 w-[95vw] h-[95vh] rounded-[2rem] bg-gray-50/90 dark:bg-[#050505]/90 border border-gray-200/50 dark:border-white/[0.08] shadow-2xl flex flex-col overflow-hidden backdrop-blur-xl ring-1 ring-black/5 dark:ring-0">
			<!-- Header -->
			<div class="border-b border-gray-200/60 dark:border-white/[0.05] bg-white/50 dark:bg-black/60 shrink-0">
				<!-- Row 1: Title + Close -->
				<div class="flex items-center justify-between px-6 pt-4 pb-2">
					<h2 class="text-sm font-bold tracking-widest uppercase text-gray-900 dark:text-white/90 flex items-center gap-2.5">
						<span class="size-2 rounded-full shadow-[0_0_10px_2px] shadow-violet-500/50 bg-violet-400"></span>
						Карта знаний
						<span class="text-[10px] text-gray-400 dark:text-white/30 font-medium tracking-wider ml-1">{chatCount} чатов · {memCount} фактов</span>
					</h2>
					<button class="p-2 text-gray-500 dark:text-white/40 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 rounded-xl transition-colors" on:click={() => showGraphFullscreen = false}>
						<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>
				<!-- Row 2: Search + Filters (centered) -->
				<div class="flex items-center justify-center gap-3 px-6 pb-3">
					<div class="relative">
						<input
							type="text"
							bind:value={graphSearch}
							placeholder="Поиск по графу..."
							class="w-60 bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/[0.08] rounded-xl pl-9 pr-4 py-2 text-sm text-gray-800 dark:text-white/90 placeholder:text-gray-400 dark:placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500/30 transition"
						/>
						<svg class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-gray-400 dark:text-white/30" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
					</div>
					<!-- View mode selector -->
					<div class="flex items-center bg-gray-100 dark:bg-white/5 rounded-lg p-0.5 border border-gray-200/60 dark:border-white/[0.06]">
						<button class="px-3 py-1.5 text-xs font-semibold rounded-md transition {graphShowChats && graphShowMemory ? 'bg-white dark:bg-white/10 text-gray-900 dark:text-white shadow-sm' : 'text-gray-400 dark:text-white/30 hover:text-gray-600 dark:hover:text-white/50'}"
							on:click={() => { graphShowChats = true; graphShowMemory = true; }}>Всё</button>
						<button class="px-3 py-1.5 text-xs font-semibold rounded-md transition {graphShowChats && !graphShowMemory ? 'bg-white dark:bg-white/10 text-indigo-600 dark:text-indigo-400 shadow-sm' : 'text-gray-400 dark:text-white/30 hover:text-gray-600 dark:hover:text-white/50'}"
							on:click={() => { graphShowChats = true; graphShowMemory = false; }}>Только чаты</button>
						<button class="px-3 py-1.5 text-xs font-semibold rounded-md transition {!graphShowChats && graphShowMemory ? 'bg-white dark:bg-white/10 text-emerald-600 dark:text-emerald-400 shadow-sm' : 'text-gray-400 dark:text-white/30 hover:text-gray-600 dark:hover:text-white/50'}"
							on:click={() => { graphShowChats = false; graphShowMemory = true; }}>Только факты</button>
					</div>
					<!-- Recency toggle -->
					<button class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition {graphColorRecency ? 'bg-violet-50 dark:bg-violet-500/10 border-violet-200 dark:border-violet-500/20 text-violet-600 dark:text-violet-400' : 'bg-transparent border-gray-200 dark:border-white/[0.06] text-gray-400 dark:text-white/25 hover:text-gray-600 dark:hover:text-white/40'}"
						on:click={() => graphColorRecency = !graphColorRecency}
						title="Яркие = недавние, тусклые = давно не трогали"
					>
						<svg class="size-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
						Давность
					</button>
				</div>
			</div>
			<!-- Graph -->
			<div class="flex-1 relative bg-gray-100/50 dark:bg-black/20" style="min-height: 500px;">
				<ChatGraph chats={projectChats} memories={memory} projectTitle={project.title} colorFrom={"#6366f1"} colorTo={"#4f46e5"} compact={false} bind:searchQuery={graphSearch} bind:showChats={graphShowChats} bind:showMemory={graphShowMemory} bind:colorByRecency={graphColorRecency} />
				<!-- Legend (bottom-right, minimal) -->
				<div class="absolute bottom-4 right-4 px-3 py-2 bg-white/80 dark:bg-black/50 backdrop-blur-md border border-gray-200/50 dark:border-white/[0.06] rounded-xl flex gap-4 z-20 shadow-md">
					<div class="flex items-center gap-1.5"><span class="size-2 rounded-full bg-indigo-500"></span><span class="text-[9px] text-gray-500 dark:text-white/40 font-bold uppercase tracking-wider">Центр</span></div>
					<div class="flex items-center gap-1.5"><span class="size-2 rounded bg-blue-500"></span><span class="text-[9px] text-gray-500 dark:text-white/40 font-bold uppercase tracking-wider">Чат</span></div>
					<div class="flex items-center gap-1.5"><span class="size-2 rotate-45 bg-emerald-500"></span><span class="text-[9px] text-gray-500 dark:text-white/40 font-bold uppercase tracking-wider">Факт</span></div>
				</div>
				<!-- Hint (bottom-left) -->
				<div class="absolute bottom-4 left-4 px-3 py-2 bg-white/70 dark:bg-black/40 backdrop-blur-md border border-gray-200/50 dark:border-white/[0.06] rounded-xl z-20">
					<span class="text-[9px] text-gray-400 dark:text-white/25 font-medium">Клик = превью · Двойной клик = открыть</span>
				</div>
			</div>
		</div>
	</div>
{/if}

{/if}
