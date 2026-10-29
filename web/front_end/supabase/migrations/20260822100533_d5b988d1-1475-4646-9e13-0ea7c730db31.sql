
-- ROLES
create type public.app_role as enum ('admin','moderator','user');

create table public.user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role app_role not null default 'user',
  created_at timestamptz not null default now(),
  unique (user_id, role)
);
grant select on public.user_roles to authenticated;
grant all on public.user_roles to service_role;
alter table public.user_roles enable row level security;

create or replace function public.has_role(_user_id uuid, _role app_role)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.user_roles where user_id = _user_id and role = _role)
$$;

create policy "read own roles" on public.user_roles for select to authenticated using (auth.uid() = user_id);
create policy "admins read all roles" on public.user_roles for select to authenticated using (public.has_role(auth.uid(),'admin'));

-- PROFILES
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default 'Reader',
  bio text default 'Book Lover',
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
grant select, insert, update on public.profiles to authenticated;
grant select on public.profiles to anon;
grant all on public.profiles to service_role;
alter table public.profiles enable row level security;
create policy "profiles public read" on public.profiles for select using (true);
create policy "profiles self insert" on public.profiles for insert to authenticated with check (auth.uid() = id);
create policy "profiles self update" on public.profiles for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- PREFERENCES
create table public.user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  theme text not null default 'light',
  language text not null default 'en',
  push_notifications boolean not null default true,
  email_updates boolean not null default true,
  favorite_genres text[] not null default '{}',
  updated_at timestamptz not null default now()
);
grant select, insert, update on public.user_preferences to authenticated;
grant all on public.user_preferences to service_role;
alter table public.user_preferences enable row level security;
create policy "prefs own" on public.user_preferences for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, avatar_url)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email,'@',1)), new.raw_user_meta_data->>'avatar_url')
  on conflict (id) do nothing;
  insert into public.user_preferences (user_id) values (new.id) on conflict do nothing;
  insert into public.user_roles (user_id, role) values (new.id, 'user') on conflict do nothing;
  return new;
end; $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

-- CATALOG
create table public.authors (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  bio text,
  created_at timestamptz not null default now()
);
grant select on public.authors to anon, authenticated;
grant all on public.authors to service_role;
alter table public.authors enable row level security;
create policy "authors public read" on public.authors for select using (true);
create policy "authors admin write" on public.authors for all to authenticated using (public.has_role(auth.uid(),'admin')) with check (public.has_role(auth.uid(),'admin'));

create table public.categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  slug text not null unique,
  icon text not null default 'book',
  sort_order int not null default 0
);
grant select on public.categories to anon, authenticated;
grant all on public.categories to service_role;
alter table public.categories enable row level security;
create policy "categories public read" on public.categories for select using (true);
create policy "categories admin write" on public.categories for all to authenticated using (public.has_role(auth.uid(),'admin')) with check (public.has_role(auth.uid(),'admin'));

create table public.books (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  author_id uuid references public.authors(id) on delete set null,
  author_name text not null default '',
  description text,
  cover_url text,
  isbn text,
  published_year int,
  pages int,
  language text not null default 'English',
  rating numeric(2,1) not null default 0,
  ratings_count int not null default 0,
  trending_rank int,
  created_at timestamptz not null default now()
);
create index books_title_idx on public.books (lower(title));
grant select on public.books to anon, authenticated;
grant all on public.books to service_role;
alter table public.books enable row level security;
create policy "books public read" on public.books for select using (true);
create policy "books admin write" on public.books for all to authenticated using (public.has_role(auth.uid(),'admin')) with check (public.has_role(auth.uid(),'admin'));

create table public.book_categories (
  book_id uuid not null references public.books(id) on delete cascade,
  category_id uuid not null references public.categories(id) on delete cascade,
  primary key (book_id, category_id)
);
grant select on public.book_categories to anon, authenticated;
grant all on public.book_categories to service_role;
alter table public.book_categories enable row level security;
create policy "book_categories public read" on public.book_categories for select using (true);
create policy "book_categories admin write" on public.book_categories for all to authenticated using (public.has_role(auth.uid(),'admin')) with check (public.has_role(auth.uid(),'admin'));

