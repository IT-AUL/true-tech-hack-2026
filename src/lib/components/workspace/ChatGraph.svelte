<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { fly, fade } from 'svelte/transition';

	export let chats: any[] = [];
	export let memories: any[] = [];
	export let projectTitle = '';
	export let colorFrom = '#6366f1';
	export let colorTo = '#4f46e5';
	export let compact = false;

	let container: HTMLDivElement;
	let graph: any = null;
	let mounted = false;
	let hoveredNode: any = null;
	let selectedNode: any = null;
	let animFrame = 0;

	// Feature state — exposed for parent to embed controls
	export let searchQuery = '';
	export let showChats = true;
	export let showMemory = true;
	export let colorByRecency = true;

	$: chatCount = chats.length;
	$: memCount = memories.length;

	$: matchingIds = searchQuery.trim()
		? new Set(
			[...chats, ...memories]
				.filter(item => {
					const text = (item.title || item.text || item.memory || '').toLowerCase();
					return text.includes(searchQuery.toLowerCase());
				})
				.map(item => item.id ? `chat-${item.id}` : `mem-${memories.indexOf(item)}`)
		  )
		: null;

	function getRecencyAlpha(updatedAt: any): number {
		if (!updatedAt) return 0.4;
		const d = typeof updatedAt === 'number' && updatedAt < 2e10
			? new Date(updatedAt * 1000) : new Date(updatedAt);
		if (isNaN(d.getTime())) return 0.4;
		const hoursAgo = (Date.now() - d.getTime()) / 3600000;
		if (hoursAgo < 1) return 1;
		if (hoursAgo < 24) return 0.9;
		if (hoursAgo < 168) return 0.7;
		return 0.45;
	}

	function buildGraphData() {
		const nodes: any[] = [];
		const links: any[] = [];

		nodes.push({ id: 'project-center', name: projectTitle || 'Пространство', val: 35, type: 'project' });

		if (showChats) {
			chats.forEach((chat, idx) => {
				const msgCount = chat.chat?.messages?.length || chat.message_count || 3;
				const sizeVal = 8 + Math.min(Math.log2(msgCount + 1) * 4, 20);
				nodes.push({
					id: `chat-${chat.id}`, name: chat.title || `Чат ${idx + 1}`,
					val: sizeVal, type: 'chat', chatId: chat.id,
					hue: 230 + (idx * 37) % 130,
					recency: getRecencyAlpha(chat.updated_at), raw: chat,
				});
				links.push({ source: 'project-center', target: `chat-${chat.id}` });
			});
		}

		if (showMemory) {
			const memLimit = Math.min(memories.length, 30);
			for (let i = 0; i < memLimit; i++) {
				const mem = memories[i];
				const text = mem.text || mem.memory || `Факт ${i + 1}`;
				nodes.push({
					id: `mem-${i}`, name: text.length > 35 ? text.substring(0, 33) + '…' : text,
					fullText: text, val: 5, type: 'memory', recency: getRecencyAlpha(mem.updated_at),
				});
				links.push({ source: 'project-center', target: `mem-${i}` });
			}
		}

		if (showChats) {
			const chatTags: Record<string, string[]> = {};
			chats.forEach(c => { if (c.tags?.length) chatTags[c.id] = c.tags.map((t: any) => typeof t === 'string' ? t : t.name); });
			const ids = Object.keys(chatTags);
			for (let i = 0; i < ids.length; i++)
				for (let j = i + 1; j < ids.length; j++)
					if (chatTags[ids[i]].some(t => chatTags[ids[j]].includes(t)))
						links.push({ source: `chat-${ids[i]}`, target: `chat-${ids[j]}`, shared: true });
		}

		return { nodes, links };
	}

	function handleNodeClick(node: any) {
		if (node.type === 'project') { selectedNode = null; return; }
		if (selectedNode?.id === node.id) {
			if (node.type === 'chat' && node.chatId) goto(`/c/${node.chatId}`);
			selectedNode = null;
		} else { selectedNode = node; }
	}

	async function initGraph() {
		if (!container || !mounted) return;
		const w = container.clientWidth; const h = container.clientHeight;
		if (w === 0 || h === 0) { setTimeout(initGraph, 200); return; }

		try {
			const { default: ForceGraph } = await import('force-graph');
			const data = buildGraphData();
			const isDark = document.documentElement.classList.contains('dark');

			if (graph) { graph._destructor?.(); graph = null; }

			graph = ForceGraph()(container)
				.graphData(data).nodeId('id').nodeVal((n: any) => n.val).nodeRelSize(1)
				.backgroundColor('rgba(0,0,0,0)').width(w).height(h).cooldownTicks(120)
				.linkColor((l: any) => l.shared ? (isDark ? 'rgba(251,191,36,0.2)' : 'rgba(217,119,6,0.15)') : (isDark ? 'rgba(139,92,246,0.1)' : 'rgba(99,102,241,0.08)'))
				.linkWidth((l: any) => l.shared ? 2 : 1.2).linkLineDash((l: any) => l.shared ? null : [4, 4])
				.linkDirectionalParticles(2).linkDirectionalParticleWidth(2)
				.linkDirectionalParticleColor(() => isDark ? 'rgba(139,92,246,0.5)' : 'rgba(99,102,241,0.4)')
				.linkDirectionalParticleSpeed(0.004)
				.onNodeClick(handleNodeClick)
				.onNodeHover((n: any) => { hoveredNode = n; if (container) container.style.cursor = n && n.type !== 'project' ? 'pointer' : 'default'; })
				.onBackgroundClick(() => { selectedNode = null; })
				.nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, gs: number) => {
					if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
					const t = Date.now() / 1000;
					const isHover = hoveredNode === node;
					const isSel = selectedNode?.id === node.id;
					const dimmed = matchingIds && !matchingIds.has(node.id) && node.type !== 'project';

					if (dimmed) ctx.globalAlpha = 0.15;
					else if (colorByRecency && node.type !== 'project') ctx.globalAlpha = node.recency ?? 1;

					if (node.type === 'project') drawProject(node, ctx, gs, t, isDark, isHover);
					else if (node.type === 'chat') drawChat(node, ctx, gs, isDark, isHover, isSel);
					else drawMem(node, ctx, gs, isDark, isHover, isSel);
					ctx.globalAlpha = 1;
				})
				.nodePointerAreaPaint((node: any, color: string, ctx: CanvasRenderingContext2D) => {
					if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
					const r = Math.sqrt(node.val) * 4;
					ctx.fillStyle = color;
					if (node.type === 'chat') ctx.fillRect(node.x - r * 1.8, node.y - r, r * 3.6, r * 2);
					else { ctx.beginPath(); ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI); ctx.fill(); }
				});

			try { graph.d3Force('charge')?.strength(-110); graph.d3Force('link')?.distance(100); } catch {}

			setTimeout(() => graph?.zoomToFit(600, 60), 1200);
			setTimeout(() => graph?.zoomToFit(800, 60), 3000);

			function tick() { if (!mounted || !graph) return; graph.nodeColor(() => 'transparent'); animFrame = requestAnimationFrame(tick); }
			animFrame = requestAnimationFrame(tick);
		} catch (e) { console.error('ChatGraph:', e); }
	}

	function drawProject(n: any, ctx: CanvasRenderingContext2D, gs: number, t: number, dark: boolean, hover: boolean) {
		const r = 24; const pulse = Math.sin(t * 2) * 3;
		for (let i = 3; i >= 1; i--) { ctx.beginPath(); ctx.arc(n.x, n.y, r + pulse + i * 9, 0, 2 * Math.PI); ctx.fillStyle = `rgba(99,102,241,${0.025 * i})`; ctx.fill(); }
		ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
		const g = ctx.createRadialGradient(n.x - r * 0.3, n.y - r * 0.3, 0, n.x, n.y, r);
		g.addColorStop(0, '#a78bfa'); g.addColorStop(0.5, colorFrom); g.addColorStop(1, colorTo);
		ctx.fillStyle = g; ctx.fill();
		ctx.beginPath(); ctx.arc(n.x - r * 0.2, n.y - r * 0.2, r * 0.35, 0, 2 * Math.PI); ctx.fillStyle = 'rgba(255,255,255,0.22)'; ctx.fill();
		ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 1.5; ctx.stroke();
		const fs = 13 / gs;
		ctx.font = `700 ${fs}px Inter,system-ui,sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
		ctx.fillStyle = dark ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.85)'; ctx.fillText(n.name, n.x, n.y + r + 16 / gs);
	}

	function drawChat(n: any, ctx: CanvasRenderingContext2D, gs: number, dark: boolean, hover: boolean, sel: boolean) {
		const r = Math.sqrt(n.val) * 4; const w = r * 3.5; const h = r * 1.8;
		const x = n.x - w / 2; const y = n.y - h / 2; const rad = 8;
		if (hover || sel) { ctx.shadowColor = sel ? 'rgba(99,102,241,0.6)' : 'rgba(99,102,241,0.35)'; ctx.shadowBlur = sel ? 20 : 14; }
		rr(ctx, x, y, w, h, rad);
		const bg = ctx.createLinearGradient(x, y, x + w, y + h);
		if (dark) { bg.addColorStop(0, sel ? 'rgba(99,102,241,0.25)' : hover ? 'rgba(99,102,241,0.18)' : 'rgba(30,30,60,0.65)'); bg.addColorStop(1, sel ? 'rgba(79,70,229,0.2)' : hover ? 'rgba(79,70,229,0.12)' : 'rgba(20,20,50,0.55)'); }
		else { bg.addColorStop(0, sel ? 'rgba(238,235,255,1)' : hover ? 'rgba(245,243,255,1)' : 'rgba(255,255,255,0.92)'); bg.addColorStop(1, sel ? 'rgba(224,218,255,1)' : hover ? 'rgba(238,235,255,1)' : 'rgba(248,247,255,0.85)'); }
		ctx.fillStyle = bg; ctx.fill(); ctx.shadowBlur = 0;
		rr(ctx, x, y, w, h, rad);
		ctx.strokeStyle = dark ? (sel ? 'rgba(139,92,246,0.7)' : hover ? 'rgba(139,92,246,0.5)' : 'rgba(99,102,241,0.2)') : (sel ? 'rgba(99,102,241,0.6)' : hover ? 'rgba(99,102,241,0.4)' : 'rgba(99,102,241,0.12)');
		ctx.lineWidth = sel ? 2 : hover ? 1.5 : 1; ctx.stroke();
		rr(ctx, x + 3, y + 4, 3, h - 8, 1.5); ctx.fillStyle = `hsl(${n.hue || 250}, 65%, 62%)`; ctx.fill();
		ctx.beginPath(); ctx.arc(x + 14, n.y, n.val > 14 ? 3.5 : 2.5, 0, 2 * Math.PI); ctx.fillStyle = `hsl(${n.hue || 250}, 55%, ${dark ? '68' : '52'}%)`; ctx.fill();
		if (gs > 0.35) {
			const fs = Math.max(9 / gs, 3); ctx.font = `600 ${fs}px Inter,system-ui,sans-serif`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
			ctx.fillStyle = dark ? 'rgba(255,255,255,0.9)' : 'rgba(15,15,30,0.88)';
			ctx.fillText(n.name.length > 22 ? n.name.substring(0, 20) + '…' : n.name, x + 22, n.y, w - 28);
		}
	}

	function drawMem(n: any, ctx: CanvasRenderingContext2D, gs: number, dark: boolean, hover: boolean, sel: boolean) {
		const r = sel ? 11 : hover ? 10 : 8;
		if (hover || sel) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 7, 0, 2 * Math.PI); ctx.fillStyle = sel ? 'rgba(52,211,153,0.2)' : 'rgba(52,211,153,0.12)'; ctx.fill(); }
		ctx.beginPath(); ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y); ctx.lineTo(n.x, n.y + r); ctx.lineTo(n.x - r, n.y); ctx.closePath();
		const dg = ctx.createLinearGradient(n.x - r, n.y - r, n.x + r, n.y + r);
		dg.addColorStop(0, dark ? 'rgba(16,185,129,0.18)' : 'rgba(16,185,129,0.14)'); dg.addColorStop(1, dark ? 'rgba(5,150,105,0.08)' : 'rgba(5,150,105,0.06)');
		ctx.fillStyle = dg; ctx.fill();
		ctx.strokeStyle = dark ? (sel ? '#6ee7b7' : '#34d399') : (sel ? '#047857' : '#10b981'); ctx.lineWidth = sel ? 2.5 : hover ? 1.8 : 1.2; ctx.stroke();
		ctx.beginPath(); ctx.moveTo(n.x, n.y - r * 0.4); ctx.lineTo(n.x + r * 0.4, n.y); ctx.lineTo(n.x, n.y + r * 0.4); ctx.lineTo(n.x - r * 0.4, n.y); ctx.closePath();
		ctx.fillStyle = dark ? 'rgba(52,211,153,0.12)' : 'rgba(16,185,129,0.08)'; ctx.fill();
		if (gs > 1 || hover || sel) {
			const fs = Math.max(7.5 / gs, 2.5); ctx.font = `500 ${fs}px Inter,system-ui,sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
			ctx.fillStyle = dark ? 'rgba(167,243,208,0.9)' : 'rgba(5,150,105,0.8)'; ctx.fillText(n.name, n.x, n.y - r - 8 / gs);
		}
	}

	function rr(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
		ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y);
		ctx.quadraticCurveTo(x + w, y, x + w, y + r); ctx.lineTo(x + w, y + h - r);
		ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h); ctx.lineTo(x + r, y + h);
		ctx.quadraticCurveTo(x, y + h, x, y + h - r); ctx.lineTo(x, y + r);
		ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
	}

	function refreshGraph() { if (!graph || !mounted) return; graph.graphData(buildGraphData()); setTimeout(() => graph?.zoomToFit(500, 50), 500); }
	$: if (mounted && graph) { showChats; showMemory; refreshGraph(); }

	onMount(() => { mounted = true; setTimeout(initGraph, 300); });
	onDestroy(() => { mounted = false; if (animFrame) cancelAnimationFrame(animFrame); if (graph) { graph._destructor?.(); graph = null; } });
