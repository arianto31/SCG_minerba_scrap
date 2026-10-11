import os
import time
import logging
import requests
import pandas as pd
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MinerbaScraper:
    # 1. Tambahkan parameter supabase_client di __init__
    def __init__(self, supabase_client):
        load_dotenv()
        self.base_url = "https://minerbaone.esdm.go.id/api/common/v2/publik"
        self.limit = 100
        
        self.test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        self.test_limit = int(os.getenv("TEST_LIMIT", "20"))
        
        self.max_workers = 5
        self.supabase = supabase_client # <-- Simpan koneksi Supabase di sini
        
        self.session = self._setup_resilient_session()

    def _setup_resilient_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        retry_strategy = Retry(
            total=5, read=5, connect=5, backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_json(self, url: str, timeout: int = 30) -> Optional[Dict]:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Gagal mengambil data dari {url} | Error: {e}")
            return None

    def get_all_companies(self) -> pd.DataFrame:
        logging.info("Memulai Step 1: Mengambil daftar perusahaan...")
        all_data = []
        page = 1

        while True:
            url = f"{self.base_url}/badan-usaha?sort=nama_badan_usaha&page={page}&limit={self.limit}&search="
            json_data = self.fetch_json(url)
            
            if not json_data:
                break
            data_block = json_data.get("data", {})
            rows = data_block.get("data", [])
            
            if not rows:
                break

            all_data.extend(rows)
            last_page = data_block.get("last_page", page)

            if self.test_mode and len(all_data) >= self.test_limit:
                all_data = all_data[:self.test_limit]
                break
            if page >= last_page:
                break

            page += 1
            time.sleep(0.3)

        df = pd.DataFrame(all_data)
        kolom_dipakai = ["id_badan_usaha", "nama_badan_usaha", "jenis_badan_usaha", "jenis_perizinan", "alamat"]
        kolom_dipakai = [c for c in kolom_dipakai if c in df.columns]
        return df[kolom_dipakai]

    def get_company_permits(self, id_badan_usaha: str, nama_badan_usaha: str) -> List[Dict]:
        hasil = []
        page = 1
        while True:
            url = (
                f"{self.base_url}/badan-usaha/{id_badan_usaha}/list-perizinan"
                f"?sort=updated_at&filter[status][]=disetujui&filter[status][]=diterima"
                f"&filter[status][]=disuspensi&filter[nomor_izin][like]=&limit=100&page={page}"
            )
            json_data = self.fetch_json(url)
            if not json_data:
                break

            data_block = json_data.get("data", {})
            rows = data_block.get("data", [])
            if not rows:
                break

            for izin in rows:
                # Pastikan semua data tipe datanya aman untuk Supabase (konversi ke string jika perlu)
                hasil.append({
                    "nama_badan_usaha": str(nama_badan_usaha) if nama_badan_usaha else "-",
                    "id_badan_usaha": str(id_badan_usaha) if id_badan_usaha else "-",
                    "nomor_izin": str(izin.get("nomor_izin")) if izin.get("nomor_izin") else "-",
                    "jenis_izin": str((izin.get("jenis_perizinan") or {}).get("jenis_perizinan")) or "-",
                    "tahap_kegiatan": str((izin.get("tahap_kegiatan") or {}).get("deskripsi")) or "-",
                    "golongan": str((izin.get("golongan") or {}).get("nama_golongan")) or "-",
                    "komoditas": str((izin.get("komoditas") or {}).get("nama_komoditas")) or "-",
                    "luas_ha": str(izin.get("luas_ha")) if izin.get("luas_ha") else "-",
                    "tanggal_berlaku": str(izin.get("tanggal_berlaku")) if izin.get("tanggal_berlaku") else "-",
                    "tanggal_berakhir": str(izin.get("tanggal_berakhir")) if izin.get("tanggal_berakhir") else "-",
                    "status_cnc": str((izin.get("status_cnc") or {}).get("status_cnc")) or "-",
                    "lokasi": str(izin.get("lokasi_perizinan")) if izin.get("lokasi_perizinan") else "-",
                    "kode_wiup": str((izin.get("wiup") or {}).get("nomor_wiup") or (izin.get("momi_iup") or {}).get("kode_wiup")) or "-",
                })

            last_page = data_block.get("last_page", page)
            if page >= last_page:
                break
            page += 1
            time.sleep(0.2)
        return hasil

    def process_all_permits(self, df_companies: pd.DataFrame):
        logging.info(f"Memulai Step 2: Mengekstrak detail izin...")
        hasil_final = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.get_company_permits, row.id_badan_usaha, row.nama_badan_usaha): row
                for row in df_companies.itertuples(index=False)
            }

            for i, future in enumerate(as_completed(futures), start=1):
                row = futures[future]
                try:
                    izin_list = future.result()
                    if izin_list:
                        hasil_final.extend(izin_list)
                    logging.info(f"[{i}/{len(df_companies)}] {row.nama_badan_usaha} -> {len(izin_list)} izin")
                except Exception as e:
                    logging.error(f"Gagal memproses {row.nama_badan_usaha}: {e}")

        # 2. HAPUS DATA LAMA & SIMPAN DATA BARU KE SUPABASE
        if hasil_final:
            logging.info("Menghapus data lama di Supabase...")
            self.supabase.table("data_tambang").delete().neq("id", 0).execute()
            
            logging.info(f"Menyimpan {len(hasil_final)} baris data baru ke Supabase...")
            
            # Supabase memiliki limit insert per batch (biasanya 1000 row). Kita potong (chunk) datanya.
            chunk_size = 500
            for j in range(0, len(hasil_final), chunk_size):
                chunk = hasil_final[j:j + chunk_size]
                self.supabase.table("data_tambang").insert(chunk).execute()
                
            logging.info("Proses penyimpanan ke Supabase selesai!")

    def run_pipeline(self):
        df_companies = self.get_all_companies()
        self.process_all_permits(df_companies)