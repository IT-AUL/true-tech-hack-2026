#!/usr/bin/env node
/**
 * Обновляет версию форка везде в репозитории перед коммитом и тегом.
 *
 * Usage:
 *   node scripts/bump-version.mjs 0.8.12-gpthub.1
 *   node scripts/bump-version.mjs 0.8.12-gpthub.1 --upstream 0.8.12
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');

const args = process.argv.slice(2);
let upstreamArg = null;
const versionArgs = [];
for (let i = 0; i < args.length; i++) {
	if (args[i] === '--upstream' && args[i + 1]) {
		upstreamArg = args[++i];
	} else if (!args[i].startsWith('-')) {
		versionArgs.push(args[i]);
	}
}

const newVersion = versionArgs[0];
if (!newVersion || !/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/.test(newVersion)) {
	console.error(
		'Usage: node scripts/bump-version.mjs <semver> [--upstream <upstream-base>]\n' +
			'Example: node scripts/bump-version.mjs 0.8.12-gpthub.1 --upstream 0.8.12',
	);
	process.exit(1);
}

const pkgPath = join(root, 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
pkg.version = newVersion;

if (!pkg.gpthub) {
	pkg.gpthub = {
		forkName: 'GPTHub',
		upstreamName: 'Open WebUI',
		upstreamVersion: '0.8.12',
		upstreamUrl: 'https://github.com/open-webui/open-webui',
	};
}

if (upstreamArg) {
	pkg.gpthub.upstreamVersion = upstreamArg;
} else {
	const m = newVersion.match(/^(\d+\.\d+\.\d+)-gpthub(?:\.|$)/);
	if (m) {
		pkg.gpthub.upstreamVersion = m[1];
	}
}

writeFileSync(pkgPath, `${JSON.stringify(pkg, null, '\t')}\n`, 'utf8');

const readmePath = join(root, 'README.md');
let readme = readFileSync(readmePath, 'utf8');

const releaseMsg = encodeURIComponent(newVersion);
const upstreamMsg = encodeURIComponent(`Open WebUI ${pkg.gpthub.upstreamVersion}`);

if (readme.includes('label=release&message=')) {
	readme = readme.replace(
		/(label=release&)message=[^&]+/,
		`$1message=${releaseMsg}`,
	);
	readme = readme.replace(
		/(label=upstream&)message=[^&]+/,
		`$1message=${upstreamMsg}`,
	);
} else {
	readme = readme.replace(
		/https:\/\/img\.shields\.io\/badge\/version-[^-]+-blue\.svg/,
		`https://img.shields.io/static/v1?label=release&message=${releaseMsg}&color=blue`,
	);
}

writeFileSync(readmePath, readme, 'utf8');

try {
	execSync('npm install --package-lock-only --ignore-scripts', {
		cwd: root,
		stdio: 'inherit',
	});
} catch {
	console.warn('npm install --package-lock-only failed; run npm install manually.');
}

console.log(`Updated package.json version → ${newVersion}`);
console.log(`Updated README badges (release / upstream)`);
console.log(`gpthub.upstreamVersion → ${pkg.gpthub.upstreamVersion}`);
console.log('\nNext: git add package.json package-lock.json README.md && git commit -m "chore: release v' + newVersion + '"');
console.log(`       git tag -a v${newVersion} -m "v${newVersion}" && git push origin <branch> && git push origin v${newVersion}`);