</script>

<div class="w-full h-full relative" style="min-height: 400px;">
	<div bind:this={container} class="absolute inset-0"></div>

	<!-- Selection Preview Panel (right side) — ONLY shown inside graph -->
	{#if selectedNode}
		<div class="absolute top-4 right-4 z-20 w-64" in:fly={{ x: 20, duration: 200 }} out:fly={{ x: 20, duration: 150 }}>
			<div class="bg-white/95 dark:bg-gray-900/90 border border-gray-200 dark:border-white/10 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden">
				<div class="px-4 py-2.5 border-b border-gray-100 dark:border-white/5 flex items-center justify-between bg-gray-50/80 dark:bg-black/30">
					<div class="flex items-center gap-2">
						{#if selectedNode.type === 'chat'}
							<span class="size-2 rounded-full bg-indigo-500"></span>
							<span class="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-white/50">Чат</span>
						{:else}
							<span class="size-2 rotate-45 bg-emerald-500"></span>
							<span class="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-white/50">Факт</span>
						{/if}
					</div>
					<button class="p-1 text-gray-400 hover:text-gray-600 dark:text-white/30 dark:hover:text-white/60 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition" on:click={() => selectedNode = null}>
						<svg class="size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>
				<div class="p-4">
					{#if selectedNode.type === 'chat'}
						<h3 class="text-sm font-bold text-gray-900 dark:text-white mb-2 leading-snug">{selectedNode.name}</h3>
						{#if selectedNode.raw?.tags?.length}
							<div class="flex flex-wrap gap-1 mb-2">
								{#each selectedNode.raw.tags as tag}
									<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20 uppercase tracking-wider">{typeof tag === 'string' ? tag : tag.name}</span>
								{/each}
							</div>
						{/if}
						<button
							class="w-full mt-1 py-2 text-xs font-bold text-white bg-gradient-to-r from-indigo-500 to-violet-600 rounded-xl hover:brightness-110 transition-all shadow-md shadow-indigo-500/20 flex items-center justify-center gap-2"
							on:click={() => goto(`/c/${selectedNode.chatId}`)}
						>
							Открыть чат →
						</button>
					{:else}
						<p class="text-xs text-gray-700 dark:text-white/80 leading-relaxed">{selectedNode.fullText || selectedNode.name}</p>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>
