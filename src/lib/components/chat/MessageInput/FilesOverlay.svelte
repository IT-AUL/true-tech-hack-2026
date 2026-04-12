<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	export let show = false;
</script>

{#if show}
	<div
		class="absolute inset-0 w-full h-full flex z-[9999] touch-none pointer-events-none"
		id="dropzone"
		role="region"
		aria-label="Drag and Drop Container"
	>
		<div
			class="absolute w-full h-full backdrop-blur-sm bg-gray-100/60 dark:bg-gray-900/80 flex justify-center transition-all"
		>
			<div class="m-auto flex flex-col justify-center">
				<div class="max-w-sm mx-auto flex flex-col items-center gap-3 p-8 rounded-2xl border-2 border-dashed border-gray-300 dark:border-gray-600 bg-white/50 dark:bg-gray-800/50">
					<svg class="size-10 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
					</svg>
					<div class="text-center">
						<div class="text-sm font-medium text-gray-700 dark:text-gray-300">{$i18n.t('Drop files here')}</div>
						<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{$i18n.t('Images, documents, audio')}</div>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
