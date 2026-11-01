import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

export const getDemoOptions = createServerFn({ method: "GET" }).handler(async () => {
  const { demoOptions } = await import("./demo.server");
  return demoOptions();
});

export const runDemo = createServerFn({ method: "POST" })
  .validator((data: unknown) =>
    z
      .object({
        scenario: z.enum(["genre", "favorite", "history"]),
        genre: z.string().max(100).default("Fantasy & Paranormal"),
        bookId: z.string().max(100).optional(),
      })
      .parse(data),
  )
  .handler(async ({ data }) => {
    const { demoRecommendations } = await import("./demo.server");
    return demoRecommendations(data);
  });
