import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { normalizeGenres } from "@/lib/categories";
import {
  AGE_GROUPS,
  EMPTY_ANSWERS,
  FREQUENCIES,
  GENRES,
  LANGUAGES,
  LENGTHS,
  MOODS,
  loadStoredAnswers,
  storeAnswers,
  type Answers,
} from "@/lib/questionnaire";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/recommend")({
  head: () => ({
    meta: [
      { title: "Personalized Recommendation Questionnaire — READORA" },
      {
        name: "description",
        content: "Answer eight quick questions about your taste and READORA will pick books made for you.",
      },
      { property: "og:title", content: "Personalized Recommendation Questionnaire — READORA" },
      { property: "og:description", content: "Tell READORA your reading taste and get personalized book picks." },
    ],
  }),
  component: RecommendPage,
});

function QuestionCard({
  index,
  title,
  subtitle,
  optional,
  error,
  children,
}: {
  index: number;
  title: string;
  subtitle?: string;
  optional?: boolean;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-gold/40 bg-card/80 p-5 shadow-card backdrop-blur sm:p-7">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-display text-sm font-bold text-gold">{String(index).padStart(2, "0")}</span>
        <h2 className="font-display text-lg font-bold text-foreground sm:text-xl">{title}</h2>
        {optional ? (
          <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
            Optional
          </span>
        ) : null}
        {subtitle ? <p className="w-full text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {children}
      {error ? <p className="mt-3 text-sm font-medium text-destructive">{error}</p> : null}
    </section>
  );
}

function OptionButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "rounded-full border px-4 py-2.5 text-sm font-medium transition-colors",
        selected
          ? "border-[var(--readora-selection-bg)] bg-choice text-choice-foreground"
          : "border-border bg-background text-foreground hover:border-gold hover:text-gold",
      )}
    >
      {label}
    </button>
  );
}

function RecommendPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [answers, setAnswers] = useState<Answers>(EMPTY_ANSWERS);
  const [errors, setErrors] = useState<Partial<Record<keyof Answers, string>>>({});
  const [submitting, setSubmitting] = useState(false);

  // New users start fully unselected. Saved preferences (DB first, local draft as
  // fallback for signed-out users) are loaded only when they actually exist.
  useEffect(() => {
    let active = true;
    const load = async () => {
      if (user) {
        const { data } = await supabase
          .from("recommendation_profiles")
          .select("*")
          .eq("user_id", user.id)
          .maybeSingle();
        if (!active) return;
        if (data) {
          const saved: Answers = {
            ageGroup: data.age_group ?? "",
            genres: normalizeGenres(data.genres ?? []),
            readingMood: data.reading_mood ?? "",
            favoriteBook: data.favorite_book ?? "",
            location: data.location ?? "",
            preferredLanguage: data.preferred_language ?? "",
            readingFrequency: data.reading_frequency ?? "",
            preferredBookLength: data.preferred_book_length ?? "",
          };
          setAnswers(saved);
          storeAnswers(saved);
        } else {
          setAnswers(EMPTY_ANSWERS);
        }
        return;
      }
      const stored = loadStoredAnswers();
      if (active && stored) setAnswers(stored);
    };
    void load();
    return () => {
      active = false;
    };
  }, [user]);

  const set = <K extends keyof Answers>(key: K, value: Answers[K]) => {
    setErrors((prev) => ({ ...prev, [key]: undefined }));
    setAnswers((prev) => {
      const next = { ...prev, [key]: value };
      storeAnswers(next);
      return next;
    });
  };

  const toggleGenre = (g: string) =>
    set("genres", answers.genres.includes(g) ? answers.genres.filter((x) => x !== g) : [...answers.genres, g]);


  const submit = async () => {
    const nextErrors: Partial<Record<keyof Answers, string>> = {};
    if (!answers.ageGroup) nextErrors.ageGroup = "Please select your age group.";
    if (!answers.genres.length) nextErrors.genres = "Please choose at least one genre.";
    if (!answers.readingMood) nextErrors.readingMood = "Please select your reading mood.";
    if (!answers.preferredLanguage) nextErrors.preferredLanguage = "Please select a preferred language.";
    if (!answers.readingFrequency) nextErrors.readingFrequency = "Please select your reading frequency.";
    if (!answers.preferredBookLength) nextErrors.preferredBookLength = "Please select a preferred book length.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      toast.error("Please answer the highlighted questions.");
      return;
    }


    setSubmitting(true);
    storeAnswers(answers);
    if (user) {
      const { error } = await supabase.from("recommendation_profiles").upsert(
        {
          user_id: user.id,
          age_group: answers.ageGroup,
          genres: answers.genres,
          reading_mood: answers.readingMood,
          favorite_book: answers.favoriteBook || null,
          location: answers.location || null,
          preferred_language: answers.preferredLanguage,
          reading_frequency: answers.readingFrequency,
          preferred_book_length: answers.preferredBookLength,
          onboarding_completed: true,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "user_id" },
      );
      if (error) toast.error("Could not save your answers, showing results anyway.");
    }
    setSubmitting(false);
    void navigate({ to: "/" });
  };

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-3xl">
        <header className="mb-6 text-center">
          <h1 className="font-display text-2xl font-extrabold text-foreground sm:text-4xl">
            Personalized Recommendation
          </h1>
          <p className="mt-2 text-sm text-muted-foreground sm:text-base">
            Answer a few questions and READORA will pick your next great book.
          </p>
        </header>

        <div className="space-y-5">
          <QuestionCard index={1} title="Age group" error={errors.ageGroup}>
            <div className="flex flex-wrap gap-2.5">
              {AGE_GROUPS.map((o) => (
                <OptionButton key={o} label={o} selected={answers.ageGroup === o} onClick={() => set("ageGroup", o)} />
              ))}
            </div>
          </QuestionCard>

          <QuestionCard index={2} title="Genres you enjoy" subtitle="Pick as many as you like" error={errors.genres}>
            <div className="flex flex-wrap gap-2.5">
              {GENRES.map((o) => (
                <OptionButton key={o} label={o} selected={answers.genres.includes(o)} onClick={() => toggleGenre(o)} />
              ))}
            </div>
          </QuestionCard>

          <QuestionCard index={3} title="What's your reading mood?" error={errors.readingMood}>
            <div className="flex flex-wrap gap-2.5">
              {MOODS.map((o) => (
                <OptionButton
                  key={o}
                  label={o}
                  selected={answers.readingMood === o}
                  onClick={() => set("readingMood", o)}
                />
              ))}
            </div>
          </QuestionCard>

          <QuestionCard index={4} title="A book you loved" optional>
            <input
              value={answers.favoriteBook}
              onChange={(e) => set("favoriteBook", e.target.value)}
              placeholder="e.g. Atomic Habits"
              className="h-11 w-full rounded-full border border-border bg-background px-4 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-gold"
            />
          </QuestionCard>

          <QuestionCard index={5} title="Your location" optional>
            <input
              value={answers.location}
              onChange={(e) => set("location", e.target.value)}
              placeholder="e.g. Cairo"
              className="h-11 w-full rounded-full border border-border bg-background px-4 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-gold"
            />
          </QuestionCard>

          <QuestionCard index={6} title="Preferred language" error={errors.preferredLanguage}>
            <div className="flex flex-wrap gap-2.5">
              {LANGUAGES.map((o) => (
                <OptionButton
                  key={o}
                  label={o}
                  selected={answers.preferredLanguage === o}
                  onClick={() => set("preferredLanguage", o)}
                />
              ))}
            </div>
          </QuestionCard>

          <QuestionCard index={7} title="Reading frequency" error={errors.readingFrequency}>
            <div className="flex flex-wrap gap-2.5">
              {FREQUENCIES.map((o) => (
                <OptionButton
                  key={o}
                  label={o}
                  selected={answers.readingFrequency === o}
                  onClick={() => set("readingFrequency", o)}
                />
              ))}
            </div>
          </QuestionCard>

          <QuestionCard index={8} title="Preferred book length" error={errors.preferredBookLength}>
            <div className="flex flex-wrap gap-2.5">
              {LENGTHS.map((o) => (
                <OptionButton
                  key={o}
                  label={o}
                  selected={answers.preferredBookLength === o}
                  onClick={() => set("preferredBookLength", o)}
                />
              ))}
            </div>
          </QuestionCard>

          <Button
            onClick={() => void submit()}
            disabled={submitting}
            className="h-14 w-full rounded-full bg-gold text-base font-bold text-gold-foreground hover:bg-gold/90"
          >
            {submitting ? "Preparing..." : "Get My Recommendations"}
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
