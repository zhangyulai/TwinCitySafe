import { ref } from "vue";
import { defineStore } from "pinia";
import { getHealth } from "../api/health";
export const useServiceStore = defineStore("service", () => {
  const status = ref<"Checking" | "Online" | "Offline">("Checking");
  const checking = ref(false);
  async function checkHealth() {
    if (checking.value) return;
    checking.value = true;
    try {
      await getHealth();
      status.value = "Online";
    } catch {
      status.value = "Offline";
    } finally {
      checking.value = false;
    }
  }
  return { status, checking, checkHealth };
});
