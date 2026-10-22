import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { Chatbot } from "@/components/readora/Chatbot";
import { SectionHeader } from "@/components/readora/BookCard";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/chat")({
  head: () => ({
    meta: [
      { title: "Chat with AI — READORA" },
      { name: "description", content: "Your personal AI reading assistant recommends books for any mood." },
      { property: "og:title", content: "Chat with AI — READORA" },
      { property: "og:description", content: "Your personal AI reading assistant." },
    ],
  }),
  component: ChatPage,
});

function ChatPage() {
  const { t } = useI18n();
  return (
    <AppShell>
      <SectionHeader title={t("chat.title")} subtitle={t("chat.intro")} />
      <div className="mx-auto max-w-2xl">
        <Chatbot variant="inline" />
      </div>
    </AppShell>
  );
}
