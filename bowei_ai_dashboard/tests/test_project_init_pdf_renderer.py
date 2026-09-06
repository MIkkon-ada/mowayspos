from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from app.services import project_init_pdf_renderer as renderer


def _write_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=144, height=144)
    with path.open("wb") as output:
        writer.write(output)


def test_renders_bounded_pngs_for_each_scanned_pdf_page(tmp_path):
    source = tmp_path / "scanned.pdf"
    _write_pdf(source, 2)

    rendered = renderer.render_project_init_pdf_images(source, tmp_path / "rendered")

    assert [path.name for path in rendered] == ["page-001.png", "page-002.png"]
    assert all(path.is_file() for path in rendered)
    with Image.open(rendered[0]) as image:
        assert image.width <= renderer.MAX_RENDERED_WIDTH
        assert image.height <= renderer.MAX_RENDERED_HEIGHT


def test_rejects_pdf_that_exceeds_vision_page_limit(tmp_path, monkeypatch):
    source = tmp_path / "many-pages.pdf"
    _write_pdf(source, 2)
    monkeypatch.setattr(renderer, "MAX_PDF_VISION_PAGES", 1)

    with pytest.raises(renderer.ProjectInitPdfRenderLimitError, match="page limit"):
        renderer.render_project_init_pdf_images(source, tmp_path / "rendered")
