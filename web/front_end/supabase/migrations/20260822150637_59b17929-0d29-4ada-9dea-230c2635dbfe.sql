ALTER TABLE public.recommendation_profiles
  ADD COLUMN IF NOT EXISTS themes text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS favorite_books uuid[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS onboarding_completed boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS public.recommendation_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  book_id uuid NOT NULL REFERENCES public.books(id) ON DELETE CASCADE,
  feedback text NOT NULL CHECK (feedback IN ('good','not_for_me')),
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, book_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.recommendation_feedback TO authenticated;
GRANT ALL ON public.recommendation_feedback TO service_role;
ALTER TABLE public.recommendation_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own recommendation feedback" ON public.recommendation_feedback
  FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.not_interested_books (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  book_id uuid NOT NULL REFERENCES public.books(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, book_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.not_interested_books TO authenticated;
GRANT ALL ON public.not_interested_books TO service_role;
ALTER TABLE public.not_interested_books ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own hidden books" ON public.not_interested_books
  FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.reading_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  book_id uuid NOT NULL REFERENCES public.books(id) ON DELETE CASCADE,
  event text NOT NULL CHECK (event IN ('viewed','started','finished','shelved')),
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.reading_history TO authenticated;
GRANT ALL ON public.reading_history TO service_role;
ALTER TABLE public.reading_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own reading history" ON public.reading_history
  FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users insert own reading history" ON public.reading_history
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.review_sentiment (
  review_id uuid PRIMARY KEY REFERENCES public.reviews(id) ON DELETE CASCADE,
  label text NOT NULL CHECK (label IN ('positive','neutral','negative')),
  score numeric NOT NULL DEFAULT 0,
  model text,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.review_sentiment TO authenticated, anon;
GRANT ALL ON public.review_sentiment TO service_role;
ALTER TABLE public.review_sentiment ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone can read review sentiment" ON public.review_sentiment
  FOR SELECT TO authenticated, anon USING (true);