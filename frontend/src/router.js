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
  scrollBehavior(to, from, savedPosition) {
    // Use browser's saved position when using back/forward
    if (savedPosition) return savedPosition;

    // If returning from detail to list with a scroll offset in query, restore it
    if (to.name === 'cctvlist' && from?.name === 'cctvdetail' && typeof to.query?.y === 'string') {
      const top = Number(to.query.y) || 0;
      return { left: 0, top, behavior: 'auto' };
    }

    // If navigating to list with query parameters (search/filter), keep scroll position
    if (to.name === 'cctvlist' && to.query && (to.query.q || to.query.cat)) {
      // If there's a scroll position in query, use it
      if (typeof to.query.y === 'string') {
        const top = Number(to.query.y) || 0;
        return { left: 0, top, behavior: 'auto' };
      }
      // Otherwise, don't scroll (keep current position)
      return false;
    }

    // Navigations within the list (e.g., changing filters via query) should keep position
    if (to.name === 'cctvlist' && from?.name === 'cctvlist') {
      return false; // keep current scroll
    }

    // Default scroll to top for normal navigations
    return { left: 0, top: 0 };
  },
});

export default router;
