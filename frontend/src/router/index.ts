import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "catalog",
      component: () => import("@/views/CatalogView.vue"),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { guestOnly: true },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/views/RegisterView.vue"),
      meta: { guestOnly: true },
    },
    {
      path: "/verify-email",
      name: "verify-email",
      component: () => import("@/views/VerifyEmailView.vue"),
    },
    {
      path: "/forgot-password",
      name: "forgot-password",
      component: () => import("@/views/ForgotPasswordView.vue"),
      meta: { guestOnly: true },
    },
    {
      path: "/reset-password",
      name: "reset-password",
      component: () => import("@/views/ResetPasswordView.vue"),
      meta: { guestOnly: true },
    },
    {
      // Возврат из VK/Яндекса. Без meta: сюда попадают и гость (вход/регистрация), и
      // залогиненный пользователь (привязка провайдера из настроек).
      path: "/oauth/:provider/callback",
      name: "oauth-callback",
      component: () => import("@/views/OAuthCallbackView.vue"),
    },
    {
      path: "/cabinet",
      name: "cabinet",
      component: () => import("@/views/CabinetView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/admin",
      name: "admin",
      component: () => import("@/views/AdminView.vue"),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: "/students/:id",
      name: "student-profile",
      component: () => import("@/views/StudentProfileView.vue"),
      meta: { requiresAuth: true, requiresTutor: true },
    },
    {
      path: "/tutors/:id",
      name: "tutor-profile",
      component: () => import("@/views/TutorProfileView.vue"),
    },
    {
      path: "/tutors/:id/book",
      name: "tutor-booking",
      component: () => import("@/views/TutorBookingView.vue"),
    },
    {
      path: "/tutors/:id/groups",
      name: "tutor-group-booking",
      component: () => import("@/views/TutorGroupBookingView.vue"),
    },
    {
      path: "/blog",
      name: "blog",
      component: () => import("@/views/BlogListView.vue"),
    },
    {
      path: "/blog/:slug",
      name: "blog-post",
      component: () => import("@/views/BlogPostView.vue"),
    },
    {
      path: "/legal/privacy",
      name: "privacy-policy",
      component: () => import("@/views/PrivacyPolicyView.vue"),
    },
    {
      path: "/legal/agreement",
      name: "user-agreement",
      component: () => import("@/views/UserAgreementView.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.isInitialized) {
    await auth.init();
  }
  const isAdmin = auth.user?.role === "admin";

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: isAdmin ? "admin" : "cabinet" };
  }
  if (to.meta.requiresAdmin && !isAdmin) {
    return { name: "cabinet" };
  }
  if (to.meta.requiresTutor && auth.user?.role !== "tutor") {
    return { name: "cabinet" };
  }
  // Admin has no ordinary tutor/student cabinet - keep it out of their way.
  if (to.name === "cabinet" && isAdmin) {
    return { name: "admin" };
  }
  return true;
});

export default router;
