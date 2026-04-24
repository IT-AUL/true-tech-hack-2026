<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { goto } from '$app/navigation';
	import {
		user,
		chats,
		settings,
		showSettings,
		chatId,
		tags,
		folders as _folders,
		showSidebar,
		showSearch,
		mobile,
		showArchivedChats,
		pinnedChats,
		scrollPaginationEnabled,
		currentChatPage,
		temporaryChatEnabled,
		channels,
		socket,
		config,
		isApp,
		models,
		selectedFolder,
		WEBUI_NAME,
		sidebarWidth,
		activeChatIds,
		projects,
		selectedProjectId
	} from '$lib/stores';
	import { onMount, getContext, tick, onDestroy } from 'svelte';

	const i18n = getContext('i18n');

	import {
		getChatList,
		getAllTags,
		getPinnedChatList,
		toggleChatPinnedStatusById,
		getChatById,
		updateChatFolderIdById,
		importChats
	} from '$lib/apis/chats';
	import { createNewFolder, getFolders, updateFolderParentIdById } from '$lib/apis/folders';
	import { getProjects } from '$lib/apis/projects';
	import { checkActiveChats } from '$lib/apis/tasks';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import ArchivedChatsModal from './ArchivedChatsModal.svelte';
	import UserMenu from './Sidebar/UserMenu.svelte';
	import ChatItem from './Sidebar/ChatItem.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Loader from '../common/Loader.svelte';
	import Folder from '../common/Folder.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Folders from './Sidebar/Folders.svelte';
	import { getChannels, createNewChannel } from '$lib/apis/channels';
	import ChannelModal from './Sidebar/ChannelModal.svelte';
	import ChannelItem from './Sidebar/ChannelItem.svelte';
	import PencilSquare from '../icons/PencilSquare.svelte';
	import Search from '../icons/Search.svelte';
	import SearchModal from './SearchModal.svelte';
	import FolderModal from './Sidebar/Folders/FolderModal.svelte';
	import Sidebar from '../icons/Sidebar.svelte';
	import PinnedModelList from './Sidebar/PinnedModelList.svelte';
	import Note from '../icons/Note.svelte';
	import { slide } from 'svelte/transition';
	import HotkeyHint from '../common/HotkeyHint.svelte';
	import SpacesColumn from './Sidebar/SpacesColumn.svelte';

	const BREAKPOINT = 768;

	let scrollTop = 0;

	let navElement;
	let shiftKey = false;

	let selectedChatId = null;
	let showCreateChannel = false;

	// Pagination variables
	let chatListLoading = false;
	let allChatsLoaded = false;

	let showCreateFolderModal = false;

	let pinnedModels = [];

	let showPinnedModels = false;
	let showChannels = false;
	let showFolders = false;

	let folders = {};
	let folderRegistry = {};

	let newFolderId = null;

	$: if ($selectedFolder) {
		initFolders();
	}

	const initFolders = async () => {
		if ($config?.features?.enable_folders === false) {
			return;
		}

		const folderList = await getFolders(localStorage.token).catch((error) => {
			return [];
		});
		_folders.set(folderList.sort((a, b) => b.updated_at - a.updated_at));

		folders = {};

		// First pass: Initialize all folder entries
		for (const folder of folderList) {
			// Ensure folder is added to folders with its data
			folders[folder.id] = { ...(folders[folder.id] || {}), ...folder };

			if (newFolderId && folder.id === newFolderId) {
				folders[folder.id].new = true;
				newFolderId = null;
			}
		}

		// Second pass: Tie child folders to their parents
		for (const folder of folderList) {
			if (folder.parent_id) {
				// Ensure the parent folder is initialized if it doesn't exist
				if (!folders[folder.parent_id]) {
					folders[folder.parent_id] = {}; // Create a placeholder if not already present
				}

				// Initialize childrenIds array if it doesn't exist and add the current folder id
				folders[folder.parent_id].childrenIds = folders[folder.parent_id].childrenIds
					? [...folders[folder.parent_id].childrenIds, folder.id]
					: [folder.id];

				// Sort the children by updated_at field
				folders[folder.parent_id].childrenIds.sort((a, b) => {
					return folders[b].updated_at - folders[a].updated_at;
				});
			}
		}
	};

	const createFolder = async ({ name, data, parent_id }) => {
		name = name?.trim();
		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		// Check for duplicate names in the same parent
		const siblings = Object.values(folders).filter((folder) => folder.parent_id === parent_id);
		if (siblings.find((folder) => folder.name.toLowerCase() === name.toLowerCase())) {
			// If a folder with the same name already exists, append a number to the name
			let i = 1;
			while (
				siblings.find((folder) => folder.name.toLowerCase() === `${name} ${i}`.toLowerCase())
			) {
				i++;
			}

			name = `${name} ${i}`;
		}

		// Add a dummy folder to the list to show the user that the folder is being created
		const tempId = uuidv4();
		folders = {
			...folders,
			[tempId]: {
				id: tempId,
				name: name,
				parent_id: parent_id,
				created_at: Date.now(),
				updated_at: Date.now()
			}
		};

		const res = await createNewFolder(localStorage.token, {
			name,
			data,
			parent_id
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			// newFolderId = res.id;
			await initFolders();
			showFolders = true;
		}
	};

	const initChannels = async () => {
		// default (none), group, dm type
		const res = await getChannels(localStorage.token).catch((error) => {
			return null;
		});

		if (res) {
			await channels.set(
				res.sort(
					(a, b) =>
						['', null, 'group', 'dm'].indexOf(a.type) - ['', null, 'group', 'dm'].indexOf(b.type)
				)
			);
		}
	};

	const initProjects = async () => {
		const res = await getProjects(localStorage.token).catch((error) => {
			return null;
		});

		if (res) {
			projects.set(res);
			
			if (res.length === 0 && window.location.pathname === '/') {
				goto('/workspace/onboarding');
			}
		}
	};

	const initChatList = async () => {
		// Reset pagination variables
		console.log('initChatList');
		currentChatPage.set(1);
		allChatsLoaded = false;
		scrollPaginationEnabled.set(false);

		initFolders();
		initProjects();
		await Promise.all([
			await (async () => {
				console.log('Init tags');
				const _tags = await getAllTags(localStorage.token);
				tags.set(_tags);
			})(),
			await (async () => {
				console.log('Init pinned chats');
				const _pinnedChats = await getPinnedChatList(localStorage.token);
				pinnedChats.set(_pinnedChats);
			})(),
			await (async () => {
				console.log('Init chat list');
				const _chats = await getChatList(localStorage.token, $currentChatPage);
				await chats.set(_chats);
			})()
		]);

		// Enable pagination
		scrollPaginationEnabled.set(true);
	};

	const loadMoreChats = async () => {
		chatListLoading = true;

		currentChatPage.set($currentChatPage + 1);

		let newChatList = [];

		newChatList = await getChatList(localStorage.token, $currentChatPage);

		// once the bottom of the list has been reached (no results) there is no need to continue querying
		allChatsLoaded = newChatList.length === 0;
		const existingIds = new Set(($chats ?? []).map((c) => c.id));
		const uniqueNewChats = newChatList.filter((c) => !existingIds.has(c.id));
		await chats.set([...($chats ? $chats : []), ...uniqueNewChats]);

		chatListLoading = false;
	};

	const importChatHandler = async (items, pinned = false, folderId = null) => {
		console.log('importChatHandler', items, pinned, folderId);
		for (const item of items) {
			console.log(item);
			if (item.chat) {
				await importChats(localStorage.token, [
					{
						chat: item.chat,
						meta: item?.meta ?? {},
						pinned: pinned,
						folder_id: folderId,
						created_at: item?.created_at ?? null,
						updated_at: item?.updated_at ?? null
					}
				]);
			}
		}

		initChatList();
	};

	const inputFilesHandler = async (files) => {
		console.log(files);

		for (const file of files) {
			const reader = new FileReader();
			reader.onload = async (e) => {
				const content = e.target.result;

				try {
					const chatItems = JSON.parse(content);
					importChatHandler(chatItems);
				} catch {
					toast.error($i18n.t(`Invalid file format.`));
				}
			};

			reader.readAsText(file);
		}
	};

	const tagEventHandler = async (type, tagName, chatId) => {
		console.log(type, tagName, chatId);
		if (type === 'delete') {
			initChatList();
		} else if (type === 'add') {
			initChatList();
		}
	};

	let draggedOver = false;

	const onDragOver = (e) => {
		e.preventDefault();

		// Check if a file is being draggedOver.
		if (e.dataTransfer?.types?.includes('Files')) {
			draggedOver = true;
		} else {
			draggedOver = false;
		}
	};

	const onDragLeave = () => {
		draggedOver = false;
	};

	const onDrop = async (e) => {
		e.preventDefault();
		console.log(e); // Log the drop event

		// Perform file drop check and handle it accordingly
		if (e.dataTransfer?.files) {
			const inputFiles = Array.from(e.dataTransfer?.files);

			if (inputFiles && inputFiles.length > 0) {
				console.log(inputFiles); // Log the dropped files
				inputFilesHandler(inputFiles); // Handle the dropped files
			}
		}

		draggedOver = false; // Reset draggedOver status after drop
	};

	let touchstart;
	let touchend;

	function checkDirection() {
		const screenWidth = window.innerWidth;
		const swipeDistance = Math.abs(touchend.screenX - touchstart.screenX);
		if (touchstart.clientX < 40 && swipeDistance >= screenWidth / 8) {
			if (touchend.screenX < touchstart.screenX) {
				showSidebar.set(false);
			}
			if (touchend.screenX > touchstart.screenX) {
				showSidebar.set(true);
			}
		}
	}

	const onTouchStart = (e) => {
		touchstart = e.changedTouches[0];
		console.log(touchstart.clientX);
	};

	const onTouchEnd = (e) => {
		touchend = e.changedTouches[0];
		checkDirection();
	};

	const onKeyDown = (e) => {
		if (e.key === 'Shift') {
			shiftKey = true;
		}
	};

	const onKeyUp = (e) => {
		if (e.key === 'Shift') {
			shiftKey = false;
		}
	};

	const onFocus = () => {};

	const onBlur = () => {
		shiftKey = false;
		selectedChatId = null;
	};

	const MIN_WIDTH = 300;
	const MAX_WIDTH = 520;

	let isResizing = false;

	let startWidth = 0;
	let startClientX = 0;

	const resizeStartHandler = (e: MouseEvent) => {
		if ($mobile) return;
		isResizing = true;

		startClientX = e.clientX;
		startWidth = $sidebarWidth ?? 340;

		document.body.style.userSelect = 'none';
	};

	const resizeEndHandler = () => {
		if (!isResizing) return;
		isResizing = false;

		document.body.style.userSelect = '';
		localStorage.setItem('sidebarWidth', String($sidebarWidth));
	};

	const resizeSidebarHandler = (endClientX) => {
		const dx = endClientX - startClientX;
		const newSidebarWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + dx));

		sidebarWidth.set(newSidebarWidth);
		document.documentElement.style.setProperty('--sidebar-width', `${newSidebarWidth}px`);
	};

	onMount(() => {
		try {
			const width = Number(localStorage.getItem('sidebarWidth'));
			if (!Number.isNaN(width) && width >= MIN_WIDTH && width <= MAX_WIDTH) {
				sidebarWidth.set(width);
			}
		} catch {}

		document.documentElement.style.setProperty('--sidebar-width', `${$sidebarWidth}px`);
		sidebarWidth.subscribe((w) => {
			if (!$selectedProjectId) {
				document.documentElement.style.setProperty('--sidebar-width', `${w}px`);
			}
		});
		selectedProjectId.subscribe((active) => {
			if (active) {
				document.documentElement.style.setProperty('--sidebar-width', `68px`);
			} else {
				document.documentElement.style.setProperty('--sidebar-width', `${$sidebarWidth}px`);
			}
		});

		const shouldShow = !$mobile ? localStorage.sidebar === 'true' : false;
		if (!$mobile && window.location.pathname === '/' && !$selectedProjectId) {
			showSidebar.set(false);
		} else {
			showSidebar.set(shouldShow);
		}

		// Always initialize projects/spaces since they are visible in SpacesColumn
		initProjects();

		const unsubscribers = [
			mobile.subscribe((value) => {
				if ($showSidebar && value) {
					showSidebar.set(false);
				}

				if ($showSidebar && !value) {
					const navElement = document.getElementsByTagName('nav')[0];
					if (navElement) {
						navElement.style['-webkit-app-region'] = 'drag';
					}
				}
			}),
			showSidebar.subscribe(async (value) => {
				localStorage.sidebar = value;

				// nav element is not available on the first render
				const navElement = document.getElementsByTagName('nav')[0];

				if (navElement) {
					if ($mobile) {
						if (!value) {
							navElement.style['-webkit-app-region'] = 'drag';
						} else {
							navElement.style['-webkit-app-region'] = 'no-drag';
						}
					} else {
						navElement.style['-webkit-app-region'] = 'drag';
					}
				}

				if (value) {
					// Only fetch channels if the feature is enabled and user has permission
					if (
						$config?.features?.enable_channels &&
						($user?.role === 'admin' || ($user?.permissions?.features?.channels ?? true))
					) {
						await initChannels();
					}
					await initChatList();

					// Check which chats have active tasks
					const allChatIds = [...$chats.map((c) => c.id), ...$pinnedChats.map((c) => c.id)];
					if (allChatIds.length > 0) {
						try {
							const res = await checkActiveChats(localStorage.token, allChatIds);
							activeChatIds.set(new Set(res.active_chat_ids || []));
						} catch (e) {
							console.debug('Failed to check active chats:', e);
						}
					}
				}
			}),
			settings.subscribe((value) => {
				if (pinnedModels != value?.pinnedModels ?? []) {
					pinnedModels = value?.pinnedModels ?? [];
					showPinnedModels = pinnedModels.length > 0;
				}
			})
		];

		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);

		window.addEventListener('touchstart', onTouchStart);
		window.addEventListener('touchend', onTouchEnd);

		window.addEventListener('focus', onFocus);
		window.addEventListener('blur', onBlur);

		const dropZone = document.getElementById('sidebar');
		if (dropZone) {
			dropZone.addEventListener('dragover', onDragOver);
			dropZone.addEventListener('drop', onDrop);
			dropZone.addEventListener('dragleave', onDragLeave);
		}

		const socketInstance = $socket;
		socketInstance?.on('events', chatActiveEventHandler);

		return () => {
			unsubscribers.forEach((unsubscriber) => unsubscriber());

			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('keyup', onKeyUp);

			window.removeEventListener('touchstart', onTouchStart);
			window.removeEventListener('touchend', onTouchEnd);

			window.removeEventListener('focus', onFocus);
			window.removeEventListener('blur', onBlur);

			if (dropZone) {
				dropZone.removeEventListener('dragover', onDragOver);
				dropZone.removeEventListener('drop', onDrop);
				dropZone.removeEventListener('dragleave', onDragLeave);
			}

			socketInstance?.off('events', chatActiveEventHandler);
		};
	});

	// Handler for chat:active events (defined outside onMount for proper cleanup)
	const chatActiveEventHandler = (event: {
		chat_id: string;
		message_id: string;
		data: { type: string; data: any };
	}) => {
		if (event.data?.type === 'chat:active') {
			const { active } = event.data.data;
			activeChatIds.update((ids) => {
				const newSet = new Set(ids);
				if (active) {
					newSet.add(event.chat_id);
				} else {
					newSet.delete(event.chat_id);
				}
				return newSet;
			});
		}
	};

	const newChatHandler = async () => {
		selectedChatId = null;
		selectedFolder.set(null);

		if ($user?.role !== 'admin' && $user?.permissions?.chat?.temporary_enforced) {
			await temporaryChatEnabled.set(true);
		} else {
			await temporaryChatEnabled.set(false);
		}

		setTimeout(() => {
			if ($mobile) {
				showSidebar.set(false);
			}
		}, 0);
	};

	const itemClickHandler = async () => {
		selectedChatId = null;
		chatId.set('');

		if ($mobile) {
			showSidebar.set(false);
		}

		await tick();
	};

	const isWindows = /Windows/i.test(navigator.userAgent);
