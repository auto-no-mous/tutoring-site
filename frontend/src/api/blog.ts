import { apiClient } from "@/api/client";
import type { BlogPost, BlogPostPage } from "@/types/blog";

export async function listBlogPosts(params: { page?: number; page_size?: number } = {}) {
  const { data } = await apiClient.get<BlogPostPage>("/blog", { params });
  return data;
}

export async function getBlogPost(slug: string) {
  const { data } = await apiClient.get<BlogPost>(`/blog/${slug}`);
  return data;
}
