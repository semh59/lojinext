import tsParser from "@typescript-eslint/parser";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";

export default [
    {
        ignores: [
            "dist/**",
            "node_modules/**",
            "coverage/**",
            "e2e/**",        // Playwright fixtures use `use` keyword
            "playwright.config.ts",
        ],
    },
    {
        files: ["**/*.{ts,tsx}"],
        languageOptions: {
            parser: tsParser,
            parserOptions: {
                ecmaVersion: "latest",
                sourceType: "module",
                ecmaFeatures: { jsx: true },
            },
            globals: {
                ...globals.browser,
                ...globals.node,
            },
        },
        plugins: {
            "react-hooks": reactHooks,
        },
        rules: {
            "react-hooks/rules-of-hooks": "error",
            // exhaustive-deps: many existing init-only effects intentionally
            // omit deps. Enable as warn (off-by-default for max-warnings=0)
            // and revisit per-effect in a dedicated cleanup PR.
            "react-hooks/exhaustive-deps": "off",
        },
    },
];
