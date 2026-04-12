#!/usr/bin/env node
/**
 * Интерактивный релиз: выбор версии → bump → commit → tag → push.
 * Запуск: npm run release
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const pkgPath = join(root, 'package.json');

const rl = createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((r) => rl.question(q, r));

function run(cmd, opts = {}) {
	return execSync(cmd, { cwd: root, encoding: 'utf8', stdio: 'pipe', ...opts }).trim();
}

function runLoud(cmd) {
	execSync(cmd, { cwd: root, stdio: 'inherit' });
}

function parseForkVersion(v) {
	const m = v.match(/^(\d+)\.(\d+)\.(\d+)(-gpthub\.(\d+))?$/);
	if (!m) return null;
	return {
		major: +m[1],
		minor: +m[2],
		patch: +m[3],
		fork: m[5] !== undefined ? +m[5] : null,
		base: `${m[1]}.${m[2]}.${m[3]}`,
	};
}

function bold(s) {
	return `\x1b[1m${s}\x1b[0m`;
}
function green(s) {
	return `\x1b[32m${s}\x1b[0m`;
}
function yellow(s) {
	return `\x1b[33m${s}\x1b[0m`;
}
function cyan(s) {
	return `\x1b[36m${s}\x1b[0m`;
}
function dim(s) {
	return `\x1b[2m${s}\x1b[0m`;
}

async function main() {
	const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
	const current = pkg.version;
	const parsed = parseForkVersion(current);

	console.log('');
	console.log(bold('  GPTHub Release'));
	console.log(dim('  ─────────────────────────────────────'));
	console.log(`  Текущая версия:  ${cyan(current)}`);
	if (pkg.gpthub?.upstreamVersion) {
		console.log(`  Upstream (база):  ${dim(`Open WebUI ${pkg.gpthub.upstreamVersion}`)}`);
	}
	console.log('');
	console.log(yellow('  ⚠️  Перед релизом убедись, что CHANGELOG.md обновлён!'));
	console.log(dim('     Добавь секцию ## [<новая-версия>] - <дата> с описанием изменений.'));
	console.log(dim('     GitHub Release автоматически подтянет её текст.'));
	console.log('');
	const clOk = await ask('  CHANGELOG.md обновлён? [Y/n]: ');
	if (clOk && clOk.toLowerCase() !== 'y' && clOk !== '') {
		console.log(yellow('\n  Открой CHANGELOG.md, добавь запись и запусти скрипт снова.'));
		rl.close();
		process.exit(0);
	}
	console.log('');

	const suggestions = [];
	if (parsed) {
		const f = parsed.fork !== null ? parsed.fork : -1;
		const upstream = pkg.gpthub?.upstreamVersion ?? parsed.base;

		// Fork releases — base stays the same, only N increments
		suggestions.push({
			label: `фича/фикс форка  ${dim('(upstream не менялся)')}`,
			version: `${parsed.base}-gpthub.${f + 1}`,
		});

		// Upstream sync — bump upstream base, reset fork counter
		const [umaj, umin, upat] = upstream.split('.').map(Number);
		suggestions.push({
			label: `синк upstream: patch  ${dim(`OWU ${umaj}.${umin}.${upat + 1}`)}`,
			version: `${umaj}.${umin}.${upat + 1}-gpthub.0`,
		});
		suggestions.push({
			label: `синк upstream: minor  ${dim(`OWU ${umaj}.${umin + 1}.0`)}`,
			version: `${umaj}.${umin + 1}.0-gpthub.0`,
		});
		suggestions.push({
			label: `синк upstream: major  ${dim(`OWU ${umaj + 1}.0.0`)}`,
			version: `${umaj + 1}.0.0-gpthub.0`,
		});
	}

	console.log(bold('  Выберите тип релиза:'));
	console.log(dim('  ┌─ fork: только N меняется, upstream-база остаётся'));
	console.log(dim('  └─ sync: апдейт до новой версии Open WebUI'));
	console.log('');
	suggestions.forEach((s, i) => {
		console.log(`    ${bold(`${i + 1})`)}  ${green(s.version)}  ${dim(`— ${s.label}`)}`);
	});
	console.log(`    ${bold(`${suggestions.length + 1})`)}  Ввести вручную`);
	console.log('');

	const choice = await ask(`  Ваш выбор [1-${suggestions.length + 1}]: `);
	let newVersion;
	const idx = parseInt(choice, 10);

	if (idx >= 1 && idx <= suggestions.length) {
		newVersion = suggestions[idx - 1].version;
	} else {
		newVersion = await ask('  Введите версию (например 0.9.0-gpthub.0): ');
	}

	newVersion = newVersion.trim();
	if (!/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/.test(newVersion)) {
		console.error('\n  Некорректный формат версии.');
		process.exit(1);
	}

	console.log('');
	console.log(`  ${cyan(current)} → ${green(newVersion)}`);
	const confirm = await ask(`  Продолжить? [Y/n]: `);
	if (confirm && confirm.toLowerCase() !== 'y' && confirm !== '') {
		console.log('  Отменено.');
		process.exit(0);
	}

	console.log('');
	console.log(dim('  → Обновляю package.json, README, lock...'));
	runLoud(`node scripts/bump-version.mjs ${newVersion}`);

	console.log('');
	console.log(dim('  → Коммит...'));
	runLoud(`git add package.json package-lock.json README.md`);
	runLoud(`git commit -m "chore: release v${newVersion}"`);

	console.log('');
	console.log(dim(`  → Тег v${newVersion}...`));
	runLoud(`git tag -a v${newVersion} -m "v${newVersion}"`);

	console.log('');
	const branch = run('git rev-parse --abbrev-ref HEAD');
	const doPush = await ask(`  Запушить ${bold(branch)} + тег ${bold(`v${newVersion}`)} в origin? [Y/n]: `);
	if (!doPush || doPush.toLowerCase() === 'y' || doPush === '') {
		console.log(dim(`  → git push origin ${branch} --follow-tags`));
		runLoud(`git push origin ${branch} --follow-tags`);
		console.log('');
		console.log(green(`  Готово! Релиз v${newVersion} запушен.`));
		console.log(dim('  GitLab CI: verify → docker build → publish release.'));
	} else {
		console.log('');
		console.log(yellow('  Коммит и тег созданы локально. Пуш:'));
		console.log(`    git push origin ${branch} --follow-tags`);
	}
	console.log('');
	rl.close();
}

main().catch((e) => {
	console.error(e);
	rl.close();
	process.exit(1);
});