-- READING LIST
create table public.user_books (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  book_id uuid not null references public.books(id) on delete cascade,
  status text not null default 'want_to_read',
  progress int not null default 0,
  created_at timestamptz not null default now(),
  unique (user_id, book_id)
);
grant select, insert, update, delete on public.user_books to authenticated;
grant all on public.user_books to service_role;
alter table public.user_books enable row level security;
create policy "user_books own" on public.user_books for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- REVIEWS
create table public.reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  book_id uuid not null references public.books(id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  body text,
  created_at timestamptz not null default now(),
  unique (user_id, book_id)
);
grant select on public.reviews to anon, authenticated;
grant insert, update, delete on public.reviews to authenticated;
grant all on public.reviews to service_role;
alter table public.reviews enable row level security;
create policy "reviews public read" on public.reviews for select using (true);
create policy "reviews own write" on public.reviews for insert to authenticated with check (auth.uid() = user_id);
create policy "reviews own update" on public.reviews for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "reviews own delete" on public.reviews for delete to authenticated using (auth.uid() = user_id or public.has_role(auth.uid(),'admin'));

-- COMMUNITY
create table public.community_posts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null default 'discussions',
  body text not null,
  tags text[] not null default '{}',
  book_id uuid references public.books(id) on delete set null,
  created_at timestamptz not null default now()
);
grant select on public.community_posts to anon, authenticated;
grant insert, update, delete on public.community_posts to authenticated;
grant all on public.community_posts to service_role;
alter table public.community_posts enable row level security;
create policy "posts public read" on public.community_posts for select using (true);
create policy "posts own insert" on public.community_posts for insert to authenticated with check (auth.uid() = user_id);
create policy "posts own update" on public.community_posts for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "posts own delete" on public.community_posts for delete to authenticated using (auth.uid() = user_id or public.has_role(auth.uid(),'admin'));

create table public.post_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.community_posts(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  body text not null,
  created_at timestamptz not null default now()
);
grant select on public.post_comments to anon, authenticated;
grant insert, update, delete on public.post_comments to authenticated;
grant all on public.post_comments to service_role;
alter table public.post_comments enable row level security;
create policy "comments public read" on public.post_comments for select using (true);
create policy "comments own insert" on public.post_comments for insert to authenticated with check (auth.uid() = user_id);
create policy "comments own delete" on public.post_comments for delete to authenticated using (auth.uid() = user_id or public.has_role(auth.uid(),'admin'));

