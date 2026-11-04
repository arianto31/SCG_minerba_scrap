"""Document extraction models: uploaded files and the output schema requested from Gemini."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# File types accepted by Gemini for this feature.
ALLOWED_MIME_TYPES = {
    "application/pdf": "PDF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
# Total request size limit (Gemini allows ~20 MB of inline data).
MAX_TOTAL_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class UploadedDocument:
    """One file (photo or PDF) for the AI to read."""
    name: str
    data: bytes
    mime_type: str


class DocumentType(str, Enum):
    IUP = "IUP"
    NIB = "NIB"
    SURAT_DUKUNGAN = "SURAT_DUKUNGAN"
    OTHER = "OTHER"


DOCUMENT_TYPE_LABELS = {
    DocumentType.IUP: "IUP (Mining Business Permit)",
    DocumentType.NIB: "NIB (Business Identification Number)",
    DocumentType.SURAT_DUKUNGAN: "Support Letter (Surat Dukungan)",
    DocumentType.OTHER: "Other / unrecognised document",
}

# Vendor columns that can be filled from a document. Field names in ExtractedDocument are
# DELIBERATELY identical to the database column names, so no conversion table is needed.
FILLABLE_COLUMNS = (
    "vendor",
    "nib_nomor", "golongan", "nib_tanggal", "nib_lokasi",
    "surat_dukungan_nomor", "surat_dukungan_tanggal", "surat_dukungan_lokasi_quarry",
    "iup_nomor", "iup_nama", "iup_bentuk_usaha",
    "iup_tanggal_terbit", "iup_periode", "iup_tanggal_berakhir",
)


class ExtractedDocument(BaseModel):
    """
    Gemini output schema. Every value may be null: use null when the information is not clearly written.
    Fields have no defaults so Gemini always returns every key.
    """
    document_type: DocumentType = Field(
        description="Document type: IUP, NIB, SURAT_DUKUNGAN, or OTHER when none fits."
    )
    vendor: Optional[str] = Field(
        description="Vendor company name: the NIB owner, or the company receiving support in a support letter. "
                    "For IUP documents use null (the IUP holder is not the vendor)."
    )
    nib_nomor: Optional[str] = Field(description="NIB number (13 digits) exactly as written.")
    golongan: Optional[str] = Field(
        description="Business/mineral group exactly as written (e.g. Batuan, Pasir, Fly Ash). "
                    "Null if not written."
    )
    nib_tanggal: Optional[str] = Field(description="NIB issue date, format YYYY-MM-DD.")
    nib_lokasi: Optional[str] = Field(
        description="Material allocation: where the material is allocated, only when the document states it "
                    "explicitly. Not the business address. Otherwise null.")
    surat_dukungan_nomor: Optional[str] = Field(description="Support letter number exactly as written.")
    surat_dukungan_tanggal: Optional[str] = Field(description="Support letter date, format YYYY-MM-DD.")
    surat_dukungan_lokasi_quarry: Optional[str] = Field(
        description="Quarry/mine location of the material mentioned in the support letter."
    )
    iup_nomor: Optional[str] = Field(
        description="IUP permit/decree number exactly as written (including slashes and letters)."
    )
    iup_nama: Optional[str] = Field(
        description="Name of the company HOLDING the IUP, as written in the document (e.g. 'PT SUMBER GUNUNG MAJU')."
    )
    iup_bentuk_usaha: Optional[str] = Field(
        description="Legal entity type of the IUP holder (PT, CV, Koperasi, Perorangan) when clear from the document."
    )
    iup_tanggal_terbit: Optional[str] = Field(
        description="Date the IUP was issued/decided, format YYYY-MM-DD."
    )
    iup_periode: Optional[int] = Field(
        description="IUP term in years (whole number), only when written explicitly."
    )
    iup_tanggal_berakhir: Optional[str] = Field(
        description="Date the IUP validity ends, format YYYY-MM-DD."
    )
    notes: Optional[str] = Field(
        description="Short note in English: parts that are blurry/unreadable or uncertain. Null if none."
    )
