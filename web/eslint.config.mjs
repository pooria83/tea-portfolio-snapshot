import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import tseslint from "typescript-eslint";
import sonarjs from "eslint-plugin-sonarjs";
import unicorn from "eslint-plugin-unicorn";
import security from "eslint-plugin-security";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  ...tseslint.configs.recommended,
  unicorn.configs["flat/recommended"],
  security.configs.recommended,
  {
    plugins: {
      sonarjs,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "react/no-unescaped-entities": "off",
      "@next/next/no-img-element": "off",

      "unicorn/no-null": "off",
      "unicorn/filename-case": "off",
      "unicorn/prevent-abbreviations": "off",
      "unicorn/no-array-reduce": "off",
      "unicorn/consistent-function-scoping": "off",
      "unicorn/prefer-spread": "off",
      "unicorn/no-abusive-eslint-disable": "error",
      "unicorn/catch-error-name": ["error", { "name": "error", "ignore": ["err"] }],
      "unicorn/no-document-cookie": "off",
      "unicorn/prefer-global-this": "off",

      "sonarjs/cognitive-complexity": ["warn", 20],
      "sonarjs/no-identical-functions": "warn",
      "sonarjs/no-identical-expressions": "error",
      "sonarjs/no-duplicated-branches": "error",
      "sonarjs/no-collapsible-if": "error",
      "sonarjs/no-collection-size-mischeck": "error",
      "sonarjs/no-gratuitous-expressions": "error",
      "sonarjs/no-element-overwrite": "error",
      "sonarjs/prefer-single-boolean-return": "error",
      "sonarjs/prefer-immediate-return": "warn",
      "sonarjs/no-empty-collection": "error",
      "sonarjs/no-use-of-empty-return-value": "error",
      "sonarjs/no-extra-arguments": "error",
      "sonarjs/no-identical-conditions": "error",
      "sonarjs/no-redundant-boolean": "error",
      "sonarjs/no-redundant-jump": "error",
      "sonarjs/no-small-switch": "warn",
      "sonarjs/no-unused-collection": "error",
      "sonarjs/no-useless-catch": "error",
      "sonarjs/no-parameter-reassignment": "error",
      "sonarjs/function-inside-loop": "error",
      "sonarjs/jsx-no-leaked-render": "error",
      "sonarjs/no-useless-react-setstate": "error",
      "sonarjs/no-nested-assignment": "error",
      "sonarjs/no-nested-conditional": "warn",
      "sonarjs/prefer-while": "warn",
      "sonarjs/no-inverted-boolean-check": "warn",
      "sonarjs/no-redundant-parentheses": "warn",
      "sonarjs/no-alphabetical-sort": "warn",
      "sonarjs/todo-tag": "warn",
      "sonarjs/fixme-tag": "warn",

      "security/detect-object-injection": "off",
      "security/detect-possible-timing-attacks": "off",
      "security/detect-non-literal-fs-filename": "off",
      "security/detect-child-process": "off",
      "security/detect-non-literal-require": "off",
    },
  },
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    languageOptions: {
      parserOptions: {
        projectService: true,
      },
    },
    rules: {
      "@typescript-eslint/no-floating-promises": "error",
    },
  },
  {
    files: ["src/components/ui/**", "src/hooks/use-mobile.ts"],
    rules: {
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/refs": "off",
    },
  },
  {
    files: ["**/__tests__/**", "*.test.*", "*.spec.*"],
    rules: {
      "sonarjs/no-redundant-boolean": "off",
      "unicorn/error-message": "off",
      "unicorn/no-array-for-each": "off",
    },
  },
  {
    files: ["vitest.config.ts", "playwright.config.ts"],
    rules: {
      "unicorn/prefer-module": "off",
      "unicorn/numeric-separators-style": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
