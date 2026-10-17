export type SceneQuality = "high" | "medium" | "low";

/** Visual budgets only. No simulator or model parameter depends on quality. */
export const qualitySettings = {
  high: { pixelRatio: 2, shadowSize: 1024, rainCapacity: 1800, labels: 8, labelDistance: Infinity, postprocessing: true },
  medium: { pixelRatio: 1.5, shadowSize: 512, rainCapacity: 1000, labels: 3, labelDistance: 180, postprocessing: true },
  low: { pixelRatio: 1, shadowSize: 0, rainCapacity: 450, labels: 1, labelDistance: 145, postprocessing: false },
} as const;
