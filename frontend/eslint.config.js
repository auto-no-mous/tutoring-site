import eslintPluginVue from "eslint-plugin-vue";
import tseslint from "typescript-eslint";
import vueTsEslintConfig from "@vue/eslint-config-typescript";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },
  // "essential" (correctness only) rather than "recommended"/"strongly-recommended":
  // this codebase intentionally uses compact single-line tags and multi-attribute
  // lines throughout, which the stricter presets treat as violations - pulling those
  // in would flag ~1000 pre-existing, stylistically-fine lines instead of real bugs.
  eslintPluginVue.configs["flat/essential"],
  vueTsEslintConfig(),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "vue/multi-word-component-names": "off",
      // Rich-text "about" fields go through sanitizeRichText (see utils/richText.ts)
      // before ever reaching v-html - the handful of call sites are a reviewed,
      // deliberate pattern, not an oversight this rule needs to keep flagging.
      "vue/no-v-html": "off",
    },
  },
);