create table public.post_likes (
  post_id uuid not null references public.community_posts(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
grant select on public.post_likes to anon, authenticated;
grant insert, delete on public.post_likes to authenticated;
grant all on public.post_likes to service_role;
alter table public.post_likes enable row level security;
create policy "likes public read" on public.post_likes for select using (true);
create policy "likes own" on public.post_likes for insert to authenticated with check (auth.uid() = user_id);
create policy "likes own delete" on public.post_likes for delete to authenticated using (auth.uid() = user_id);

-- CHAT
create table public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null,
  content text not null,
  created_at timestamptz not null default now()
);
grant select, insert, delete on public.chat_messages to authenticated;
grant all on public.chat_messages to service_role;
alter table public.chat_messages enable row level security;
create policy "chat own" on public.chat_messages for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- NOTIFICATIONS
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  body text,
  read boolean not null default false,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.notifications to authenticated;
grant all on public.notifications to service_role;
alter table public.notifications enable row level security;
create policy "notifications own" on public.notifications for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- SEED CATEGORIES
insert into public.categories (name, slug, icon, sort_order) values
 ('Fiction','fiction','book-open',1),
 ('Fantasy','fantasy','star',2),
 ('Sci-Fi','sci-fi','rocket',3),
 ('Romance','romance','heart',4),
 ('Mystery','mystery','search',5),
 ('Biography','biography','user-round',6),
 ('Self-Help','self-help','sparkle',7),
 ('Business','business','briefcase',8),
 ('History','history','landmark',9),
 ('Poetry','poetry','feather',10),
 ('Adventure','adventure','compass',11),
 ('Classic','classic','crown',12);

-- SEED AUTHORS
insert into public.authors (name) values
 ('Frank Herbert'),('James Clear'),('Andy Weir'),('Paulo Coelho'),('Yuval Noah Harari'),
 ('Matt Haig'),('Tara Westover'),('George Orwell'),('Patrick Rothfuss'),('J.R.R. Tolkien'),
 ('Harper Lee'),('Jane Austen'),('Isaac Asimov'),('Alex Michaelides'),('Michelle Obama'),
 ('Cal Newport'),('Delia Owens'),('Madeline Miller'),('Brandon Sanderson'),('Agatha Christie');

-- SEED BOOKS
insert into public.books (title, author_name, description, cover_url, isbn, published_year, pages, language, rating, ratings_count, trending_rank) values
 ('Dune','Frank Herbert','Set on the desert planet Arrakis, Dune tells the story of young Paul Atreides, whose family accepts stewardship of the most precious substance in the universe. A timeless epic of survival, politics, power and destiny.','https://covers.openlibrary.org/b/isbn/9780441013593-L.jpg','9780441013593',1965,412,'English',4.8,24512,1),
 ('Atomic Habits','James Clear','An easy and proven way to build good habits and break bad ones, with practical strategies grounded in biology, psychology and neuroscience.','https://covers.openlibrary.org/b/isbn/9780735211292-L.jpg','9780735211292',2018,320,'English',4.7,18320,2),
 ('The Martian','Andy Weir','A lone astronaut must survive on Mars using his ingenuity and science after being left behind by his crew.','https://covers.openlibrary.org/b/isbn/9780553418026-L.jpg','9780553418026',2011,369,'English',4.6,16044,3),
 ('Project Hail Mary','Andy Weir','A lone astronaut wakes with no memory aboard a spacecraft, and must solve an extinction-level mystery to save Earth.','https://covers.openlibrary.org/b/isbn/9780593135204-L.jpg','9780593135204',2021,476,'English',4.5,14210,4),
 ('The Alchemist','Paulo Coelho','A shepherd boy travels from Spain to the Egyptian desert in search of a treasure, and discovers the wisdom of following his heart.','https://covers.openlibrary.org/b/isbn/9780062315007-L.jpg','9780062315007',1988,208,'English',4.7,21988,5),
 ('Sapiens','Yuval Noah Harari','A brief history of humankind, tracing our species from the Stone Age to the age of artificial intelligence.','https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg','9780062316097',2011,443,'English',4.6,19870,6),
 ('The Midnight Library','Matt Haig','Between life and death is a library where each book lets you try another version of your life.','https://covers.openlibrary.org/b/isbn/9780525559474-L.jpg','9780525559474',2020,304,'English',4.6,15320,7),
 ('Educated','Tara Westover','A memoir about a young woman who leaves her survivalist family and goes on to earn a PhD from Cambridge University.','https://covers.openlibrary.org/b/isbn/9780399590504-L.jpg','9780399590504',2018,352,'English',4.7,17540,8),
 ('1984','George Orwell','In a totalitarian superstate, Winston Smith rebels against constant surveillance and the tyranny of the Party.','https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg','9780451524935',1949,328,'English',4.8,30111,9),
 ('The Name of the Wind','Patrick Rothfuss','The first-hand account of Kvothe, an infamous magician, musician and adventurer, told in his own words.','https://covers.openlibrary.org/b/isbn/9780756404741-L.jpg','9780756404741',2007,662,'English',4.9,12980,10),
 ('The Lord of the Rings','J.R.R. Tolkien','The epic quest to destroy the One Ring and defeat the Dark Lord Sauron.','https://covers.openlibrary.org/b/isbn/9780618640157-L.jpg','9780618640157',1954,1178,'English',4.8,28744,11),
 ('To Kill a Mockingbird','Harper Lee','A young girl in the American South watches her father defend a black man falsely accused of a crime.','https://covers.openlibrary.org/b/isbn/9780061120084-L.jpg','9780061120084',1960,336,'English',4.7,26310,12),
 ('Pride and Prejudice','Jane Austen','Elizabeth Bennet navigates manners, morality and marriage in Georgian England.','https://covers.openlibrary.org/b/isbn/9780141439518-L.jpg','9780141439518',1813,432,'English',4.7,24101,13),
 ('Foundation','Isaac Asimov','A mathematician predicts the fall of the Galactic Empire and creates a Foundation to preserve knowledge.','https://covers.openlibrary.org/b/isbn/9780553293357-L.jpg','9780553293357',1951,244,'English',4.5,11220,14),
 ('The Silent Patient','Alex Michaelides','A famous painter shoots her husband and never speaks again; a psychotherapist is determined to find out why.','https://covers.openlibrary.org/b/isbn/9781250301697-L.jpg','9781250301697',2019,336,'English',4.4,13980,15),
 ('Becoming','Michelle Obama','The intimate memoir of the former First Lady of the United States.','https://covers.openlibrary.org/b/isbn/9781524763138-L.jpg','9781524763138',2018,448,'English',4.7,20455,16),
 ('Deep Work','Cal Newport','Rules for focused success in a distracted world.','https://covers.openlibrary.org/b/isbn/9781455586691-L.jpg','9781455586691',2016,304,'English',4.5,9880,17),
 ('Where the Crawdads Sing','Delia Owens','A girl raised alone in the marshes of North Carolina becomes a suspect in a murder case.','https://covers.openlibrary.org/b/isbn/9780735219090-L.jpg','9780735219090',2018,384,'English',4.6,18770,18),
 ('Circe','Madeline Miller','The story of the witch of Aiaia, banished by the gods and forging her own power.','https://covers.openlibrary.org/b/isbn/9780316556347-L.jpg','9780316556347',2018,393,'English',4.6,12455,19),
 ('Dune Messiah','Frank Herbert','The sequel to Dune, following Paul Atreides as emperor and the price of prophecy.','https://covers.openlibrary.org/b/isbn/9780441172696-L.jpg','9780441172696',1969,336,'English',4.6,8120,20),
 ('Children of Dune','Frank Herbert','The children of Paul Atreides inherit a dangerous legacy on Arrakis.','https://covers.openlibrary.org/b/isbn/9780441104024-L.jpg','9780441104024',1976,444,'English',4.5,7210,21),
 ('The Way of Kings','Brandon Sanderson','On the storm-scoured world of Roshar, war rages while ancient powers awaken.','https://covers.openlibrary.org/b/isbn/9780765365279-L.jpg','9780765365279',2010,1007,'English',4.8,14320,22),
 ('Murder on the Orient Express','Agatha Christie','Hercule Poirot investigates a murder aboard a snowbound luxury train.','https://covers.openlibrary.org/b/isbn/9780062693662-L.jpg','9780062693662',1934,274,'English',4.6,15990,23),
 ('The Hobbit','J.R.R. Tolkien','Bilbo Baggins is swept into a quest to reclaim a dwarven kingdom from a dragon.','https://covers.openlibrary.org/b/isbn/9780547928227-L.jpg','9780547928227',1937,310,'English',4.8,25680,24);

update public.books b set author_id = a.id from public.authors a where a.name = b.author_name;

insert into public.book_categories (book_id, category_id)
select b.id, c.id from (values
 ('Dune','sci-fi'),('Dune','adventure'),('Dune','classic'),
 ('Atomic Habits','self-help'),('Atomic Habits','business'),
 ('The Martian','sci-fi'),('The Martian','adventure'),
 ('Project Hail Mary','sci-fi'),('Project Hail Mary','adventure'),
 ('The Alchemist','fiction'),('The Alchemist','classic'),
 ('Sapiens','history'),('Sapiens','biography'),
 ('The Midnight Library','fiction'),
 ('Educated','biography'),
 ('1984','sci-fi'),('1984','classic'),('1984','fiction'),
 ('The Name of the Wind','fantasy'),('The Name of the Wind','adventure'),
 ('The Lord of the Rings','fantasy'),('The Lord of the Rings','classic'),
 ('To Kill a Mockingbird','classic'),('To Kill a Mockingbird','fiction'),
 ('Pride and Prejudice','romance'),('Pride and Prejudice','classic'),
 ('Foundation','sci-fi'),
 ('The Silent Patient','mystery'),
 ('Becoming','biography'),
 ('Deep Work','self-help'),('Deep Work','business'),
 ('Where the Crawdads Sing','fiction'),('Where the Crawdads Sing','mystery'),
 ('Circe','fantasy'),
 ('Dune Messiah','sci-fi'),
 ('Children of Dune','sci-fi'),
 ('The Way of Kings','fantasy'),
 ('Murder on the Orient Express','mystery'),('Murder on the Orient Express','classic'),
 ('The Hobbit','fantasy'),('The Hobbit','adventure')
) as x(title, slug)
join public.books b on b.title = x.title
join public.categories c on c.slug = x.slug;
