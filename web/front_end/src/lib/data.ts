/**
 * BRS Data Layer — Re-export bridge
 * Toan bo logic da duoc phan theo feature trong src/features/ va src/shared/.
 * File nay re-export de giu tuong thich nguoc.
 */

export * from "@/shared/api/client";
export * from "@/features/books/types";
export * from "@/features/books/api";
export * from "@/features/books/queries";
export * from "@/features/catalog/queries";
export * from "@/features/reviews/types";
export * from "@/features/reviews/queries";
export * from "@/features/community/types";
export * from "@/features/community/queries";
export * from "@/features/user/types";
export * from "@/features/user/queries";
