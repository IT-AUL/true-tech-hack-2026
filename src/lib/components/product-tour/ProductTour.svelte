<script lang="ts">
	import { onMount } from 'svelte';
	import { driver } from 'driver.js';
	import 'driver.js/dist/driver.css';

	import { page } from '$app/stores';
	import { selectedProjectId } from '$lib/stores';

	let driverObj: any = null;

	const startHomeTour = () => {
		driverObj = driver({
			showProgress: true,
			animate: true,
			popoverClass: 'driver-theme-dark-studio',
			steps: [
				{
					popover: {
						title: 'VibeHub: Единый интеллект-хаб 🌌',
						description: 'Добро пожаловать. Это не просто чат, а ваш личный центр управления ИИ-агентами.',
						side: 'center',
						align: 'center'
					}
				},
				{
					element: '#tour-logo',
					popover: {
						title: 'Контроль и фокус',
						description: 'Центральная точка управления вашим присутствием в системе.',
						side: 'bottom',
						align: 'center'
					}
				},
				{
					element: '#tour-smart-actions',
					popover: {
						title: 'Генерация и Сценарии',
						description: 'Нужен отчет, файл или изображение? Смарт-задачи запустят нужные инструменты в один клик.',
						side: 'top',
						align: 'center'
					}
				},
				{
					element: '#tour-ai-insights',
					popover: {
						title: 'Автоподбор и Маршрутизация',
						description: 'VibeHub анализирует ваш запрос и автоматически выбирает лучшую модель для задачи. Вы видите этот процесс в реальном времени.',
						side: 'bottom',
						align: 'center'
					}
				},
				{
					element: '#tour-add-space',
					popover: {
						title: 'Создайте свое первое Пространство',
						description: 'Разделите чаты по проектам. Создайте новое пространство, чтобы AI получил отдельную память для конкретной работы.',
						side: 'right',
						align: 'center'
					}
				},
				{
					element: '#tour-spaces-column',
					popover: {
						title: 'Ваша ИИ-Вселенная',
						description: 'Список всех активных пространств. Каждое — со своей историей и базой знаний.',
						side: 'right',
						align: 'start'
					}
				}
			],
			onPopoverRender: (popover) => {
				popover.nextButton.innerText = 'Далее';
				popover.previousButton.innerText = 'Назад';
				popover.closeButton.innerHTML = '&times;';
			}
		});
		driverObj.drive();
	};

	const startSpaceTour = () => {
		driverObj = driver({
			showProgress: true,
			animate: true,
			popoverClass: 'driver-theme-dark-studio',
			steps: [
				{
					popover: {
						title: 'Пространство: Режим глубокого контекста 🧠',
						description: 'Вы перешли в автономный проектный модуль. Здесь всё работает на вашу экспертизу.',
						side: 'center',
						align: 'center'
					}
				},
				{
					element: '#tour-space-header',
					popover: {
						title: 'Мониторинг Автороутинга',
						description: 'Следите за тем, как система распределяет нагрузку между моделями внутри этого проекта.',
						side: 'bottom',
						align: 'start'
					}
				},
				{
					element: '#tour-space-memory',
					popover: {
						title: 'База знаний (Memory V2)',
						description: 'AI автоматически извлекает факты. Ни одно ваше решение не будет забыто — оно станет частью "памяти" проекта.',
						side: 'left',
						align: 'start'
					}
				},
				{
					element: '#tour-space-mindmap',
					popover: {
						title: 'Графы знаний и Связи',
						description: 'Визуализируйте, как ваши чаты и факты связаны между собой. Это ваша карта смыслов проекта.',
						side: 'bottom',
						align: 'center'
					}
				},
				{
					element: '#tour-input-menu',
					popover: {
						title: 'Мультимедиа и Файлы',
						description: 'Генерируйте изображения, создавайте документы или подключайте Google Drive прямо здесь.',
						side: 'top',
						align: 'start'
					}
				},
				{
					element: '#tour-voice-control',
					popover: {
						title: 'Голосовая диктовка',
						description: 'Некогда писать? Используйте STT-движок для быстрой диктовки запросов.',
						side: 'top',
						align: 'center'
					}
				},
				{
					element: '#tour-voice-mode',
					popover: {
						title: 'Голосовой режим (Call)',
						description: 'Перейдите в режим живого диалога. AI будет слушать и отвечать голосом в реальном времени.',
						side: 'top',
						align: 'center'
					}
				},
				{
					element: '#tour-model-selector',
					popover: {
						title: 'Управление движками',
						description: 'В любой момент можно переключить модель вручную или оставить это на откуп автоподбору.',
						side: 'top',
						align: 'center'
					}
				},
				{
					element: '#tour-send-button',
					popover: {
						title: 'Запуск мысли',
						description: 'Нажмите Enter или кнопку отправки, чтобы получить ответ от вашего цифрового разума.',
						side: 'top',
						align: 'end'
					}
				}
			],
			onPopoverRender: (popover, { state }) => {
				popover.nextButton.innerText = state.isLastStep ? 'К работе!' : 'Далее';
				popover.previousButton.innerText = 'Назад';
			}
		});
		driverObj.drive();
	};

	onMount(() => {
		setTimeout(() => {
			const isHomePage = window.location.pathname === '/';
			const isSpacePage = $selectedProjectId !== null;

			if (isHomePage && !isSpacePage && !localStorage.getItem('homeTourDone')) {
				startHomeTour();
				localStorage.setItem('homeTourDone', 'true');
			} else if (isSpacePage && !localStorage.getItem(`spaceTour_${$selectedProjectId}`)) {
				startSpaceTour();
				localStorage.setItem(`spaceTour_${$selectedProjectId}`, 'true');
			}
		}, 1000);
	});

	// Reactively trigger Space tour when entering a space
	$: if ($selectedProjectId && !localStorage.getItem(`spaceTour_${$selectedProjectId}`)) {
		setTimeout(startSpaceTour, 500);
		localStorage.setItem(`spaceTour_${$selectedProjectId}`, 'true');
	}
