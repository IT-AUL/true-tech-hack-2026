#!/usr/bin/env node
/**
 * CI: тег v* должен совпадать с "version" в package.json (v + semver).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
const tag = process.env.CI_COMMIT_TAG;

if (!tag) {
	console.error('CI_COMMIT_TAG is not set');
	process.exit(1);
}

const expected = `v${pkg.version}`;
if (tag !== expected) {
	console.error(
		`Version mismatch: git tag is "${tag}" but package.json has "version": "${pkg.version}" (expected tag ${expected}).\n` +
			'Run: node scripts/bump-version.mjs <version> && commit, then tag again.',
	);
	process.exit(1);
}

console.log(`OK: tag ${tag} matches package.json version ${pkg.version}`);
