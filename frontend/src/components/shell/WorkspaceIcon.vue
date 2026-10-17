<script setup lang="ts">
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  gis: 'M4 5l5-2 6 2 5-2v15l-5 2-6-2-5 2z M9 3v15 M15 5v15',
  operation: 'M9 3h6l1 4 4 1v8l-4 1-1 4H9l-1-4-4-1V8l4-1z M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
  pipeline: 'M4 3v6h7v6h9v6 M11 9V3 M4 15v6 M2 9h4 M9 3h4 M18 21h4 M2 15h4',
  risk: 'M3 19h18 M5 15l4-5 4 3 6-9 M15 4h4v4',
  simulation: 'M12 3l9 4v6c0 4-5 7-9 9-4-2-9-5-9-9V7z M8 12l3 3 5-6',
  review: 'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',
};
</script>
<template><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.dashboard"/></svg></template>
