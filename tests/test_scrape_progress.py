import unittest
from types import SimpleNamespace

from minerba_scraper import (
    STAGE_COMPANIES, STAGE_DONE, STAGE_PERMITS, STAGE_SAVE, ScrapeProgress,
)
from ui.scrape_progress import ScrapeProgressView, percent, render_error_html, render_progress_html


class ProgressHtmlTest(unittest.TestCase):
    def test_percent_follows_stage_weights(self):
        self.assertEqual(percent(ScrapeProgress(STAGE_COMPANIES)), 0)
        self.assertEqual(percent(ScrapeProgress(STAGE_PERMITS, done=0, total=100)), 5)
        self.assertEqual(percent(ScrapeProgress(STAGE_PERMITS, done=50, total=100)), 48)   # 5 + 85*0.5
        self.assertEqual(percent(ScrapeProgress(STAGE_PERMITS, done=100, total=100)), 90)
        self.assertEqual(percent(ScrapeProgress(STAGE_SAVE, done=1, total=2)), 95)
        self.assertEqual(percent(ScrapeProgress(STAGE_DONE)), 100)

    def test_permit_card_shows_counts_rate_and_failures(self):
        html = render_progress_html(ScrapeProgress(
            STAGE_PERMITS, message="Extracting permits", done=3780, total=9000, permits=12450,
            failed=2, rate=85.4, elapsed=72))
        for text in ("3,780/9,000 companies", "12,450 permits", "85/s", "1:12", "2 failed", "width:"):
            self.assertIn(text, html)
        self.assertNotIn("\n\n", html)  # blank lines break the HTML block in markdown

    def test_company_stage_without_total_is_animated(self):
        self.assertIn("busy", render_progress_html(ScrapeProgress(STAGE_COMPANIES)))

    def test_done_card_and_caption(self):
        html = render_progress_html(ScrapeProgress(STAGE_DONE, message="Done", total=9000, permits=31200,
                                                   elapsed=105), caption="updated 15/10/2026 10:00")
        self.assertIn("✓ Done", html)
        self.assertIn("100%", html)
        self.assertIn("updated 15/10/2026 10:00", html)

    def test_overlay_centers_card_on_screen(self):
        p = ScrapeProgress(STAGE_PERMITS, done=1, total=10)
        self.assertIn('class="sp-overlay"', render_progress_html(p, overlay=True))
        self.assertNotIn('<div class="sp-overlay">', render_progress_html(p))   # the static summary does not float
        self.assertIn("position:fixed", render_progress_html(p))                # the CSS rule is always present

    def test_text_is_escaped(self):
        self.assertNotIn("<script>", render_error_html("<script>alert(1)</script>"))


class ViewTest(unittest.TestCase):
    def test_throttles_but_always_draws_stage_change_and_completion(self):
        drawn = []
        slot = SimpleNamespace(markdown=lambda html, unsafe_allow_html=False: drawn.append(html))
        view = ScrapeProgressView(slot, min_interval=3600)       # practically never passes the time throttle
        view.update(ScrapeProgress(STAGE_PERMITS, done=0, total=10))    # stage change -> drawn
        view.update(ScrapeProgress(STAGE_PERMITS, done=3, total=10))    # held back
        view.update(ScrapeProgress(STAGE_PERMITS, done=10, total=10))   # finished -> drawn
        view.update(ScrapeProgress(STAGE_DONE, total=10))               # DONE -> drawn
        self.assertEqual(len(drawn), 3)
        self.assertTrue(all("sp-overlay" in html for html in drawn))   # running progress is centered
        self.assertEqual(view.last.stage, STAGE_DONE)


if __name__ == "__main__":
    unittest.main()
