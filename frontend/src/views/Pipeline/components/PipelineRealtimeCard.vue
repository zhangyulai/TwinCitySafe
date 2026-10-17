<script setup lang="ts">
import type {PipelineState} from '../../../types/realtime';import {statusLabels} from '../../../types/pipeline';defineProps<{state?:PipelineState}>();
</script><template><div class="pipe-live"><div>实时压力<strong data-testid="pipe-pressure">{{state?.pressure.toFixed(3)??'—'}} <small>MPa</small></strong></div><div>实时流量<strong data-testid="pipe-flow">{{state?.flow.toFixed(2)??'—'}} <small>m³/h</small></strong></div><p data-testid="pipe-status">{{state?statusLabels[state.status]:'等待实时连接'}} · 软件仿真</p></div></template>
