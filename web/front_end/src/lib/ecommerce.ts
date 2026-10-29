import { supabase } from "@/integrations/supabase/client";
import { type Book } from "@/lib/data";

export type CartItem = {
  id: string; // Supabase cart_item id hoặc local temp id
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

// Helper lấy danh sách sách theo batch từ Python API
export async function fetchBooksBatch(bookIds: (string | number)[]): Promise<Record<string, Book>> {
  const numericIds = bookIds
    .map((id) => Number(id))
    .filter((n) => !isNaN(n) && n > 0);

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
      // Đảm bảo sách có giá hợp lý nếu price <= 0
      const price = b.price && b.price > 0 ? b.price : Number((((Number(b.id) * 37) % 30) + 9.99).toFixed(2));
      map[String(b.id)] = { ...b, id: String(b.id), price };
    }
    return map;
  } catch (err) {
    console.error("Error fetching books batch:", err);
    return {};
  }
}

// ─── CART LOGIC ──────────────────────────────────────────────────────────────

export function getLocalCart(): CartItem[] {
  try {
    const data = localStorage.getItem(LOCAL_CART_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveLocalCart(items: CartItem[]) {
  try {
    localStorage.setItem(LOCAL_CART_KEY, JSON.stringify(items));
    window.dispatchEvent(new Event("cart_updated"));
  } catch {}
}

export async function fetchUserCart(userId: string | null): Promise<CartItem[]> {
  let rawItems: { id: string; book_id: string; quantity: number }[] = [];

  if (userId) {
    const { data, error } = await supabase
      .from("cart_items")
      .select("id, book_id, quantity")
      .eq("user_id", userId);

    if (!error && data) {
      rawItems = data;
    }
  } else {
    rawItems = getLocalCart();
  }

  if (rawItems.length === 0) return [];

  // Lấy chi tiết sách từ Python API
  const bookIds = rawItems.map((i) => i.book_id);
  const booksMap = await fetchBooksBatch(bookIds);

  return rawItems.map((item) => ({
    ...item,
    book: booksMap[String(item.book_id)],
  }));
}

export async function addToCart(userId: string | null, bookId: string, quantity = 1): Promise<void> {
  if (userId) {
    // Kiểm tra xem đã có trong cart chưa
    const { data } = await supabase
      .from("cart_items")
      .select("id, quantity")
      .eq("user_id", userId)
      .eq("book_id", bookId)
      .maybeSingle();

    if (data) {
      await supabase
        .from("cart_items")
        .update({ quantity: data.quantity + quantity })
        .eq("id", data.id);
    } else {
      await supabase.from("cart_items").insert({
        user_id: userId,
        book_id: bookId,
        quantity,
      });
    }
  } else {
    const items = getLocalCart();
    const idx = items.findIndex((i) => String(i.book_id) === String(bookId));
    if (idx >= 0 && items[idx]) {
      items[idx]!.quantity += quantity;
    } else {
      items.push({
        id: `local-${Date.now()}-${Math.random()}`,
        book_id: bookId,
        quantity,
      });
    }
    saveLocalCart(items);
  }
}

export async function updateCartQuantity(
  userId: string | null,
  cartItemId: string,
  bookId: string,
  quantity: number
): Promise<void> {
  if (quantity <= 0) {
    return removeFromCart(userId, cartItemId, bookId);
  }

  if (userId) {
    await supabase.from("cart_items").update({ quantity }).eq("id", cartItemId);
  } else {
    const items = getLocalCart();
    const item = items.find((i) => i.id === cartItemId || String(i.book_id) === String(bookId));
    if (item) {
      item.quantity = quantity;
      saveLocalCart(items);
    }
  }
}

export async function removeFromCart(
  userId: string | null,
  cartItemId: string,
  bookId: string
): Promise<void> {
  if (userId) {
    await supabase.from("cart_items").delete().eq("id", cartItemId);
  } else {
    const items = getLocalCart().filter(
      (i) => i.id !== cartItemId && String(i.book_id) !== String(bookId)
    );
    saveLocalCart(items);
  }
}

export async function clearCart(userId: string | null): Promise<void> {
  if (userId) {
    await supabase.from("cart_items").delete().eq("user_id", userId);
  } else {
    saveLocalCart([]);
  }
}

// ─── WISHLIST LOGIC ──────────────────────────────────────────────────────────

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
  } catch {}
}

export async function fetchUserWishlist(userId: string | null): Promise<WishlistItem[]> {
  let rawItems: { id: string; book_id: string; created_at: string }[] = [];

  if (userId) {
    const { data, error } = await supabase
      .from("wishlist_items")
      .select("id, book_id, created_at")
      .eq("user_id", userId);

    if (!error && data) {
      rawItems = data;
    }
  } else {
    const ids = getLocalWishlist();
    rawItems = ids.map((id) => ({
      id: `local-w-${id}`,
      book_id: id,
      created_at: new Date().toISOString(),
    }));
  }

  if (rawItems.length === 0) return [];

  const bookIds = rawItems.map((i) => i.book_id);
  const booksMap = await fetchBooksBatch(bookIds);

  return rawItems.map((item) => ({
    ...item,
    book: booksMap[String(item.book_id)],
  }));
}

export async function toggleWishlist(userId: string | null, bookId: string): Promise<boolean> {
  if (userId) {
    const { data } = await supabase
      .from("wishlist_items")
      .select("id")
      .eq("user_id", userId)
      .eq("book_id", bookId)
      .maybeSingle();

    if (data) {
      await supabase.from("wishlist_items").delete().eq("id", data.id);
      return false; // đã xóa
    } else {
      await supabase.from("wishlist_items").insert({
        user_id: userId,
        book_id: bookId,
      });
      return true; // đã thêm
    }
  } else {
    const ids = getLocalWishlist();
    const strId = String(bookId);
    const idx = ids.indexOf(strId);
    if (idx >= 0) {
      ids.splice(idx, 1);
      saveLocalWishlist(ids);
      return false;
    } else {
      ids.push(strId);
      saveLocalWishlist(ids);
      return true;
    }
  }
}

// ─── ORDER & CHECKOUT ────────────────────────────────────────────────────────

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
  // 1. Tạo đơn hàng
  const { data: order, error: orderErr } = await supabase
    .from("orders")
    .insert({
      user_id: userId,
      status: "pending",
      total_amount: totalAmount,
      shipping_address: shippingAddress,
    })
    .select()
    .single();

  if (orderErr || !order) {
    throw new Error(orderErr?.message || "Không thể tạo đơn hàng");
  }

  // 2. Tạo chi tiết đơn hàng
  const orderItemsData = items.map((item) => ({
    order_id: order.id,
    book_id: String(item.book_id),
    quantity: item.quantity,
    price_at_purchase: item.book?.price ?? 14.99,
  }));

  const { error: itemsErr } = await supabase.from("order_items").insert(orderItemsData);
  if (itemsErr) {
    console.error("Order items error:", itemsErr);
  }

  // 3. Dọn sạch giỏ hàng
  await clearCart(userId);

  return order as Order;
}

