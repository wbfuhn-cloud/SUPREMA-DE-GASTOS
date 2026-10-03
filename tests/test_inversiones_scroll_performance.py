import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"


class ScrollPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (VISOR / "index.html").read_text(encoding="utf-8")
        cls.css = (VISOR / "style.css").read_text(encoding="utf-8")
        cls.js = (VISOR / "app.js").read_text(encoding="utf-8")

    def test_bolsa_does_not_load_continuous_webgl_renderers(self):
        self.assertNotIn("three.min.js", self.html)
        self.assertNotIn("particle_fluid.js", self.html)
        self.assertNotIn('src="/static/liquidGL.js', self.html)

    def test_scrolling_panels_skip_expensive_paint_work(self):
        self.assertIn("background-attachment: scroll", self.css)
        self.assertIn("backdrop-filter: none", self.css)
        self.assertIn("content-visibility: auto", self.css)
        self.assertIn("html.is-scrolling .page-content .glass-panel", self.css)

    def test_scroll_listener_is_passive_and_polling_is_idempotent(self):
        self.assertIn("pageScroller.addEventListener('scroll'", self.js)
        self.assertIn("{ passive: true }", self.js)
        self.assertIn("if (statusInterval) return;", self.js)
        self.assertIn("statusInterval = null;", self.js)


if __name__ == "__main__":
    unittest.main(verbosity=2)
