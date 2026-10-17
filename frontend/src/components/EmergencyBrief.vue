<script setup lang="ts">
import {useRealtimeStore} from '../store/useRealtimeStore';import {emergencyPhaseLabels} from '../types/emergency';import '../views/Simulation/emergency.css';const rt=useRealtimeStore();
</script><template><div v-if="rt.state?.emergency" class="emergency-brief" data-testid="emergency-brief">当前应急：{{rt.state.emergency.plan_code}} · {{emergencyPhaseLabels[rt.state.emergency.phase]}}<RouterLink to="/simulation">查看仿真处置 →</RouterLink></div></template>
