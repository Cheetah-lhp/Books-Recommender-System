-- 1. Rename existing categories into official ones
update public.categories set name='Fiction', slug='fiction', icon='book-open', sort_order=1 where slug='fiction';
update public.categories set name='Romance', slug='romance', icon='heart', sort_order=2 where slug='romance';
update public.categories set name='Fantasy & Paranormal', slug='fantasy-paranormal', icon='sparkle', sort_order=3 where slug='fantasy';
update public.categories set name='Mystery, Thriller & Crime', slug='mystery-thriller-crime', icon='search', sort_order=4 where slug='mystery';
update public.categories set name='Poetry', slug='poetry', icon='feather', sort_order=8 where slug='poetry';
update public.categories set name='Non-Fiction', slug='non-fiction', icon='landmark', sort_order=9 where slug='self-help';
update public.categories set name='History & Biography', slug='history-biography', icon='user-round', sort_order=10 where slug='biography';

-- 2. Add the missing official categories
insert into public.categories (name, slug, icon, sort_order)
select v.name, v.slug, v.icon, v.sort_order
from (values
  ('Young Adult','young-adult','star',5),
  ('Children','children','crown',6),
  ('Comics & Graphic','comics-graphic','rocket',7)
) as v(name, slug, icon, sort_order)
where not exists (select 1 from public.categories c where c.slug = v.slug);

-- 3. Remap books from retired categories onto official ones
with remap as (
  select old_c.id as old_id, new_c.id as new_id
  from (values
    ('sci-fi','fiction'),
    ('adventure','fiction'),
    ('classic','fiction'),
    ('history','history-biography'),
    ('business','non-fiction')
  ) as m(old_slug, new_slug)
  join public.categories old_c on old_c.slug = m.old_slug
  join public.categories new_c on new_c.slug = m.new_slug
)
insert into public.book_categories (book_id, category_id)
select distinct bc.book_id, r.new_id
from public.book_categories bc
join remap r on r.old_id = bc.category_id
on conflict do nothing;

-- 4. Drop links to retired categories, then the categories themselves
delete from public.book_categories bc
using public.categories c
where bc.category_id = c.id
  and c.slug in ('sci-fi','adventure','classic','history','business');

delete from public.categories
where slug in ('sci-fi','adventure','classic','history','business');