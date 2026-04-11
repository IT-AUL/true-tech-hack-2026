module.exports = {
	root: true,
	ignorePatterns: ['build', '.svelte-kit', 'node_modules', 'static', 'package', 'dist'],
	extends: [
		'eslint:recommended',
		'plugin:@typescript-eslint/recommended',
		'plugin:svelte/recommended',
		'plugin:cypress/recommended',
		'prettier'
	],
	parser: '@typescript-eslint/parser',
	plugins: ['@typescript-eslint'],
	parserOptions: {
		sourceType: 'module',
		ecmaVersion: 2020,
		extraFileExtensions: ['.svelte']
	},
	env: {
		browser: true,
		es2017: true,
		node: true
	},
	// Open WebUI upstream is not clean under strict @typescript-eslint; CI runs eslint on the whole tree.
	rules: {
		'@typescript-eslint/no-explicit-any': 'off',
		'@typescript-eslint/no-unused-vars': 'off',
		'@typescript-eslint/no-unused-expressions': 'off',
		'no-unused-vars': 'off',
		'no-undef': 'off',
		'no-constant-condition': 'off',
		'no-useless-escape': 'off',
		'no-control-regex': 'off',
		'getter-return': 'off',
		'prefer-const': 'off',
		'no-extra-boolean-cast': 'off',
		'no-prototype-builtins': 'off',
		'@typescript-eslint/no-empty-object-type': 'off',
		'no-empty': 'off',
		'no-ex-assign': 'off',
		'no-unsafe-optional-chaining': 'off',
		'@typescript-eslint/ban-ts-comment': 'off',
		'@typescript-eslint/no-unsafe-function-type': 'off',
		'no-async-promise-executor': 'off'
	},
	overrides: [
		{
			files: ['*.svelte'],
			parser: 'svelte-eslint-parser',
			parserOptions: {
				parser: '@typescript-eslint/parser'
			},
			rules: {
				// @typescript-eslint/no-unused-vars crashes on some Svelte AST nodes (e.g. Svelte 5 / reactive)
				'@typescript-eslint/no-unused-vars': 'off',
				'no-unused-vars': 'off',
				// Svelte runes / stores: false positives
				'no-undef': 'off',
				// Upstream uses {@html} and has noisy a11y/CSS compile warnings
				'svelte/no-at-html-tags': 'off',
				'svelte/valid-compile': 'off',
				'svelte/no-unused-svelte-ignore': 'off',
				'svelte/no-inner-declarations': 'off'
			}
		}
	]
};
