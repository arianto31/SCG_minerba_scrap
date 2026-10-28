"""
MinerbaOne (ESDM) permit data scraper -> Supabase.

Speed comes from:
  * asyncio + httpx (HTTP/2 when the `h2` package is installed): hundreds of requests run concurrently
  * adaptive concurrency: drops automatically when the server answers 429/5xx, rises again when healthy
  * extra pages (pagination) are fetched in parallel, not one by one
  * saving to Supabase with minimal responses

.env variables (all optional):
  MAX_WORKERS=60            maximum concurrency; raise it if the log shows no 429 errors
  PERMIT_LIMIT=500          permits per page
  MAX_RETRIES=5             retries per request
  REQUEST_TIMEOUT=20        seconds
  USE_HTTP2=true
  SKIP_COMPANIES_WITHOUT_PERMIT=false   skip companies whose jenis_perizinan field is empty
  SAVE_WORKERS=1            parallel database writers
  TEST_MODE=false / TEST_LIMIT=20
"""
import asyncio
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import httpx
import pandas as pd
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RETRY_STATUS = {429, 500, 502, 503, 504}

# Pipeline stages (used to report progress to the UI)
STAGE_COMPANIES, STAGE_PERMITS, STAGE_SAVE, STAGE_DONE = "companies", "permits", "save", "done"


@dataclass(frozen=True)
class ScrapeProgress:
    """Scraping progress snapshot sent to the `on_progress` callback."""
    stage: str
    message: str = ""
    done: int = 0            # companies finished / batches saved (depends on stage)
    total: int = 0
    permits: int = 0         # permits collected
    failed: int = 0
    rate: float = 0.0        # companies per second
    concurrency: int = 0
    elapsed: float = 0.0     # seconds since the pipeline started


class ScrapeError(Exception):
    """A request failed permanently (after all retries) or was rejected by the server."""


class AdaptiveGate:
    """
    AIMD-style concurrency limiter: drops fast (x0.7) when the server refuses, rises slowly (+1)
    after a streak of successes. Also honours the Retry-After header for all workers at once.
    """
    RECOVER_AFTER = 30     # consecutive successes before the limit rises by 1
    PENALTY_COOLDOWN = 1.0  # seconds; simultaneous failures count once

    def __init__(self, maximum: int, minimum: int = 4):
        self.maximum = maximum
        self.minimum = min(minimum, maximum)
        self.limit = maximum
        self._active = 0
        self._streak = 0
        self._pause_until = 0.0
        self._last_penalty = 0.0
        self._cond = asyncio.Condition()

    async def acquire(self) -> None:
        delay = self._pause_until - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        async with self._cond:
            await self._cond.wait_for(lambda: self._active < self.limit)
            self._active += 1

    async def release(self) -> None:
        async with self._cond:
            self._active -= 1
            self._cond.notify_all()

    def reward(self) -> None:
        self._streak += 1
        if self._streak >= self.RECOVER_AFTER and self.limit < self.maximum:
            self.limit += 1
            self._streak = 0

    def penalize(self, pause: float = 0.0) -> None:
        now = time.monotonic()
        if now - self._last_penalty >= self.PENALTY_COOLDOWN:
            self.limit = max(self.minimum, int(self.limit * 0.7))
            self._last_penalty = now
        self._streak = 0
        if pause > 0:
            self._pause_until = max(self._pause_until, now + pause)


def _retry_after(response) -> float:
    """Seconds from the Retry-After header (numeric form only); 0 when absent."""
    try:
        return max(0.0, float(response.headers.get("Retry-After", 0)))
    except (TypeError, ValueError):
        return 0.0


def _unpack(payload) -> Tuple[list, int]:
    """Get (rows, last page number) from an API response."""
    block = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        return [], 1
    rows = block.get("data") or []
    try:
        last_page = int(block.get("last_page") or 1)
    except (TypeError, ValueError):
        last_page = 1
    return rows, last_page


def _has_value(value) -> bool:
    return value not in (None, "", "-", [], {}, "[]", "{}", "null")


