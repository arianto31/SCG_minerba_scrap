import asyncio
import unittest

import httpx

from minerba_scraper import (
    STAGE_COMPANIES, STAGE_DONE, STAGE_PERMITS, STAGE_SAVE, AdaptiveGate, MinerbaScraper, ScrapeError,
)


class FakeResponse:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data, headers or {}

    def json(self):
        return self._data


def page(rows, last_page=1):
    return {"data": {"data": rows, "last_page": last_page}}


class FakeClient:
    """Klien HTTP palsh: `handler(url, call_number)` menentukan respons. Mencatat konkurensi puncak."""

    def __init__(self, handler, latency=0.0):
        self.handler, self.latency, self.calls, self.active, self.peak = handler, latency, 0, 0, 0

    async def get(self, url):
        self.calls += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.latency)
            result = self.handler(url, self.calls)
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            self.active -= 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeTable:
    def __init__(self, store, name):
        self.store, self.name, self.op = store, name, None

    def select(self, *_):
        self.op = "select"; return self

    def order(self, *_, **__): return self
    def limit(self, *_): return self
    def lte(self, *_): self.op = "delete_old"; return self
    def gt(self, *_): self.op = "rollback"; return self
    def gte(self, *_): self.op = "rollback"; return self

    def insert(self, rows, **_):
        self.op, self.rows = "insert", rows; return self

    def delete(self):
        self.op = "delete"; return self

    def execute(self):
        if self.op == "insert":
            self.store["inserted"].extend(self.rows)
        elif self.op == "delete_old":
            self.store["deleted"] = True
        elif self.op == "rollback":
            self.store["rolled_back"] = True
        return type("R", (), {"data": [{"id": 7}] if self.op == "select" else []})()


class FakeSupabase:
    def __init__(self):
        self.store = {"inserted": [], "deleted": False, "rolled_back": False}

    def table(self, name):
        return FakeTable(self.store, name)


def make_scraper(client, workers=8):
    scraper = MinerbaScraper(FakeSupabase())
    scraper.max_workers, scraper.backoff_base, scraper.retry_pass_delay = workers, 0.001, 0
    scraper.save_backoff = 0
    scraper._build_client = lambda: client
    return scraper


class AdaptiveGateTest(unittest.IsolatedAsyncioTestCase):
    async def test_penalty_shrinks_and_rewards_recover(self):
        gate = AdaptiveGate(maximum=20, minimum=4)
        gate.penalize()
        self.assertEqual(gate.limit, 14)
        gate.penalize()  # masih dalam masa jeda -> tidak turun dua kali
        self.assertEqual(gate.limit, 14)
        for _ in range(AdaptiveGate.RECOVER_AFTER):
            gate.reward()
        self.assertEqual(gate.limit, 15)

    async def test_limit_never_below_minimum(self):
        gate = AdaptiveGate(maximum=5, minimum=4)
        gate._last_penalty = -10
        gate.penalize()
        self.assertEqual(gate.limit, 4)


class GetJsonTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.scraper = make_scraper(None)
        self.scraper.gate = AdaptiveGate(maximum=8)

    async def test_retries_429_then_succeeds(self):
        client = FakeClient(lambda url, n: FakeResponse(429, headers={"Retry-After": "0.01"}) if n < 3
                            else FakeResponse(200, {"ok": 1}))
        self.scraper.client = client
        self.assertEqual(await self.scraper._get_json("u"), {"ok": 1})
        self.assertEqual(client.calls, 3)
        self.assertLess(self.scraper.gate.limit, 8)  # konkurensi diturunkan

    async def test_retries_transport_error(self):
        client = FakeClient(lambda url, n: httpx.ConnectError("boom") if n == 1 else FakeResponse(200, {"ok": 1}))
        self.scraper.client = client
        self.assertEqual(await self.scraper._get_json("u"), {"ok": 1})

    async def test_client_error_is_not_retried(self):
        client = FakeClient(lambda url, n: FakeResponse(404))
        self.scraper.client = client
        with self.assertRaises(ScrapeError):
            await self.scraper._get_json("u")
        self.assertEqual(client.calls, 1)

    async def test_gives_up_after_max_retries(self):
        client = FakeClient(lambda url, n: FakeResponse(500))
        self.scraper.client = client
        self.scraper.max_retries = 2
        with self.assertRaises(ScrapeError):
            await self.scraper._get_json("u")
        self.assertEqual(client.calls, 3)


class PipelineTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def permit(no):
        return {"nomor_izin": no, "jenis_perizinan": {"jenis_perizinan": "IUP OP"}, "luas_ha": 10,
                "tanggal_berakhir": "2030-01-01"}

    def handler(self, url, n):
        if "/badan-usaha?" in url:
            return FakeResponse(200, page([{"id_badan_usaha": f"c{i}", "nama_badan_usaha": f"PT {i}"}
                                           for i in range(40)]))
        company = url.split("/badan-usaha/")[1].split("/")[0]
        if company == "c13":
            return FakeResponse(404)  # satu perusahaan selalu gagal
        if company == "c5":  # perusahaan dengan 3 halaman izin
            page_no = int(url.rsplit("page=", 1)[1])
            return FakeResponse(200, page([self.permit(f"c5-{page_no}")], last_page=3))
        return FakeResponse(200, page([self.permit(f"{company}-1")]))

    async def test_collects_all_pages_and_isolates_failures(self):
        scraper = make_scraper(FakeClient(self.handler, latency=0.005), workers=10)
        rows = await scraper._scrape_all()
        numbers = {r["nomor_izin"] for r in rows}
        self.assertEqual(len(rows), 39 - 1 + 3)            # 40 perusahaan - c13 gagal - c5(1) + c5(3 halaman)
        self.assertTrue({"c5-1", "c5-2", "c5-3"} <= numbers)
        self.assertNotIn("c13-1", numbers)
        self.assertEqual(rows[0]["jenis_izin"], "IUP OP")

    async def test_concurrency_respects_limit(self):
        client = FakeClient(self.handler, latency=0.01)
        await make_scraper(client, workers=6)._scrape_all()
        self.assertLessEqual(client.peak, 6)
        self.assertGreater(client.peak, 1)

    def test_run_pipeline_saves_and_deletes_old_rows(self):
        scraper = make_scraper(FakeClient(self.handler))
        scraper.run_pipeline()
        store = scraper.supabase.store
        self.assertEqual(len(store["inserted"]), 41)
        self.assertTrue(store["deleted"])

    def test_progress_events_cover_all_stages_in_order(self):
        events = []
        scraper = make_scraper(FakeClient(self.handler))
        scraper.on_progress = events.append
        scraper.run_pipeline()

        stages = [e.stage for e in events]
        order = [STAGE_COMPANIES, STAGE_PERMITS, STAGE_SAVE, STAGE_DONE]
        self.assertEqual(sorted(set(stages), key=order.index), order)
        self.assertEqual(stages, sorted(stages, key=order.index))        # urutan tahap tidak mundur
        permits = [e for e in events if e.stage == STAGE_PERMITS]
        self.assertEqual(permits[-1].done, permits[-1].total)             # perusahaan utama selesai semua
        last = events[-1]
        self.assertEqual((last.stage, last.permits, last.failed), (STAGE_DONE, 41, 1))   # c13 gagal
        self.assertEqual(last.total, 40)
        self.assertGreaterEqual(last.elapsed, 0)

    def test_failing_callback_does_not_break_scraping(self):
        def broken(_):
            raise RuntimeError("ui error")
        scraper = make_scraper(FakeClient(self.handler))
        scraper.on_progress = broken
        scraper.run_pipeline()
        self.assertEqual(len(scraper.supabase.store["inserted"]), 41)

    def test_transient_socket_error_on_save_is_retried(self):
        scraper = make_scraper(FakeClient(self.handler))
        original, calls = scraper._insert_once, []

        def flaky(chunk):
            calls.append(1)
            if len(calls) == 1:
                raise httpx.WriteError("[WinError 10035] socket")
            return original(chunk)
        scraper._insert_once = flaky
        scraper.run_pipeline()
        self.assertEqual(len(scraper.supabase.store["inserted"]), 41)
        self.assertTrue(scraper.supabase.store["deleted"])
        self.assertFalse(scraper.supabase.store["rolled_back"])

    def test_permanent_save_failure_rolls_back_and_keeps_old_data(self):
        scraper = make_scraper(FakeClient(self.handler))
        scraper.save_retries = 1

        def always_fails(chunk):
            raise httpx.WriteError("[WinError 10035] socket")
        scraper._insert_once = always_fails
        with self.assertRaises(httpx.WriteError):
            scraper.run_pipeline()
        store = scraper.supabase.store
        self.assertTrue(store["rolled_back"])   # baris baru yang sempat masuk dibatalkan
        self.assertFalse(store["deleted"])      # data lama tidak disentuh

    def test_save_is_sequential_by_default(self):
        self.assertEqual(MinerbaScraper(FakeSupabase()).save_workers, 1)

    def test_empty_result_keeps_old_data(self):
        scraper = make_scraper(FakeClient(lambda url, n: FakeResponse(200, page([]))))
        scraper.run_pipeline()
        self.assertFalse(scraper.supabase.store["deleted"])


if __name__ == "__main__":
    unittest.main()
