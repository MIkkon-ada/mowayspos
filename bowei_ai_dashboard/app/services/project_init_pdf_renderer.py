"""Bounded PDF page rendering for project-init Vision fallback."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from PIL import Image
from pypdf import PdfReader


MAX_PDF_VISION_PAGES = 8
MAX_RENDERED_WIDTH = 2_048
MAX_RENDERED_HEIGHT = 2_048
MAX_RENDERED_PIXELS = 4_000_000
MAX_TOTAL_RENDERED_PIXELS = 20_000_000
_RENDER_DPI = 144
_RENDER_TIMEOUT_SECONDS = 30


class ProjectInitPdfRenderLimitError(ValueError):
    """Raised when a scanned PDF cannot be rendered safely for Vision."""


def render_project_init_pdf_images(
    path: Path,
    output_directory: Path,
    *,
    max_images: int = MAX_PDF_VISION_PAGES,
) -> list[Path]:
    """Render a bounded PDF to temporary PNG pages for Vision analysis."""

    if max_images < 1:
        raise ValueError("max_images must be positive")
    source = Path(path)
    try:
        page_count = len(PdfReader(source).pages)
    except Exception as exc:
        raise ProjectInitPdfRenderLimitError("PDF cannot be rendered for Vision") from exc

    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise ProjectInitPdfRenderLimitError(
            "扫描版 PDF 识别依赖 pdftoppm；请安装 Poppler 或使用 Docker 运行后端"
        )

    page_limit = min(max_images, MAX_PDF_VISION_PAGES)
    if page_count < 1:
        raise ProjectInitPdfRenderLimitError("PDF has no pages")
    if page_count > page_limit:
        raise ProjectInitPdfRenderLimitError("PDF exceeds Vision page limit")

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / "rendered"
    try:
        result = subprocess.run(
            [renderer, "-png", "-r", str(_RENDER_DPI), "-f", "1", "-l", str(page_count), str(source), str(prefix)],
            check=False,
            capture_output=True,
            timeout=_RENDER_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise ProjectInitPdfRenderLimitError("PDF cannot be rendered for Vision")
        total_pixels = 0
        rendered: list[Path] = []
        for index in range(1, page_count + 1):
            raw_output = destination / f"rendered-{index}.png"
            if not raw_output.is_file():
                raise ProjectInitPdfRenderLimitError("PDF renderer did not produce every page")
            output = destination / f"page-{index:03d}.png"
            with Image.open(raw_output) as image:
                resized = _resize_to_limits(image)
                pixels = resized.width * resized.height
                total_pixels += pixels
                if total_pixels > MAX_TOTAL_RENDERED_PIXELS:
                    raise ProjectInitPdfRenderLimitError("PDF exceeds Vision total pixel limit")
                resized.save(output, format="PNG", optimize=True)
                resized.close()
            raw_output.unlink(missing_ok=True)
            rendered.append(output)
        return rendered
    except subprocess.TimeoutExpired as exc:
        raise ProjectInitPdfRenderLimitError("PDF rendering timed out") from exc
    except OSError as exc:
        raise ProjectInitPdfRenderLimitError("PDF cannot be rendered for Vision") from exc


def _resize_to_limits(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width < 1 or height < 1:
        raise ProjectInitPdfRenderLimitError("PDF page dimensions are invalid")
    scale = min(
        1.0,
        MAX_RENDERED_WIDTH / width,
        MAX_RENDERED_HEIGHT / height,
        (MAX_RENDERED_PIXELS / (width * height)) ** 0.5,
    )
    if scale >= 1.0:
        return image.copy()
    return image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))),
        Image.Resampling.LANCZOS,
    )