export async function fetchUserOrders(userId: string): Promise<Order[]> {
  const { data: orders, error } = await supabase
    .from("orders")
    .select("id, user_id, status, total_amount, shipping_address, created_at, updated_at")
    .eq("user_id", userId)
    .order("created_at", { ascending: false });

  if (error || !orders) return [];

  // Lấy chi tiết order_items cho từng đơn
  const orderIds = orders.map((o) => o.id);
  if (orderIds.length === 0) return [];

  const { data: itemsData } = await supabase
    .from("order_items")
    .select("id, order_id, book_id, quantity, price_at_purchase")
    .in("order_id", orderIds);

  const bookIds = (itemsData || []).map((i) => i.book_id);
  const booksMap = await fetchBooksBatch(bookIds);

  const itemsByOrder: Record<string, OrderItem[]> = {};
  for (const it of itemsData || []) {
    if (!itemsByOrder[it.order_id]) {
      itemsByOrder[it.order_id] = [];
    }
    const orderList = itemsByOrder[it.order_id];
    if (orderList) {
      orderList.push({
        ...it,
        book: booksMap[String(it.book_id)],
      });
    }
  }

  return orders.map((o) => ({
    ...o,
    items: itemsByOrder[o.id] || [],
  })) as Order[];
}

export function formatPrice(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}