</script>

<style>
	:global(.driver-theme-dark-studio) {
		background-color: rgba(255, 255, 255, 0.95) !important;
		border-radius: 16px !important;
		padding: 20px !important;
		box-shadow: 0 10px 40px -10px rgba(0,0,0,0.3) !important;
		border: 1px solid rgba(0,0,0,0.05) !important;
		color: #1a1a1a !important;
		font-family: inherit !important;
	}

	:global(html.dark .driver-theme-dark-studio) {
		background-color: rgba(20, 20, 20, 0.85) !important;
		backdrop-filter: blur(16px) !important;
		-webkit-backdrop-filter: blur(16px) !important;
		color: #f3f4f6 !important;
		border: 1px solid rgba(255,255,255,0.08) !important;
		box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5) !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-title) {
		font-size: 1.15rem !important;
		font-weight: 600 !important;
		margin-bottom: 8px !important;
		border-bottom: none !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-description) {
		font-size: 0.95rem !important;
		line-height: 1.5 !important;
		opacity: 0.85 !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-footer) {
		margin-top: 16px !important;
		display: flex !important;
		justify-content: space-between !important;
		align-items: center !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-progress-text) {
		font-size: 0.8rem !important;
		font-weight: 500 !important;
		opacity: 0.6 !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-prev-btn),
	:global(.driver-theme-dark-studio .driver-popover-next-btn) {
		border: none !important;
		border-radius: 8px !important;
		padding: 6px 14px !important;
		font-size: 0.85rem !important;
		font-weight: 500 !important;
		cursor: pointer !important;
		transition: all 0.2s !important;
		text-shadow: none !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-prev-btn) {
		background: transparent !important;
		color: inherit !important;
		opacity: 0.6 !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-prev-btn:hover) {
		opacity: 1 !important;
		background: rgba(0,0,0,0.05) !important;
	}
	:global(html.dark .driver-theme-dark-studio .driver-popover-prev-btn:hover) {
		background: rgba(255,255,255,0.1) !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-next-btn) {
		background: #6366f1 !important; /* Indigo-500 */
		color: white !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-next-btn:hover) {
		background: #4f46e5 !important;
	}

	:global(.driver-theme-dark-studio .driver-popover-close-btn) {
		top: 15px !important;
		right: 15px !important;
		color: inherit !important;
		opacity: 0.5 !important;
	}
	:global(.driver-theme-dark-studio .driver-popover-close-btn:hover) {
		opacity: 1 !important;
	}
</style>
