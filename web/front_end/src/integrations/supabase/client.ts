// Supabase client — standalone, không phụ thuộc Lovable
import { createClient } from '@supabase/supabase-js';
import type { Database } from './types';

function createSupabaseClient() {
  const envObj = (import.meta as unknown as { env: Record<string, string> }).env;
  const SUPABASE_URL =
    envObj?.['VITE_SUPABASE_URL'] ||
    (typeof process !== 'undefined' ? process.env['SUPABASE_URL'] : undefined) ||
    'https://oxftbkdevxewkvzsunuo.supabase.co';
  const SUPABASE_ANON_KEY =
    envObj?.['VITE_SUPABASE_ANON_KEY'] ||
    envObj?.['VITE_SUPABASE_PUBLISHABLE_KEY'] ||
    (typeof process !== 'undefined'
      ? process.env['SUPABASE_ANON_KEY'] || process.env['SUPABASE_PUBLISHABLE_KEY']
      : undefined) ||
    'sb_publishable_TegSFZQvUkzULU8rFda1Kw_tIWMDhKO';

  return createClient<Database>(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      storage: typeof window !== 'undefined' ? localStorage : undefined,
      persistSession: typeof window !== 'undefined',
      autoRefreshToken: typeof window !== 'undefined',
    },
  });
}

let _supabase: ReturnType<typeof createSupabaseClient> | undefined;

// Import: import { supabase } from "@/integrations/supabase/client";
export const supabase = new Proxy({} as ReturnType<typeof createSupabaseClient>, {
  get(_, prop, receiver) {
    if (!_supabase) _supabase = createSupabaseClient();
    return Reflect.get(_supabase, prop, receiver);
  },
});
