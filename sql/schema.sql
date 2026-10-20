-- Jalankan sekali di Supabase (SQL Editor).

-- 1) Kolom `kategori` = nama tabel vendor (mis. 'Vendor Pasir'). Data lama otomatis masuk 'Umum'.
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS kategori text NOT NULL DEFAULT 'Umum';

-- 2) Kolom `golongan` = golongan usaha vendor (Batuan, Pasir, Fly Ash, dll).
ALTER TABLE vendor_procurement ADD COLUMN IF NOT EXISTS golongan text;

-- 3) (Opsional) daftar nama tabel, agar tabel yang masih kosong tidak hilang setelah refresh.
CREATE TABLE IF NOT EXISTS vendor_tables (nama text PRIMARY KEY);
INSERT INTO vendor_tables (nama) VALUES ('Umum') ON CONFLICT DO NOTHING;
ALTER TABLE vendor_tables DISABLE ROW LEVEL SECURITY;
