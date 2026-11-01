-- Run once in Supabase (SQL Editor). Safe to run again.

-- 1) `kategori` column = vendor list name (e.g. 'Vendor Pasir'). Existing rows go to the default list 'Umum'.
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS kategori text NOT NULL DEFAULT 'Umum';

-- 2) `golongan` column = vendor material group (Batuan, Pasir, Fly Ash, etc.).
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS golongan text;

-- 3) (Optional) registry of list names, so empty lists do not disappear after a refresh.
CREATE TABLE IF NOT EXISTS vendor_tables (nama text PRIMARY KEY);
INSERT INTO vendor_tables (nama) VALUES ('Umum') ON CONFLICT DO NOTHING;
ALTER TABLE vendor_tables DISABLE ROW LEVEL SECURITY;

-- 4) `lokasi_maps` column = Google Maps link of the quarry / IUP location.
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS lokasi_maps text;

-- 5) `iup_renewal` column = IUP renewal tracker (JSON text: steps, last update, verification).
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS iup_renewal text;

-- 6) `vendor_monthly` table = monthly price per MT and density for each IUP holder + vendor.
CREATE TABLE IF NOT EXISTS vendor_monthly (
  id           bigserial PRIMARY KEY,
  kategori     text    NOT NULL,
  holder_key   text    NOT NULL,
  vendor_key   text    NOT NULL,
  holder       text,
  vendor       text,
  year         integer NOT NULL,
  month        integer NOT NULL CHECK (month BETWEEN 1 AND 12),
  price_per_mt numeric,
  density      numeric,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kategori, holder_key, vendor_key, year, month)
);
ALTER TABLE vendor_monthly DISABLE ROW LEVEL SECURITY;
