-- Run once in Supabase (SQL Editor). Safe to run again.

-- 1) `kategori` column = vendor list name (e.g. 'Vendor Pasir'). Existing rows go to the default list 'Umum'.
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS kategori text NOT NULL DEFAULT 'Umum';

-- 2) `golongan` column = vendor material group (Batuan, Pasir, Fly Ash, etc.).
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS golongan text;

-- 3) (Optional) registry of list names, so empty lists do not disappear after a refresh.
CREATE TABLE IF NOT EXISTS vendor_tables (nama text PRIMARY KEY);
INSERT INTO vendor_tables (nama) VALUES ('Umum') ON CONFLICT DO NOTHING;
ALTER TABLE vendor_tables DISABLE ROW LEVEL SECURITY;
