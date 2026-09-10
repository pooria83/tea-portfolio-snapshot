import {defineConfig, globalIgnores} from 'eslint/config';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import eslintConfigPrettier from 'eslint-config-prettier';
import localRules from './eslint-local-plugin.mjs';

export default defineConfig([
  globalIgnores([
    'node_modules/**',
    'android/**',
    'ios/**',
    'Pods/**',
    'coverage/**',
    'e2e/**',
    'metro.config.js',
    'babel.config.js',
    'jest.config.js',
  ]),
  ...tseslint.configs.recommendedTypeChecked.map((config) => ({
    ...config,
    files: ['src/**/*.{ts,tsx}'],
  })),
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: ['__tests__/**/*.{ts,tsx}'],
  })),
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {prefer: 'type-imports'},
      ],
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {argsIgnorePattern: '^_', varsIgnorePattern: '^_'},
      ],
      '@typescript-eslint/no-misused-promises': [
        'error',
        {checksVoidReturn: false},
      ],
      '@typescript-eslint/prefer-promise-reject-errors': [
        'error',
        {allowThrowingAny: true, allowThrowingUnknown: true},
      ],
      'no-console': 'warn',
    },
  },
  {
    files: ['src/services/logging/logger.ts'],
    rules: {
      'no-console': 'off',
    },
  },
  {
    files: ['__tests__/setup.ts'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  {
    files: ['__tests__/**/*.{ts,tsx}'],
    plugins: {
      'react-hooks': reactHooks,
      local: localRules,
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      'local/no-direct-result-current-assertion': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {prefer: 'type-imports'},
      ],
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {argsIgnorePattern: '^_', varsIgnorePattern: '^_'},
      ],
      'no-console': 'warn',
    },
  },
  eslintConfigPrettier,
]);
