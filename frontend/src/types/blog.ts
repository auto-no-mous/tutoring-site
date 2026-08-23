export interface BlogPostListItem {
  id: string;
  slug: string;
  title: string;
  summary: string;
  cover_image_url: string | null;
  published_at: string | null;
}

export interface BlogPost extends BlogPostListItem {
  body: string;
  author_name: string | null;
}

// Черновики и служебные поля видит только админка - публичные схемы их не отдают.
export interface BlogPostAdmin extends BlogPost {
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface BlogPostPage {
  items: BlogPostListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface BlogPostPayload {
  title: string;
  body: string;
  summary: string;
  cover_image_url: string | null;
  slug: string | null;
  is_published: boolean;
}
