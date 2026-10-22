ALTER TABLE public.books ADD COLUMN IF NOT EXISTS publisher text, ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT '{}';

UPDATE public.books SET publisher = v.publisher, tags = v.tags FROM (VALUES
 ('Dune','Chilton Books', ARRAY['epic','desert','politics','classic']),
 ('Dune Messiah','G. P. Putnam''s Sons', ARRAY['epic','sequel','politics']),
 ('Children of Dune','G. P. Putnam''s Sons', ARRAY['epic','sequel','space opera']),
 ('Atomic Habits','Avery', ARRAY['productivity','self-improvement','psychology']),
 ('Deep Work','Grand Central Publishing', ARRAY['focus','productivity','career']),
 ('Sapiens','Harper', ARRAY['history','anthropology','big ideas']),
 ('Educated','Random House', ARRAY['memoir','education','family']),
 ('Becoming','Crown', ARRAY['memoir','inspiration','politics']),
 ('1984','Secker & Warburg', ARRAY['dystopia','classic','politics']),
 ('Foundation','Gnome Press', ARRAY['space opera','classic','science']),
 ('Circe','Little, Brown and Company', ARRAY['mythology','retelling','fantasy']),
 ('Murder on the Orient Express','Collins Crime Club', ARRAY['mystery','detective','classic']),
 ('Pride and Prejudice','T. Egerton', ARRAY['romance','classic','society']),
 ('Project Hail Mary','Ballantine Books', ARRAY['space','science','survival']),
 ('The Alchemist','HarperTorch', ARRAY['philosophy','journey','inspiration']),
 ('The Hobbit','George Allen & Unwin', ARRAY['fantasy','adventure','classic']),
 ('The Lord of the Rings','George Allen & Unwin', ARRAY['epic fantasy','adventure','classic']),
 ('The Martian','Crown', ARRAY['space','survival','science']),
 ('The Midnight Library','Canongate Books', ARRAY['contemporary','philosophy','life']),
 ('The Name of the Wind','DAW Books', ARRAY['fantasy','magic','coming of age']),
 ('The Silent Patient','Celadon Books', ARRAY['thriller','psychological','mystery']),
 ('The Way of Kings','Tor Books', ARRAY['epic fantasy','magic','war']),
 ('To Kill a Mockingbird','J. B. Lippincott & Co.', ARRAY['classic','justice','coming of age']),
 ('Where the Crawdads Sing','G. P. Putnam''s Sons', ARRAY['mystery','nature','coming of age'])
) AS v(title, publisher, tags) WHERE public.books.title = v.title;