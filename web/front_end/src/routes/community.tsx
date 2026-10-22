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
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { postsQuery } from "@/lib/data";
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
      const { error } = await supabase.from("community_posts").insert({ user_id: user.id, body, kind: tab });
      if (error) throw error;
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
      if (liked) {
        await supabase.from("post_likes").delete().eq("post_id", postId).eq("user_id", user.id);
      } else {
        await supabase.from("post_likes").insert({ post_id: postId, user_id: user.id });
      }
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
            {t(`community.${key}`)}
          </button>
        ))}
      </div>

      <div className="surface-card mb-6 p-4">
        <div className="flex gap-3">
          <Avatar className="h-9 w-9 shrink-0">
            <AvatarImage src={profile?.avatar_url ?? undefined} alt="" />
            <AvatarFallback>{(profile?.full_name ?? "R").charAt(0)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("community.placeholder")}
              className="min-h-16"
            />
            <div className="mt-2 flex justify-end">
              <Button
                className="rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={!body.trim()}
                onClick={() => create.mutate()}
              >
                {t("community.post")}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {visible.map((post) => {
          const liked = Boolean(user && post.post_likes.some((l) => l.user_id === user.id));
          return (
            <article key={post.id} className="surface-card p-4">
              <div className="flex items-center gap-3">
                <Avatar className="h-9 w-9">
                  <AvatarImage src={post.profiles?.avatar_url ?? undefined} alt="" />
                  <AvatarFallback>{(post.profiles?.full_name ?? "R").charAt(0)}</AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-foreground">{post.profiles?.full_name ?? "Reader"}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(post.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-sm text-foreground">{post.body}</p>
              {post.tags?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {post.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground">
                      #{tag}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                <button
                  className={cn("inline-flex items-center gap-1", liked && "text-gold")}
                  onClick={() => like.mutate({ postId: post.id, liked })}
                >
                  <Heart className={cn("h-4 w-4", liked && "fill-gold")} />
                  {post.post_likes.length}
                </button>
                <span className="inline-flex items-center gap-1">
                  <MessageCircle className="h-4 w-4" />
                  {post.post_comments.length}
                </span>
              </div>
            </article>
          );
        })}
        {visible.length === 0 ? <p className="text-sm text-muted-foreground">{t("profile.empty")}</p> : null}
      </div>
    </AppShell>
  );
}
