import { authFetch } from "@/lib/auth-api";
import { type Book } from "@/lib/data";

export type CartItem = {
  id: string;
  book_id: string;
  quantity: number;
  book?: Book | undefined;
};

export type WishlistItem = {
  id: string;
  book_id: string;
  created_at: string;
  book?: Book | undefined;
};

export type OrderItem = {
  id: string;
  order_id: string;
  book_id: string;
  quantity: number;
  price_at_purchase: number;
  book?: Book | undefined;
};

export type Order = {
  id: string;
  user_id: string;
  status: "pending" | "processing" | "shipped" | "delivered" | "cancelled";
  total_amount: number;
  shipping_address: string;
  created_at: string;
  updated_at: string;
  items?: OrderItem[] | undefined;
};

const LOCAL_CART_KEY = "brs_local_cart";
const LOCAL_WISHLIST_KEY = "brs_local_wishlist";
const LOCAL_ORDERS_KEY = "brs_local_orders";

function cartKey(userId: string | null) {
  return userId ? `${LOCAL_CART_KEY}:${userId}` : LOCAL_CART_KEY;
}
function ordersKey(userId: string) {
  return `${LOCAL_ORDERS_KEY}:${userId}`;
}

export async function fetchBooksBatch(bookIds: (string | number)[]): Promise<Record<string, Book>> {
  const numericIds = bookIds.map((id) => Number(id)).filter((n) => !isNaN(n) && n > 0);
  if (numericIds.length === 0) return {};
  try {
    const res = await fetch("/api/books/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: numericIds }),
    });
    if (!res.ok) return {};
    const books: Book[] = await res.json();
    const map: Record<string, Book> = {};
    for (const b of books) {
      const price = b.price && b.price > 0 ? b.price : Number((((Number(b.id) * 37) % 30) + 9.99).toFixed(2));
      map[String(b.id)] = { ...b, id: String(b.id), price };
    }
    return map;
  } catch {
    return {};
  }
}

export function getLocalCart(userId: string | null = null): CartItem[] {
  try {
    const data = localStorage.getItem(cartKey(userId));
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveLocalCart(items: CartItem[], userId: string | null = null) {
  try {
    localStorage.setItem(cartKey(userId), JSON.stringify(items));
    window.dispatchEvent(new Event("cart_updated"));
  } catch {
    /* ignore */
  }
}

export async function fetchUserCart(userId: string | null): Promise<CartItem[]> {
  const rawItems = getLocalCart(userId);
  if (rawItems.length === 0) return [];
  const booksMap = await fetchBooksBatch(rawItems.map((i) => i.book_id));
  return rawItems.map((item) => ({ ...item, book: booksMap[String(item.book_id)] }));
}

export async function addToCart(userId: string | null, bookId: string, quantity = 1): Promise<void> {
  const items = getLocalCart(userId);
  const idx = items.findIndex((i) => String(i.book_id) === String(bookId));
  if (idx >= 0 && items[idx]) items[idx]!.quantity += quantity;
  else items.push({ id: `local-${Date.now()}-${Math.random()}`, book_id: bookId, quantity });
  saveLocalCart(items, userId);
}

export async function updateCartQuantity(
  userId: string | null,
  cartItemId: string,
  bookId: string,
  quantity: number,
): Promise<void> {
  if (quantity <= 0) return removeFromCart(userId, cartItemId, bookId);
  const items = getLocalCart(userId);
  const item = items.find((i) => i.id === cartItemId || String(i.book_id) === String(bookId));
  if (item) {
    item.quantity = quantity;
    saveLocalCart(items, userId);
  }
}

export async function removeFromCart(userId: string | null, cartItemId: string, bookId: string): Promise<void> {
  saveLocalCart(
    getLocalCart(userId).filter((i) => i.id !== cartItemId && String(i.book_id) !== String(bookId)),
    userId,
  );
}

export async function clearCart(userId: string | null): Promise<void> {
  saveLocalCart([], userId);
}

export function getLocalWishlist(): string[] {
  try {
    const data = localStorage.getItem(LOCAL_WISHLIST_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveLocalWishlist(bookIds: string[]) {
  try {
    localStorage.setItem(LOCAL_WISHLIST_KEY, JSON.stringify(bookIds));
    window.dispatchEvent(new Event("wishlist_updated"));
  } catch {
    /* ignore */
  }
}

export async function fetchUserWishlist(userId: string | null): Promise<WishlistItem[]> {
  let rawItems: { id: string; book_id: string; created_at: string }[] = [];
  if (userId) {
    const res = await authFetch("/api/wishlist");
    if (res.ok) {
      const rows = (await res.json()) as { id: number; book_id: string }[];
      rawItems = rows.map((r) => ({
        id: String(r.id),
        book_id: String(r.book_id),
        created_at: new Date().toISOString(),
      }));
    }
  } else {
    rawItems = getLocalWishlist().map((id) => ({
      id: `local-w-${id}`,
      book_id: id,
      created_at: new Date().toISOString(),
    }));
  }
  if (!rawItems.length) return [];
  const booksMap = await fetchBooksBatch(rawItems.map((i) => i.book_id));
  return rawItems.map((item) => ({ ...item, book: booksMap[String(item.book_id)] }));
}

export async function toggleWishlist(userId: string | null, bookId: string): Promise<boolean> {
  if (userId) {
    const current = await fetchUserWishlist(userId);
    const exists = current.find((i) => String(i.book_id) === String(bookId));
    if (exists) {
      await authFetch(`/api/wishlist/${encodeURIComponent(bookId)}`, { method: "DELETE" });
      return false;
    }
    await authFetch("/api/wishlist", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ book_id: bookId }),
    });
    return true;
  }
  const ids = getLocalWishlist();
  const strId = String(bookId);
  const idx = ids.indexOf(strId);
  if (idx >= 0) {
    ids.splice(idx, 1);
    saveLocalWishlist(ids);
    return false;
  }
  ids.push(strId);
  saveLocalWishlist(ids);
  return true;
}

export async function createOrder({
  userId,
  items,
  shippingAddress,
  totalAmount,
}: {
  userId: string;
  items: CartItem[];
  shippingAddress: string;
  totalAmount: number;
}): Promise<Order> {
  const order: Order = {
    id: `ord-${Date.now()}`,
    user_id: userId,
    status: "pending",
    total_amount: totalAmount,
    shipping_address: shippingAddress,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    items: items.map((item, i) => ({
      id: `oi-${Date.now()}-${i}`,
      order_id: `ord-${Date.now()}`,
      book_id: String(item.book_id),
      quantity: item.quantity,
      price_at_purchase: item.book?.price ?? 14.99,
      book: item.book,
    })),
  };
  try {
    const existing = JSON.parse(localStorage.getItem(ordersKey(userId)) || "[]") as Order[];
    existing.unshift(order);
    localStorage.setItem(ordersKey(userId), JSON.stringify(existing));
  } catch {
    /* ignore */
  }
  await clearCart(userId);
  return order;
}

export async function fetchUserOrders(userId: string): Promise<Order[]> {
  try {
    return JSON.parse(localStorage.getItem(ordersKey(userId)) || "[]") as Order[];
  } catch {
    return [];
  }
}

export function formatPrice(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}