</script>

<ArchivedChatsModal
	bind:show={$showArchivedChats}
	onUpdate={async () => {
		await initChatList();
	}}
	onDelete={(id) => {
		if ($chatId === id) {
			goto('/');
			chatId.set('');
		}
	}}
/>

<ChannelModal
	bind:show={showCreateChannel}
	onSubmit={async (payload: any) => {
		let { type, name, is_private, access_grants, group_ids, user_ids } = payload ?? {};
		name = name?.trim();

		if (type === 'dm') {
			if (!user_ids || user_ids.length === 0) {
				toast.error($i18n.t('Please select at least one user for Direct Message channel.'));
				return;
			}
		} else {
			if (!name) {
				toast.error($i18n.t('Channel name cannot be empty.'));
				return;
			}
		}

		const res = await createNewChannel(localStorage.token, {
			type: type,
			name: name,
			is_private: is_private,
			access_grants: access_grants,
			group_ids: group_ids,
			user_ids: user_ids
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			$socket.emit('join-channels', { auth: { token: $user?.token } });
			await initChannels();
			showCreateChannel = false;
			showChannels = true;
			goto(`/channels/${res.id}`);
		}
	}}
/>

<FolderModal
	bind:show={showCreateFolderModal}
	onSubmit={async (folder) => {
		await createFolder(folder);
		showCreateFolderModal = false;
	}}
/>

<!-- svelte-ignore a11y-no-static-element-interactions -->

{#if $showSidebar}
	<div
		class=" {$isApp
			? ' ml-[4.5rem] md:ml-0'
			: ''} fixed md:hidden z-40 top-0 right-0 left-0 bottom-0 bg-black/60 w-full min-h-screen h-screen flex justify-center overflow-hidden overscroll-contain"
		on:mousedown={() => {
			showSidebar.set(!$showSidebar);
		}}
	/>
{/if}

<SearchModal
	bind:show={$showSearch}
	onClose={() => {
		if ($mobile) {
			showSidebar.set(false);
		}
	}}
/>

<button
	id="sidebar-new-chat-button"
	class="hidden"
	on:click={() => {
		goto('/');
		newChatHandler();
	}}
/>

<svelte:window
	on:mousemove={(e) => {
		if (!isResizing) return;
		resizeSidebarHandler(e.clientX);
	}}
	on:mouseup={() => {
		resizeEndHandler();
	}}
/>

{#if !$mobile && !$showSidebar}
	<div class="h-full z-10 transition-all" id="sidebar">
		<SpacesColumn onSpaceSelect={(id) => { showSidebar.set(true); }} />
	</div>
{/if}


<!-- {$i18n.t('New Folder')} -->
<!-- {$i18n.t('Pinned')} -->

{#if $showSidebar}
	<div
		bind:this={navElement}
		id="sidebar"
		class="h-screen max-h-[100dvh] min-h-screen select-none {$showSidebar
			? `${$mobile ? 'bg-gray-50 dark:bg-gray-950' : 'bg-gray-50/70 dark:bg-gray-950/70'} z-50`
			: ' bg-transparent z-0 '} {$isApp
			? `ml-[4.5rem] md:ml-0 `
			: ' transition-all duration-300 '} shrink-0 text-gray-900 dark:text-gray-200 text-sm fixed top-0 left-0 overflow-x-hidden
        "
		transition:slide={{ duration: 250, axis: 'x' }}
		data-state={$showSidebar}
	>
		<div
			class="my-auto flex flex-row h-screen max-h-[100dvh] w-[var(--sidebar-width)] z-50 {$showSidebar
				? ''
				: 'invisible'}"
		>
			<SpacesColumn />
			<div class="flex flex-col flex-1 min-w-0 overflow-x-hidden scrollbar-hidden bg-gray-50/50 dark:bg-gray-950/50">
				<div class="sidebar px-3 pt-3 pb-2 flex justify-between items-center sticky top-0 z-10">
					<!-- Sidebar Toggle Button (moved to top left since logo is gone) -->
					<Tooltip content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')} placement="bottom">
						<button
							id="tour-sidebar-toggle-close"
							class="flex rounded-xl size-9 justify-center items-center bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition {isWindows ? 'cursor-pointer' : 'cursor-[w-resize]'}"
							on:click={() => { showSidebar.set(!$showSidebar); }}
							aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
						>
							<Sidebar className="size-4" />
						</button>
					</Tooltip>

					<div
						class="{scrollTop > 0 ? 'visible' : 'invisible'} sidebar-bg-gradient-to-b bg-linear-to-b from-gray-50 dark:from-gray-950 to-transparent from-50% pointer-events-none absolute inset-0 -z-10 -mb-6"
					></div>
				</div>

				{#if !$selectedProjectId}
					<div></div>
				{/if}

				<div
					class="relative flex flex-col flex-1 overflow-y-auto scrollbar-hidden pt-1 pb-3"
					on:scroll={(e) => {
						if (e.target.scrollTop === 0) {
							scrollTop = 0;
						} else {
							scrollTop = e.target.scrollTop;
						}

						// Infinite scroll: load more chats when near bottom
						if ($scrollPaginationEnabled && !chatListLoading && !allChatsLoaded) {
							const { scrollHeight, clientHeight } = e.target;
							if (scrollHeight - scrollTop - clientHeight < 200) {
								loadMoreChats();
							}
						}
					}}
				>
				<div class="pb-1.5 px-2 flex flex-col gap-1">
					<a
						id="sidebar-new-chat-button"
						class="group flex items-center gap-3 rounded-xl px-3 py-2.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:brightness-110 transition shadow-sm outline-none"
						href="/"
						draggable="false"
						on:click={newChatHandler}
						aria-label={$i18n.t('New Chat')}
					>
						<PencilSquare className="size-4.5" strokeWidth="2" />
						<span class="text-sm font-semibold">Новый чат</span>
						<HotkeyHint name="newChat" className="ml-auto group-hover:visible invisible opacity-50" />
					</a>

					<button
						id="sidebar-search-button"
						class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-900 border border-transparent hover:border-gray-200 dark:hover:border-gray-800 transition outline-none"
						on:click={() => { showSearch.set(true); }}
						draggable="false"
					>
						<Search strokeWidth="2" className="size-4.5" />
						<span class="text-sm font-medium">Поиск</span>
						<HotkeyHint name="search" className="ml-auto group-hover:visible invisible opacity-50" />
					</button>

					{#if ($config?.features?.enable_notes ?? false) && ($user?.role === 'admin' || ($user?.permissions?.features?.notes ?? true))}
						<a
							id="sidebar-notes-button"
							class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-900 border border-transparent hover:border-gray-200 dark:hover:border-gray-800 transition outline-none"
							href="/notes"
							on:click={itemClickHandler}
							draggable="false"
						>
							<Note className="size-4.5" strokeWidth="2" />
							<span class="text-sm font-medium">Заметки</span>
						</a>
					{/if}

					{#if $user?.role === 'admin' || $user?.permissions?.workspace?.models || $user?.permissions?.workspace?.knowledge || $user?.permissions?.workspace?.prompts || $user?.permissions?.workspace?.tools}
						<a
							id="sidebar-workspace-button"
							class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-900 border border-transparent hover:border-gray-200 dark:hover:border-gray-800 transition outline-none"
							href="/workspace"
							on:click={itemClickHandler}
							draggable="false"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4.5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 0 0 2.25-2.25V6a2.25 2.25 0 0 0-2.25-2.25H6A2.25 2.25 0 0 0 3.75 6v2.25A2.25 2.25 0 0 0 6 10.5Zm0 9.75h2.25A2.25 2.25 0 0 0 10.5 18v-2.25a2.25 2.25 0 0 0-2.25-2.25H6a2.25 2.25 0 0 0-2.25 2.25V18A2.25 2.25 0 0 0 6 20.25Zm9.75-9.75H18a2.25 2.25 0 0 0 2.25-2.25V6A2.25 2.25 0 0 0 18 3.75h-2.25A2.25 2.25 0 0 0 13.5 6v2.25a2.25 2.25 0 0 0 2.25 2.25Z" />
							</svg>
							<span class="text-sm font-medium">Настройки ИИ</span>
						</a>
					{/if}

					<div class="mt-4 mb-2 px-3">
						<div class="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">
							Предыдущие чаты
						</div>
					</div>
				</div>

				{#if !$selectedProjectId}

				{#if ($models ?? []).length > 0 && (($settings?.pinnedModels ?? []).length > 0 || $config?.default_pinned_models)}
					<Folder
						id="sidebar-models"
						bind:open={showPinnedModels}
						className="px-2 mt-0.5"
						name={$i18n.t('Models')}
						chevron={false}
						dragAndDrop={false}
					>
						<PinnedModelList bind:selectedChatId {shiftKey} />
					</Folder>
				{/if}

				{#if $config?.features?.enable_channels && ($user?.role === 'admin' || ($user?.permissions?.features?.channels ?? true)) && ($channels?.length > 0 || $user?.role === 'admin')}
					<Folder
						id="sidebar-channels"
						bind:open={showChannels}
						className="px-2 mt-0.5"
						name={$i18n.t('Channels')}
						chevron={false}
						dragAndDrop={false}
						onAdd={$user?.role === 'admin' || ($user?.permissions?.features?.channels ?? true)
							? async () => {
									await tick();

									setTimeout(() => {
										showCreateChannel = true;
									}, 0);
								}
							: null}
						onAddLabel={$i18n.t('Create Channel')}
					>
						{#each $channels as channel, channelIdx (`${channel?.id}`)}
							<ChannelItem
								{channel}
								onUpdate={async () => {
									await initChannels();
								}}
							/>

							{#if channelIdx < $channels.length - 1 && channel.type !== $channels[channelIdx + 1]?.type}<hr
									class=" border-gray-100/40 dark:border-gray-800/10 my-1.5 w-full"
								/>
							{/if}
						{/each}
					</Folder>
				{/if}

				{#if $config?.features?.enable_folders && ($user?.role === 'admin' || ($user?.permissions?.features?.folders ?? true))}
					<Folder
						id="sidebar-folders"
						bind:open={showFolders}
						className="px-2 mt-0.5"
						name={$i18n.t('Folders')}
						chevron={false}
						onAdd={() => {
							showCreateFolderModal = true;
						}}
						onAddLabel={$i18n.t('New Folder')}
						on:drop={async (e) => {
							const { type, id, item } = e.detail;

							if (type === 'folder') {
								if (folders[id].parent_id === null) {
									return;
								}

								const res = await updateFolderParentIdById(localStorage.token, id, null).catch(
									(error) => {
										toast.error(`${error}`);
										return null;
									}
								);

								if (res) {
									await initFolders();
								}
							}
						}}
					>
						<Folders
							bind:folderRegistry
							{folders}
							{shiftKey}
							onDelete={(folderId) => {
								selectedFolder.set(null);
								initChatList();
							}}
							on:update={() => {
								initChatList();
							}}
							on:import={(e) => {
								const { folderId, items } = e.detail;
								importChatHandler(items, false, folderId);
							}}
							on:change={async () => {
								initChatList();
							}}
						/>
					</Folder>
				{/if}

				<div class="px-2 mt-4 mb-2">
					<div class="text-xs font-semibold text-gray-500 uppercase tracking-wider pl-2.5">
						Предыдущие чаты
					</div>
				</div>

				{:else}

				<div class="px-2.5 mt-1 mb-1.5">
					<button
						class="w-full flex items-center gap-2.5 p-2 rounded-xl bg-gradient-to-r from-indigo-500/10 to-purple-500/10 dark:from-indigo-500/15 dark:to-purple-500/15 border border-indigo-200/30 dark:border-indigo-800/30 hover:from-indigo-500/15 hover:to-purple-500/15 dark:hover:from-indigo-500/20 dark:hover:to-purple-500/20 transition-all group"
						on:click={() => goto('/')}
						title="Дашборд пространства"
					>
						{#each $projects as p}
							{#if p.id === $selectedProjectId}
								{@const desc = p.description || ''}
								{@const metaMatch = desc.match(/<!--space-meta:(.+?)-->/)}
								{@const meta = metaMatch ? (() => { try { return JSON.parse(metaMatch[1]); } catch { return {}; } })() : {}}
								<div class="size-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm shrink-0 shadow-sm">
									{meta.emoji || p.title[0]?.toUpperCase() || '🚀'}
								</div>
								<div class="flex-1 min-w-0 text-left">
									<div class="text-xs font-semibold text-gray-900 dark:text-white truncate">{p.title}</div>
									<div class="text-[9px] text-indigo-500 dark:text-indigo-400 flex items-center gap-1">
										<span class="size-1 rounded-full bg-green-500 inline-block"></span>
										Mem0 активна
									</div>
								</div>
							{/if}
						{/each}
						<div class="flex gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition">
							<span
								class="p-1 hover:bg-white/50 dark:hover:bg-gray-800/50 rounded-md text-gray-400 hover:text-red-500 transition"
								role="button"
								tabindex="0"
								on:click|stopPropagation={() => selectedProjectId.set(null)}
								on:keydown={(e) => { if (e.key === 'Enter') selectedProjectId.set(null); }}
								title="Выйти"
							>
								<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3">
									<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</span>
						</div>
					</button>
				</div>
				{/if}
				<div class="pt-1.5 pb-20">
					{#if $chats !== null}
						{#each ($selectedProjectId ? $chats.filter(c => c.project_id === $selectedProjectId) : $chats) as chat, idx (`chat-${chat.id}`)}
							<div class="px-[0.4375rem] flex justify-center text-gray-800 dark:text-gray-200">
								<ChatItem
									className="w-full"
									id={chat.id}
									title={chat.title}
									createdAt={chat.updated_at}
									selected={chat.id === selectedChatId || chat.id === $chatId}
									{shiftKey}
									on:select={() => {
										selectedChatId = chat.id;
									}}
									on:unselect={() => {
										selectedChatId = null;
									}}
									on:change={() => {
										initChatList();
									}}
									on:dragEnd={(e) => {
										// Handle drag end
									}}
								/>
							</div>
						{/each}
					{/if}

					<div class="w-full flex justify-center py-2">
						{#if chatListLoading}
							<Spinner className="size-4" />
						{:else if !allChatsLoaded}
							<div class="h-10 w-full" />
						{/if}
					</div>
					</div>
				</div>

				<div class="px-1.5 pt-1.5 pb-2 sticky bottom-0 z-10 -mt-3 sidebar">
					<div
						class=" sidebar-bg-gradient-to-t bg-linear-to-t from-gray-50 dark:from-gray-950 to-transparent from-50% pointer-events-none absolute inset-0 -z-10 -mt-6"
					></div>
					<div class="flex flex-col font-primary">
						<!-- User menu moved to SpacesColumn -->
					</div>
				</div>
			</div>
		</div>
	</div>

	{#if !$mobile && !$selectedProjectId}
		<div
			class="relative flex items-center justify-center group border-l border-gray-50 dark:border-gray-850/30 hover:border-gray-200 dark:hover:border-gray-800 transition z-20"
			id="sidebar-resizer"
			on:mousedown={resizeStartHandler}
			role="separator"
		>
			<div
				class=" absolute -left-1.5 -right-1.5 -top-0 -bottom-0 z-20 cursor-col-resize bg-transparent"
			/>
		</div>
	{/if}
{/if}
