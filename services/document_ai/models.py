"""Model data ekstraksi dokumen: berkas upload dan skema keluaran yang diminta dari Gemini."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# Jenis berkas yang diterima Gemini untuk fitur ini.
ALLOWED_MIME_TYPES = {
    "application/pdf": "PDF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
# Batas total ukuran permintaan (Gemini membatasi ~20 MB untuk data yang dikirim langsung).
MAX_TOTAL_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class UploadedDocument:
    """Satu berkas (foto atau PDF) yang akan dibaca AI."""
    name: str
    data: bytes
    mime_type: str


class DocumentType(str, Enum):
    IUP = "IUP"
    NIB = "NIB"
    SURAT_DUKUNGAN = "SURAT_DUKUNGAN"
    LAINNYA = "LAINNYA"


DOCUMENT_TYPE_LABELS = {
    DocumentType.IUP: "IUP (Izin Usaha Pertambangan)",
    DocumentType.NIB: "NIB (Nomor Induk Berusaha)",
    DocumentType.SURAT_DUKUNGAN: "Surat Dukungan",
    DocumentType.LAINNYA: "Dokumen lain / tidak dikenali",
}

# Kolom tabel vendor yang dapat diisi dari dokumen. Nama field di ExtractedDocument SENGAJA
# sama dengan nama kolom database sehingga pemetaan tidak butuh tabel konversi.
FILLABLE_COLUMNS = (
    "vendor",
    "nib_nomor", "golongan", "nib_tanggal", "nib_lokasi",
    "surat_dukungan_nomor", "surat_dukungan_tanggal", "surat_dukungan_lokasi_quarry",
    "iup_nomor", "iup_nama", "iup_bentuk_usaha",
    "iup_tanggal_terbit", "iup_periode", "iup_tanggal_berakhir",
)


class ExtractedDocument(BaseModel):
    """
    Skema keluaran Gemini. Semua nilai boleh null: isi null jika informasinya tidak tertulis jelas.
    Field tanpa nilai bawaan agar Gemini selalu mengembalikan seluruh kunci.
    """
    document_type: DocumentType = Field(
        description="Jenis dokumen: IUP, NIB, SURAT_DUKUNGAN, atau LAINNYA bila tidak cocok."
    )
    vendor: Optional[str] = Field(
        description="Nama perusahaan vendor: pemilik NIB, atau penerima dukungan pada surat dukungan. "
                    "Untuk dokumen IUP isi null (pemegang IUP bukan vendor)."
    )
    nib_nomor: Optional[str] = Field(description="Nomor NIB (13 digit) persis seperti tertulis.")
    golongan: Optional[str] = Field(
        description="Golongan/jenis bahan galian usaha sebagaimana tertulis (mis. Batuan, Pasir, Fly Ash). "
                    "Null jika tidak tertulis."
    )
    nib_tanggal: Optional[str] = Field(description="Tanggal terbit NIB, format YYYY-MM-DD.")
    nib_lokasi: Optional[str] = Field(description="Alamat/lokasi usaha pada NIB.")
    surat_dukungan_nomor: Optional[str] = Field(description="Nomor surat dukungan persis seperti tertulis.")
    surat_dukungan_tanggal: Optional[str] = Field(description="Tanggal surat dukungan, format YYYY-MM-DD.")
    surat_dukungan_lokasi_quarry: Optional[str] = Field(
        description="Lokasi quarry/tambang asal material yang disebut pada surat dukungan."
    )
    iup_nomor: Optional[str] = Field(
        description="Nomor izin/SK IUP persis seperti tertulis (termasuk garis miring dan huruf)."
    )
    iup_nama: Optional[str] = Field(
        description="Nama badan usaha PEMEGANG IUP, sesuai penulisan di dokumen (mis. 'PT SUMBER GUNUNG MAJU')."
    )
    iup_bentuk_usaha: Optional[str] = Field(
        description="Bentuk badan usaha pemegang IUP (PT, CV, Koperasi, Perorangan) bila jelas dari dokumen."
    )
    iup_tanggal_terbit: Optional[str] = Field(
        description="Tanggal IUP ditetapkan/diterbitkan, format YYYY-MM-DD."
    )
    iup_periode: Optional[int] = Field(
        description="Jangka waktu IUP dalam tahun (angka bulat), hanya jika tertulis eksplisit."
    )
    iup_tanggal_berakhir: Optional[str] = Field(
        description="Tanggal berakhirnya masa berlaku IUP, format YYYY-MM-DD."
    )
    catatan: Optional[str] = Field(
        description="Catatan singkat: bagian yang buram/tidak terbaca atau meragukan. Null jika tidak ada."
    )
