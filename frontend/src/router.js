import { createRouter, createWebHistory } from "vue-router";
import cctvlist from "./views/cctvlist.vue";
import cctvdetail from "./views/cctvdetail.vue";

const routes = [
  { path: "/", name: "cctvlist", component: cctvlist },
  { path: "/cctv/:id", name: "cctvdetail", component: cctvdetail, props: true },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