class MinerbaScraper:
    def __init__(self, supabase_client, on_progress: Optional[Callable[[ScrapeProgress], None]] = None):
        """`on_progress(ScrapeProgress)` is called regularly; errors in the callback never stop the scraping."""
        load_dotenv()
        self.base_url = "https://minerbaone.esdm.go.id/api/common/v2/publik"
        self.limit = 1000
        self.permit_limit = int(os.getenv("PERMIT_LIMIT", "500"))

        self.test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        self.test_limit = int(os.getenv("TEST_LIMIT", "20"))

        self.max_workers = int(os.getenv("MAX_WORKERS", "60"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "5"))
        self.timeout = float(os.getenv("REQUEST_TIMEOUT", "20"))
        self.use_http2 = os.getenv("USE_HTTP2", "true").lower() == "true"
        self.skip_without_permit = os.getenv("SKIP_COMPANIES_WITHOUT_PERMIT", "false").lower() == "true"
        self.backoff_base = 0.5
        # The Supabase client uses one HTTP/2 connection; writing from many threads at once can trigger
        # WinError 10035 on Windows. Default 1 (sequential); raise SAVE_WORKERS only if it is stable.
        self.save_workers = max(1, int(os.getenv("SAVE_WORKERS", "1")))
        self.save_retries = 4
        self.save_backoff = 1.0
        self.retry_pass_delay = 3.0  # pause before retrying failed companies

        self.supabase = supabase_client
        self.on_progress = on_progress
        self._t0 = time.perf_counter()
        self._stats = {"companies": 0, "failed": 0}
        self.client: Optional[httpx.AsyncClient] = None
        self.gate: Optional[AdaptiveGate] = None

    def _emit(self, stage: str, **fields) -> None:
        if self.on_progress is None:
            return
        try:
            self.on_progress(ScrapeProgress(stage=stage, elapsed=time.perf_counter() - self._t0, **fields))
        except Exception:  # noqa: BLE001 - a UI error must not break the scraping
            logging.exception("on_progress failed (ignored)")

    # ------------------------------------------------------------------ HTTP
    def _build_client(self) -> httpx.AsyncClient:
        options = dict(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=httpx.Limits(max_connections=self.max_workers,
                                max_keepalive_connections=self.max_workers),
            follow_redirects=True,
        )
        if self.use_http2:
            try:
                return httpx.AsyncClient(http2=True, **options)
            except ImportError:
                logging.info("Package 'h2' not found, using HTTP/1.1. Install `pip install httpx[http2]` for more speed.")
        return httpx.AsyncClient(**options)

    def _backoff(self, attempt: int, retry_after: float) -> float:
        wait = min(30.0, self.backoff_base * (2 ** attempt))
        return max(wait, retry_after) + random.uniform(0, self.backoff_base / 2)

    async def _get_json(self, url: str) -> dict:
        """GET + JSON with retries. Raises ScrapeError if it still fails."""
        last_error = "unknown"
        for attempt in range(self.max_retries + 1):
            retry_after = 0.0
            await self.gate.acquire()
            try:
                response = await self.client.get(url)
                status = response.status_code
                if status == 200:
                    payload = response.json()
                    self.gate.reward()
                    return payload
                if status not in RETRY_STATUS:
                    raise ScrapeError(f"HTTP {status} for {url}")
                retry_after = _retry_after(response)
                last_error = f"HTTP {status}"
                self.gate.penalize(retry_after)
            except (httpx.RequestError, ValueError) as exc:  # network/timeout/truncated JSON
                last_error = f"{type(exc).__name__}: {exc}"
                self.gate.penalize()
            finally:
                await self.gate.release()
            await asyncio.sleep(self._backoff(attempt, retry_after))
        raise ScrapeError(f"Failed after {self.max_retries + 1} attempts ({last_error}): {url}")

    # ------------------------------------------------------------------ Step 1: companies
    def _company_url(self, page: int) -> str:
        return f"{self.base_url}/badan-usaha?sort=nama_badan_usaha&page={page}&limit={self.limit}&search="

    async def get_all_companies(self) -> pd.DataFrame:
        logging.info("Starting step 1: fetching the company list...")
        self._emit(STAGE_COMPANIES, message="Fetching company list")
        rows, last_page = _unpack(await self._get_json(self._company_url(1)))
        rows = list(rows)

        if last_page > 1 and not (self.test_mode and len(rows) >= self.test_limit):
            pages = await asyncio.gather(*(self._get_json(self._company_url(p)) for p in range(2, last_page + 1)))
            for payload in pages:  # page order is preserved
                rows.extend(_unpack(payload)[0])
        if self.test_mode:
            rows = rows[:self.test_limit]

        self._emit(STAGE_COMPANIES, message="Company list received", done=len(rows), total=len(rows))
        df = pd.DataFrame(rows)
        cols = ["id_badan_usaha", "nama_badan_usaha", "jenis_badan_usaha", "jenis_perizinan", "alamat"]
        return df[[c for c in cols if c in df.columns]]

    # ------------------------------------------------------------------ Step 2: permits
    @staticmethod
    def _s(value, default="-") -> str:
        """Safe string: None/'' -> '-' (str(None) would give 'None')."""
        return default if value in (None, "") else str(value)

    def _parse_permit(self, permit: dict, id_bu: str, nama_bu: str) -> Dict:
        s = self._s
        g = lambda key: permit.get(key) or {}
        return {
            "nama_badan_usaha": s(nama_bu),
            "id_badan_usaha": s(id_bu),
            "nomor_izin": s(permit.get("nomor_izin")),
            "jenis_izin": s(g("jenis_perizinan").get("jenis_perizinan")),
            "tahap_kegiatan": s(g("tahap_kegiatan").get("deskripsi")),
            "golongan": s(g("golongan").get("nama_golongan")),
            "komoditas": s(g("komoditas").get("nama_komoditas")),
            "luas_ha": s(permit.get("luas_ha")),
            "tanggal_berlaku": s(permit.get("tanggal_berlaku")),
            "tanggal_berakhir": s(permit.get("tanggal_berakhir")),
            "status_cnc": s(g("status_cnc").get("status_cnc")),
            "lokasi": s(permit.get("lokasi_perizinan")),
            "kode_wiup": s(g("wiup").get("nomor_wiup") or g("momi_iup").get("kode_wiup")),
        }

    def _permit_url(self, id_badan_usaha: str, page: int) -> str:
        return (
            f"{self.base_url}/badan-usaha/{id_badan_usaha}/list-perizinan"
            f"?sort=updated_at&filter[status][]=disetujui&filter[status][]=diterima"
            f"&filter[status][]=disuspensi&filter[nomor_izin][like]="
            f"&limit={self.permit_limit}&page={page}"
        )

    async def get_company_permits(self, id_badan_usaha: str, nama_badan_usaha: str) -> List[Dict]:
        rows, last_page = _unpack(await self._get_json(self._permit_url(id_badan_usaha, 1)))
        rows = list(rows)
        if last_page > 1:  # remaining pages in parallel
            pages = await asyncio.gather(
                *(self._get_json(self._permit_url(id_badan_usaha, p)) for p in range(2, last_page + 1))
            )
            for payload in pages:
                rows.extend(_unpack(payload)[0])
        return [self._parse_permit(i, id_badan_usaha, nama_badan_usaha) for i in rows]

    async def _scrape_companies(self, companies: List[Tuple[str, str]], workers: int,
                                offset: int = 0, label: str = "Extracting permits"):
        """Worker pool: each worker takes the next company from the queue."""
        queue: asyncio.Queue = asyncio.Queue()
        for company in companies:
            queue.put_nowait(company)

        rows: List[Dict] = []
        failed: List[Tuple[str, str]] = []
        total, finished, started = len(companies), 0, time.perf_counter()
        self._emit(STAGE_PERMITS, message=label, done=0, total=total, permits=offset,
                   concurrency=self.gate.limit)

        async def worker():
            nonlocal finished
            while True:
                try:
                    id_bu, name = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    rows.extend(await self.get_company_permits(id_bu, name))
                except Exception as exc:  # noqa: BLE001 - one failing company must not stop the others
                    failed.append((id_bu, name))
                    logging.error(f"Failed to process {name}: {exc}")
                finished += 1
                rate = finished / max(time.perf_counter() - started, 1e-6)
                self._emit(STAGE_PERMITS, message=label, done=finished, total=total,
                           permits=offset + len(rows), failed=len(failed), rate=rate,
                           concurrency=self.gate.limit)
                if finished % 500 == 0 or finished == total:
                    logging.info(f"[{finished}/{total}] permits: {len(rows)} | {rate:.0f} companies/s "
                                 f"| concurrency {self.gate.limit}")

        await asyncio.gather(*(worker() for _ in range(max(1, min(workers, total or 1)))))
        return rows, failed

    async def process_all_permits(self, df_companies: pd.DataFrame) -> List[Dict]:
        logging.info("Starting step 2: extracting permit details...")
        if self.skip_without_permit and "jenis_perizinan" in df_companies.columns:
            has_permit = df_companies["jenis_perizinan"].map(_has_value)
            logging.info(f"Skipping {int((~has_permit).sum())} companies without jenis_perizinan data.")
            df_companies = df_companies[has_permit]

        if df_companies.empty:
            logging.warning("The company list is empty.")
            return []
        companies = list(zip(df_companies["id_badan_usaha"], df_companies["nama_badan_usaha"]))
        self._stats["companies"] = len(companies)
        rows, failed = await self._scrape_companies(companies, self.max_workers)
        self._stats["failed"] = len(failed)

        if failed:
            logging.warning(f"{len(failed)} companies failed, retrying with low concurrency...")
            await asyncio.sleep(self.retry_pass_delay)
            retry_rows, still_failed = await self._scrape_companies(
                failed, max(4, self.max_workers // 4),
                offset=len(rows), label="Retrying failed companies",
            )
            rows.extend(retry_rows)
            self._stats["failed"] = len(still_failed)
            if still_failed:
                logging.warning(f"{len(still_failed)} companies still failed: "
                                f"{', '.join(n for _, n in still_failed[:10])}{' ...' if len(still_failed) > 10 else ''}")
        return rows

    # ------------------------------------------------------------------ Step 3: save
    def _save_to_supabase(self, rows: List[Dict], chunk_size: int = 1000, workers: Optional[int] = None):
        if not rows:
            logging.warning("No data to save; existing data was not deleted.")
            return

        table = self.supabase.table
        # Remember the newest old row: old data is only deleted AFTER the new data is safely stored
        res = table("data_tambang").select("id").order("id", desc=True).limit(1).execute()
        old_max_id = res.data[0]["id"] if res.data else None

        logging.info(f"Saving {len(rows)} new rows to Supabase...")
        chunks = [rows[i:i + chunk_size] for i in range(0, len(rows), chunk_size)]
        save_info = dict(done=0, total=len(chunks), permits=len(rows))
        self._emit(STAGE_SAVE, message="Saving to database", **save_info)
        with ThreadPoolExecutor(max_workers=workers or self.save_workers) as ex:
            futures = [ex.submit(self._insert_chunk, c) for c in chunks]
            try:
                for done, f in enumerate(as_completed(futures), start=1):
                    f.result()  # raises if an insert failed -> old data is kept
                    self._emit(STAGE_SAVE, message="Saving to database",
                               **{**save_info, "done": done})
            except Exception:
                for pending in futures:
                    pending.cancel()
                self._rollback_partial_insert(old_max_id)
                raise

        if old_max_id is not None:
            self._emit(STAGE_SAVE, message="Removing old data", **{**save_info, "done": len(chunks)})
            logging.info("Deleting old data...")
            table("data_tambang").delete().lte("id", old_max_id).execute()
        logging.info("Saving to Supabase finished!")

    def _insert_chunk(self, chunk: List[Dict]):
        """Insert one batch; network/socket errors are retried with increasing pauses."""
        for attempt in range(self.save_retries + 1):
            try:
                return self._insert_once(chunk)
            except httpx.RequestError as exc:  # e.g. WinError 10035, timeout, dropped connection
                if attempt == self.save_retries:
                    raise
                wait = self.save_backoff * (2 ** attempt)
                logging.warning(f"Insert failed ({type(exc).__name__}), retrying in {wait:.0f}s "
                                f"({attempt + 1}/{self.save_retries})")
                time.sleep(wait)

    def _insert_once(self, chunk: List[Dict]):
        """Insert with a minimal response (no 1000 rows echoed back) when the library supports it."""
        table = self.supabase.table("data_tambang")
        try:
            from postgrest.types import ReturnMethod
            return table.insert(chunk, returning=ReturnMethod.minimal).execute()
        except (ImportError, TypeError):
            return table.insert(chunk).execute()

    def _rollback_partial_insert(self, old_max_id) -> None:
        """Insert failed half-way: delete the new rows that got in so they do not duplicate the old data."""
        try:
            query = self.supabase.table("data_tambang").delete()
            query = query.gt("id", old_max_id) if old_max_id is not None else query.gte("id", 0)
            query.execute()
            logging.warning("Saving failed; the new rows that got in were removed, old data is intact.")
        except Exception:  # noqa: BLE001
            logging.exception("Could not undo the partial insert; run Refresh again to clean up duplicates.")

    # ------------------------------------------------------------------ pipeline
    async def _scrape_all(self) -> List[Dict]:
        self.gate = AdaptiveGate(maximum=self.max_workers)
        async with self._build_client() as client:
            self.client = client
            df_companies = await self.get_all_companies()
            logging.info(f"{len(df_companies)} companies found.")
            return await self.process_all_permits(df_companies)

    @staticmethod
    def _run(coro):
        """Run a coroutine from sync code (also safe when an event loop already runs, e.g. Jupyter)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()

    def run_pipeline(self):
        self._t0 = started = time.perf_counter()
        self._stats = {"companies": 0, "failed": 0}
        rows = self._run(self._scrape_all())
        logging.info(f"Scraping finished in {time.perf_counter() - started:.0f}s ({len(rows)} permits).")
        self._save_to_supabase(rows)
        logging.info(f"Total pipeline time: {time.perf_counter() - started:.0f}s.")
        self._emit(
            STAGE_DONE,
            message="Done" if rows else "No new data; existing data kept",
            done=self._stats["companies"], total=self._stats["companies"],
            permits=len(rows), failed=self._stats["failed"],
        )
