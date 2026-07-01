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
            // 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): eskiden
            // "off" idi (hiçbir stale-closure bug'ı yakalanmıyordu). 13
            // mevcut ihlal bulunup düzeltildi (kalıcı mount-only init
            // efektleri eslint-disable ile belgelendi), artık error.
            "react-hooks/exhaustive-deps": "error",
        },
    },
];
