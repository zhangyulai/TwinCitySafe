import { createRouter, createWebHistory } from "vue-router";
export const navigation = [
  { path: "/dashboard", label: "综合态势" },
  { path: "/operation", label: "智慧运维" },
  { path: "/pipeline", label: "地下管网" },
  { path: "/risk", label: "风险研判" },
  { path: "/simulation", label: "应急推演" },
  { path: "/review", label: "事件复盘" },
];
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    {
      path: "/dashboard",
      component: () => import("../views/Dashboard/index.vue"),
    },
    {
      path: "/operation",
      component: () => import("../views/Operation/index.vue"),
    },
    {
      path: "/pipeline",
      component: () => import("../views/Pipeline/index.vue"),
    },
    { path: "/risk", component: () => import("../views/Risk/index.vue") },
    {
      path: "/simulation",
      component: () => import("../views/Simulation/index.vue"),
    },
    { path: "/review", component: () => import("../views/Review/index.vue") },
    { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
  ],
});
