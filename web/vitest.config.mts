import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // テスト対象は集計ロジック（純粋関数）だけ。
    // Reactコンポーネントの描画テストはしない（見た目は手動確認で足りる）。
    include: ["lib/**/*.test.ts"],
    environment: "node",
  },
});
