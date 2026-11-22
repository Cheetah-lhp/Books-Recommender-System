import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/wishlist")({
  beforeLoad: () => {
    throw redirect({ to: "/discover" });
  },
});
