import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";

export default tseslint.config(
  { ignores: ["dist", "node_modules/"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      // Add React Native specific configuration if needed, for now use generic React
    ],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.jest,
        ...globals.node,
      },
      parser: tseslint.parser,
      parserOptions: {
        project: ["./tsconfig.json", "./apps/*/tsconfig.json"],
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      ...reactPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^\\_" }],
      "@typescript-eslint/no-explicit-any": "warn",
      "react/react-in-jsx-scope": "off", // Not needed for React 17+
    },
    settings: {
      react: {
        version: "detect", // Automatically detect the React version
      },
    },
  },
);
