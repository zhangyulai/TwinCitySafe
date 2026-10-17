import { defineStore } from 'pinia';
import { ref } from 'vue';
import { demoApi, actionError, type Readiness } from '../api/demo';
import { useRealtimeStore } from './useRealtimeStore';
function storedMode() { try { return sessionStorage.getItem('twincity-demo') === '1'; } catch { return false; } }
export const useDemoStore = defineStore('demo', () => {
  const enabled = ref(new URLSearchParams(location.search).get('demo') === '1' || storedMode());
  const readiness = ref<Readiness | null>(null), checking = ref(false), busy = ref(false), error = ref(''), notice = ref('');
  function setEnabled(value: boolean) { enabled.value = value; try { sessionStorage.setItem('twincity-demo', value ? '1' : '0'); } catch { /* storage is optional */ } }
  async function check() {
    if (checking.value) return;
    checking.value = true;
    try { readiness.value = await demoApi.readiness(); } catch { readiness.value = null; } finally { checking.value = false; }
  }
  async function control(action: string, body: Record<string, unknown> = {}) {
    if (busy.value) return false;
    busy.value = true; error.value = ''; notice.value = '';
    try {
      const state = await demoApi.control(action, body);
      useRealtimeStore().applyRealtimeState(state);
      notice.value = ({ start: '演示已启动，状态由实时仿真推进。', reset: '已恢复正常监测，历史档案已保留。', pause: '仿真已暂停。', resume: '仿真已继续。', speed: '仿真速度已更新。' } as Record<string, string>)[action] ?? '操作完成。';
      return true;
    } catch (e) { error.value = actionError(e); return false; } finally { busy.value = false; }
  }
  return { enabled, setEnabled, readiness, checking, busy, error, notice, check, control };
});
