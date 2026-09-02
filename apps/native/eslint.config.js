import eslintConfigNative from "@loopops/eslint-config-native";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslintConfigNative,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        project: "./tsconfig.json",
      },
    },
  },
);
