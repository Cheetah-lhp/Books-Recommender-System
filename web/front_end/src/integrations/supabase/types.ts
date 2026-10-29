export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.15"
  }
  public: {
    Tables: {
      authors: {
        Row: {
          bio: string | null
          created_at: string
          id: string
          name: string
        }
        Insert: {
          bio?: string | null
          created_at?: string
          id?: string
          name: string
        }
        Update: {
          bio?: string | null
          created_at?: string
          id?: string
          name?: string
        }
        Relationships: []
      }
      book_categories: {
        Row: {
          book_id: string
          category_id: string
        }
        Insert: {
          book_id: string
          category_id: string
        }
        Update: {
          book_id?: string
          category_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "book_categories_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "book_categories_category_id_fkey"
            columns: ["category_id"]
            isOneToOne: false
            referencedRelation: "categories"
            referencedColumns: ["id"]
          },
        ]
      }
      books: {
        Row: {
          author_id: string | null
          author_name: string
          cover_url: string | null
          created_at: string
          description: string | null
          id: string
          isbn: string | null
          language: string
          pages: number | null
          published_year: number | null
          publisher: string | null
          rating: number
          ratings_count: number
          tags: string[]
          title: string
          trending_rank: number | null
        }
        Insert: {
          author_id?: string | null
          author_name?: string
          cover_url?: string | null
          created_at?: string
          description?: string | null
          id?: string
          isbn?: string | null
          language?: string
          pages?: number | null
          published_year?: number | null
          publisher?: string | null
          rating?: number
          ratings_count?: number
          tags?: string[]
          title: string
          trending_rank?: number | null
        }
        Update: {
          author_id?: string | null
          author_name?: string
          cover_url?: string | null
          created_at?: string
          description?: string | null
          id?: string
          isbn?: string | null
          language?: string
          pages?: number | null
          published_year?: number | null
          publisher?: string | null
          rating?: number
          ratings_count?: number
          tags?: string[]
          title?: string
          trending_rank?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "books_author_id_fkey"
            columns: ["author_id"]
            isOneToOne: false
            referencedRelation: "authors"
            referencedColumns: ["id"]
          },
        ]
      }
      cart_items: {
        Row: {
          book_id: string
          created_at: string
          id: string
          quantity: number
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          id?: string
          quantity?: number
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          id?: string
          quantity?: number
          user_id?: string
        }
        Relationships: []
      }
      categories: {
        Row: {
          icon: string
          id: string
          name: string
          slug: string
          sort_order: number
        }
        Insert: {
          icon?: string
          id?: string
          name: string
          slug: string
          sort_order?: number
        }
        Update: {
          icon?: string
          id?: string
          name?: string
          slug?: string
          sort_order?: number
        }
        Relationships: []
      }
      chat_messages: {
        Row: {
          content: string
          created_at: string
          id: string
          role: string
          user_id: string
        }
        Insert: {
          content: string
          created_at?: string
          id?: string
          role: string
          user_id: string
        }
        Update: {
          content?: string
          created_at?: string
          id?: string
          role?: string
          user_id?: string
        }
        Relationships: []
      }
      community_posts: {
        Row: {
          body: string
          book_id: string | null
          created_at: string
          id: string
          kind: string
          tags: string[]
          user_id: string
        }
        Insert: {
          body: string
          book_id?: string | null
          created_at?: string
          id?: string
          kind?: string
          tags?: string[]
          user_id: string
        }
        Update: {
          body?: string
          book_id?: string | null
          created_at?: string
          id?: string
          kind?: string
          tags?: string[]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "community_posts_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      not_interested_books: {
        Row: {
          book_id: string
          created_at: string
          id: string
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          id?: string
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "not_interested_books_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      notifications: {
        Row: {
          body: string | null
          created_at: string
          id: string
          read: boolean
          title: string
          user_id: string
        }
        Insert: {
          body?: string | null
          created_at?: string
          id?: string
          read?: boolean
          title: string
          user_id: string
        }
        Update: {
          body?: string | null
          created_at?: string
          id?: string
          read?: boolean
          title?: string
          user_id?: string
        }
        Relationships: []
      }
      order_items: {
        Row: {
          book_id: string
          created_at: string
          id: string
          order_id: string
          price_at_purchase: number
          quantity: number
        }
        Insert: {
          book_id: string
          created_at?: string
          id?: string
          order_id: string
          price_at_purchase: number
          quantity: number
        }
        Update: {
          book_id?: string
          created_at?: string
          id?: string
          order_id?: string
          price_at_purchase?: number
          quantity?: number
        }
        Relationships: [
          {
            foreignKeyName: "order_items_order_id_fkey"
            columns: ["order_id"]
            isOneToOne: false
            referencedRelation: "orders"
            referencedColumns: ["id"]
          },
        ]
      }
      orders: {
        Row: {
          created_at: string
          id: string
          shipping_address: string
          status: string
          total_amount: number
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          shipping_address: string
          status?: string
          total_amount?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          shipping_address?: string
          status?: string
          total_amount?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      post_comments: {
        Row: {
          body: string
          created_at: string
          id: string
          post_id: string
          user_id: string
        }
        Insert: {
          body: string
          created_at?: string
          id?: string
          post_id: string
          user_id: string
        }
        Update: {
          body?: string
          created_at?: string
          id?: string
          post_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "post_comments_post_id_fkey"
            columns: ["post_id"]
            isOneToOne: false
            referencedRelation: "community_posts"
            referencedColumns: ["id"]
          },
        ]
      }
      post_likes: {
        Row: {
          created_at: string
          post_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          post_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          post_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "post_likes_post_id_fkey"
            columns: ["post_id"]
            isOneToOne: false
            referencedRelation: "community_posts"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          avatar_url: string | null
          bio: string | null
          created_at: string
          full_name: string
          id: string
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          bio?: string | null
          created_at?: string
          full_name?: string
          id: string
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          bio?: string | null
          created_at?: string
          full_name?: string
          id?: string
          updated_at?: string
        }
        Relationships: []
      }
      reading_history: {
        Row: {
          book_id: string
          created_at: string
          event: string
          id: string
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          event: string
          id?: string
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          event?: string
          id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "reading_history_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      recommendation_feedback: {
        Row: {
          book_id: string
          created_at: string
          feedback: string
          id: string
          reason: string | null
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          feedback: string
          id?: string
          reason?: string | null
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          feedback?: string
          id?: string
          reason?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "recommendation_feedback_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      recommendation_profiles: {
        Row: {
          age_group: string | null
          created_at: string
          favorite_book: string | null
          favorite_books: string[]
          genres: string[]
          location: string | null
          onboarding_completed: boolean
          preferred_book_length: string | null
          preferred_language: string | null
          reading_frequency: string | null
          reading_mood: string | null
          themes: string[]
          updated_at: string
          user_id: string
        }
        Insert: {
          age_group?: string | null
          created_at?: string
          favorite_book?: string | null
          favorite_books?: string[]
          genres?: string[]
          location?: string | null
          onboarding_completed?: boolean
          preferred_book_length?: string | null
          preferred_language?: string | null
          reading_frequency?: string | null
          reading_mood?: string | null
          themes?: string[]
          updated_at?: string
          user_id: string
        }
        Update: {
          age_group?: string | null
          created_at?: string
          favorite_book?: string | null
          favorite_books?: string[]
          genres?: string[]
          location?: string | null
          onboarding_completed?: boolean
          preferred_book_length?: string | null
          preferred_language?: string | null
          reading_frequency?: string | null
          reading_mood?: string | null
          themes?: string[]
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      review_sentiment: {
        Row: {
          created_at: string
          label: string
          model: string | null
          review_id: string
          score: number
        }
        Insert: {
          created_at?: string
          label: string
          model?: string | null
          review_id: string
          score?: number
        }
        Update: {
          created_at?: string
          label?: string
          model?: string | null
          review_id?: string
          score?: number
        }
        Relationships: [
          {
            foreignKeyName: "review_sentiment_review_id_fkey"
            columns: ["review_id"]
            isOneToOne: true
            referencedRelation: "reviews"
            referencedColumns: ["id"]
          },
        ]
      }
      reviews: {
        Row: {
          body: string | null
          book_id: string
          created_at: string
          id: string
          rating: number
          user_id: string
        }
        Insert: {
          body?: string | null
          book_id: string
          created_at?: string
          id?: string
          rating: number
          user_id: string
        }
        Update: {
          body?: string | null
          book_id?: string
          created_at?: string
          id?: string
          rating?: number
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "reviews_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      user_books: {
        Row: {
          book_id: string
          created_at: string
          id: string
          progress: number
          status: string
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          id?: string
          progress?: number
          status?: string
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          id?: string
          progress?: number
          status?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_books_book_id_fkey"
            columns: ["book_id"]
            isOneToOne: false
            referencedRelation: "books"
            referencedColumns: ["id"]
          },
        ]
      }
      user_preferences: {
        Row: {
          email_updates: boolean
          favorite_genres: string[]
          language: string
          push_notifications: boolean
          theme: string
          updated_at: string
          user_id: string
        }
        Insert: {
          email_updates?: boolean
          favorite_genres?: string[]
          language?: string
          push_notifications?: boolean
          theme?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          email_updates?: boolean
          favorite_genres?: string[]
          language?: string
          push_notifications?: boolean
          theme?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      wishlist_items: {
        Row: {
          book_id: string
          created_at: string
          id: string
          user_id: string
        }
        Insert: {
          book_id: string
          created_at?: string
          id?: string
          user_id: string
        }
        Update: {
          book_id?: string
          created_at?: string
          id?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "admin" | "moderator" | "user"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "moderator", "user"],
    },
  },
} as const
