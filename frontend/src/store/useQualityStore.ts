import { defineStore } from "pinia";
import { ref } from "vue";
import type { SceneQuality } from "../three/types/quality";

const storageKey = "twincity-quality";
function initialQuality(): SceneQuality {
  try { const saved = localStorage.getItem(storageKey); if (saved === "high" || saved === "medium" || saved === "low") return saved; } catch { /* Browser storage may be disabled. */ }
  return "high";
}
export const useQualityStore = defineStore("scene-quality", () => {
  const quality = ref<SceneQuality>(initialQuality());
  function setQuality(value: SceneQuality): void {
    if (!(value === "high" || value === "medium" || value === "low")) return;
    quality.value = value;
    try { localStorage.setItem(storageKey, value); } catch { /* Keep the current in-memory choice. */ }
  }
  return { quality, setQuality };
});
