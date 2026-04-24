<script lang="ts">
	import { models, showSettings, settings, user, mobile, config } from '$lib/stores';
	import { onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Selector from './ModelSelector/Selector.svelte';
	import Tooltip from '../common/Tooltip.svelte';

	import { updateUserSettings } from '$lib/apis/users';
	const i18n = getContext('i18n');

	export let selectedModels = [''];
	export let disabled = false;
	export let showSetDefault = false; // Intentionally ignored in the new minimal design

	const pinModelHandler = async (modelId) => {
		let pinnedModels = $settings?.pinnedModels ?? [];

		if (pinnedModels.includes(modelId)) {
			pinnedModels = pinnedModels.filter((id) => id !== modelId);
		} else {
			pinnedModels = [...new Set([...pinnedModels, modelId])];
		}

		settings.set({ ...$settings, pinnedModels: pinnedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	$: if (selectedModels.length > 0 && $models.length > 0) {
		const _selectedModels = selectedModels.map((model) =>
			$models.map((m) => m.id).includes(model) ? model : ''
		);

		if (JSON.stringify(_selectedModels) !== JSON.stringify(selectedModels)) {
			selectedModels = _selectedModels;
		}
	}
</script>

<div id="tour-model-selector" class="flex items-center gap-1">
	{#each selectedModels as selectedModel, selectedModelIdx}
		<div class="flex items-center gap-1 shrink-0">
			<Selector
				id={`${selectedModelIdx}`}
				placeholder={$i18n.t('Select a model')}
				items={$models.map((model) => ({
					value: model.id,
					label: model.name,
					model: model
				}))}
				{pinModelHandler}
				bind:value={selectedModel}
			/>

			{#if $user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true)}
				{#if selectedModelIdx === 0 && selectedModels.length === 1}
					<Tooltip content={$i18n.t('Add Model')}>
						<button
							class="text-gray-300 hover:text-gray-500 transition-colors disabled:opacity-50 px-1"
							{disabled}
							on:click={() => { selectedModels = [...selectedModels, '']; }}
							aria-label="Add Model"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-3"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
						</button>
					</Tooltip>
				{:else if selectedModelIdx > 0}
					<Tooltip content={$i18n.t('Remove Model')}>
						<button
							class="text-gray-300 hover:text-gray-500 transition-colors disabled:opacity-50 px-1"
							{disabled}
							on:click={() => {
								selectedModels.splice(selectedModelIdx, 1);
								selectedModels = selectedModels;
							}}
							aria-label="Remove Model"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-3"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" /></svg>
						</button>
					</Tooltip>
				{/if}
			{/if}
		</div>
	{/each}
</div>
