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

	const suggestions = [];
	if (parsed) {
		const f = parsed.fork !== null ? parsed.fork : -1;
		suggestions.push({
			label: 'gpthub (фикс/фича форка)',
			version: `${parsed.base}-gpthub.${f + 1}`,
		});
		suggestions.push({
			label: 'patch (базовый патч)',
			version: `${parsed.major}.${parsed.minor}.${parsed.patch + 1}-gpthub.0`,
		});
		suggestions.push({
			label: 'minor (новый минор)',
			version: `${parsed.major}.${parsed.minor + 1}.0-gpthub.0`,
		});
		suggestions.push({
			label: 'major (мажорный)',
			version: `${parsed.major + 1}.0.0-gpthub.0`,
		});
	}

	console.log(bold('  Выберите версию:'));
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
