/**
 * Shared presentation context for the competition deployment.
 *
 * Shared presentation vocabulary. Operational assets remain software
 * simulation assets rather than surveyed building or utility ownership.
 */
export const parkContext = {
  name: '智慧园区',
  scope: '数字孪生工作空间',
  workspace: '园区安全工作台',
  simulationNotice: '园区运维与安全协同平台',
  floodZone: 'B2 地下停车场',
} as const;

const buildingLabels: Record<string, string> = {
  'A-OFFICE': '办公楼 A',
  'B-RESEARCH': '科研楼 B',
  'C-LAB': '实验楼 C',
  'D-SERVICE': '综合服务楼',
  'B2-PARKING': parkContext.floodZone,
};

export function parkBuildingName(id?: string | null, fallback = '园区建筑'): string {
  return id ? buildingLabels[id] ?? fallback : fallback;
}

export function parkAssetArea(area?: string | null): string {
  return area ?? '园区仿真区域';
}
