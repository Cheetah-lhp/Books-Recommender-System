import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Heart, MessageCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { SectionHeader } from "@/components/readora/BookCard";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth";
import { postsQuery } from "@/lib/data";
import { loadLocalPosts, saveLocalPosts } from "@/features/community/queries";
import type { CommunityPost } from "@/features/community/types";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/community")({
  head: () => ({
    meta: [
      { title: "Reader Community — READORA" },
      { name: "description", content: "Join discussions, reading groups and events with fellow READORA readers." },
      { property: "og:title", content: "Reader Community — READORA" },
      { property: "og:description", content: "Discussions, reading groups and events for readers." },
    ],
  }),
  component: CommunityPage,
});

const TABS = ["discussions", "groups", "events"] as const;

function CommunityPage() {
  const { t } = useI18n();
  const { user, profile } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<(typeof TABS)[number]>("discussions");
  const [body, setBody] = useState("");
  const { data: posts = [] } = useQuery(postsQuery);

  const create = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("auth");
      const next: CommunityPost = {
        id: `post-${Date.now()}`,
        body,
        tags: [],
        kind: tab,
        created_at: new Date().toISOString(),
        user_id: user.id,
        book_id: null,
        profiles: { full_name: profile?.full_name || user.email, avatar_url: profile?.avatar_url ?? null },
        books: null,
        post_likes: [],
        post_comments: [],
      };
      saveLocalPosts([next, ...loadLocalPosts()]);
    },
    onSuccess: () => {
      setBody("");
      void qc.invalidateQueries({ queryKey: ["community", "posts"] });
    },
    onError: () => toast.error(user ? "Could not post" : t("auth.signedOut")),
  });

  const like = useMutation({
    mutationFn: async ({ postId, liked }: { postId: string; liked: boolean }) => {
      if (!user) throw new Error("auth");
      const all = loadLocalPosts();
      const post = all.find((p) => p.id === postId);
      if (!post) return;
      if (liked) post.post_likes = post.post_likes.filter((l) => l.user_id !== user.id);
      else post.post_likes = [...post.post_likes, { user_id: user.id }];
      saveLocalPosts(all);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["community", "posts"] }),
    onError: () => toast.error(t("auth.signedOut")),
  });

  const visible = posts.filter((p) => p.kind === tab);

  return (
    <AppShell>
      <SectionHeader title={t("community.title")} subtitle={t("community.sub")} />

      <div className="mb-5 inline-flex rounded-full bg-secondary p-1">
        {TABS.map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-semibold transition-colors",
              tab === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {key}
          </button>
        ))}
      </div>

      <div className="mb-6 space-y-3">
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Share with readers…" />
        <Button disabled={!body.trim() || create.isPending} onClick={() => create.mutate()}>
          Post
        </Button>
      </div>

      <div className="space-y-4">
        {visible.map((p) => {
          const liked = Boolean(user && p.post_likes.some((l) => l.user_id === user.id));
          return (
            <article key={p.id} className="surface-card p-4">
              <div className="mb-2 flex items-center gap-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={p.profiles?.avatar_url ?? undefined} />
                  <AvatarFallback>{(p.profiles?.full_name ?? "?")[0]}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-sm font-semibold">{p.profiles?.full_name ?? "Reader"}</p>
                  <p className="text-xs text-muted-foreground">{new Date(p.created_at).toLocaleString()}</p>
                </div>
              </div>
              <p className="text-sm text-foreground">{p.body}</p>
              <div className="mt-3 flex gap-3">
                <button
                  className="inline-flex items-center gap-1 text-sm text-muted-foreground"
                  onClick={() => like.mutate({ postId: p.id, liked })}
                >
                  <Heart className={cn("h-4 w-4", liked && "fill-current text-red-500")} />
                  {p.post_likes.length}
                </button>
                <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                  <MessageCircle className="h-4 w-4" />
                  {p.post_comments.length}
                </span>
              </div>
            </article>
          );
        })}
        {!visible.length && <p className="text-sm text-muted-foreground">No posts yet.</p>}
      </div>
    </AppShell>
  );
}
