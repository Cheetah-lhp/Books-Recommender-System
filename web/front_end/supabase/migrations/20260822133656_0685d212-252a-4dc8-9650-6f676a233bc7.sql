CREATE TABLE IF NOT EXISTS public.recommendation_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  age_group TEXT,
  genres TEXT[] NOT NULL DEFAULT '{}',
  reading_mood TEXT,
  favorite_book TEXT,
  location TEXT,
  preferred_language TEXT,
  reading_frequency TEXT,
  preferred_book_length TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.recommendation_profiles TO authenticated;
GRANT ALL ON public.recommendation_profiles TO service_role;

ALTER TABLE public.recommendation_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own recommendation profile"
ON public.recommendation_profiles FOR ALL TO authenticated
USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);