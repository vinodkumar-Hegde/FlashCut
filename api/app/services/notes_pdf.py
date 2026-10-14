import html
import math
import re
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage

from reportlab.graphics.shapes import (
    Drawing,
    Line,
    Polygon,
    Rect,
    String,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.lib.utils import (
    ImageReader,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


LOGO_PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    / "assets"
    / "doctutorials-logo.png"
)

REGULAR_FONT = (
    "/usr/share/fonts/truetype/"
    "dejavu/DejaVuSans.ttf"
)

BOLD_FONT = (
    "/usr/share/fonts/truetype/"
    "dejavu/DejaVuSans-Bold.ttf"
)


def register_fonts():
    pdfmetrics.registerFont(
        TTFont(
            "FlashCut",
            REGULAR_FONT,
        )
    )

    pdfmetrics.registerFont(
        TTFont(
            "FlashCut-Bold",
            BOLD_FONT,
        )
    )


def safe_text(
    value,
) -> str:
    return html.escape(
        str(value or "")
    )


def wrapped_lines(
    text: str,
    *,
    width: int = 22,
    maximum: int = 3,
) -> list[str]:
    words = str(
        text or ""
    ).split()

    result = []
    line = ""

    for word in words:
        candidate = (
            f"{line} {word}".strip()
        )

        if (
            len(candidate) <= width
            or not line
        ):
            line = candidate
            continue

        result.append(line)
        line = word

        if len(result) >= maximum:
            break

    if (
        line
        and len(result) < maximum
    ):
        result.append(line)

    return result[:maximum]


def draw_label(
    drawing,
    *,
    text,
    x,
    y,
    width=22,
    size=8,
    color=colors.HexColor(
        "#172033"
    ),
):
    lines = wrapped_lines(
        text,
        width=width,
    )

    offset = (
        (len(lines) - 1)
        * 5
    )

    for index, line in enumerate(
        lines
    ):
        drawing.add(
            String(
                x,
                y
                + offset
                - index * 10,
                line,
                fontName="FlashCut",
                fontSize=size,
                fillColor=color,
                textAnchor="middle",
            )
        )


def flowchart_drawing(
    visual: dict,
):
    nodes = (
        visual.get(
            "nodes",
            [],
        )
        or []
    )[:10]

    width = 480
    box_width = 310
    box_height = 42
    gap = 26

    height = max(
        100,
        len(nodes)
        * (
            box_height
            + gap
        )
        + 20,
    )

    drawing = Drawing(
        width,
        height,
    )

    positions = {}

    x = (
        width
        - box_width
    ) / 2

    for index, node in enumerate(
        nodes
    ):
        y = (
            height
            - 20
            - box_height
            - index
            * (
                box_height
                + gap
            )
        )

        positions[
            node["id"]
        ] = (
            x
            + box_width / 2,
            y
            + box_height / 2,
        )

        drawing.add(
            Rect(
                x,
                y,
                box_width,
                box_height,
                rx=8,
                ry=8,
                fillColor=colors.HexColor(
                    "#EFF6FF"
                ),
                strokeColor=colors.HexColor(
                    "#4A90D9"
                ),
                strokeWidth=1,
            )
        )

        draw_label(
            drawing,
            text=node.get(
                "label",
                "",
            ),
            x=x
            + box_width / 2,
            y=y
            + box_height / 2
            - 3,
            width=48,
            size=8.5,
        )

    node_index = {
        node["id"]: index
        for index, node
        in enumerate(nodes)
    }

    edges = (
        visual.get(
            "edges",
            [],
        )
        or []
    )

    for edge in edges:
        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        if (
            source not in node_index
            or target not in node_index
        ):
            continue

        sx, sy = positions[source]
        tx, ty = positions[target]

        start_y = (
            sy
            - box_height / 2
        )

        end_y = (
            ty
            + box_height / 2
        )

        drawing.add(
            Line(
                sx,
                start_y,
                tx,
                end_y,
                strokeColor=colors.HexColor(
                    "#70839B"
                ),
                strokeWidth=1.2,
            )
        )

        drawing.add(
            Polygon(
                [
                    tx - 3,
                    end_y + 6,

                    tx + 3,
                    end_y + 6,

                    tx,
                    end_y,
                ],
                fillColor=colors.HexColor(
                    "#70839B"
                ),
                strokeColor=colors.HexColor(
                    "#70839B"
                ),
            )
        )

    return drawing


def mindmap_drawing(
    visual: dict,
):
    nodes = (
        visual.get(
            "nodes",
            [],
        )
        or []
    )[:9]

    width = 480
    height = 340

    drawing = Drawing(
        width,
        height,
    )

    if not nodes:
        return drawing

    root_id = visual.get(
        "root_id"
    )

    by_id = {
        node["id"]: node
        for node in nodes
    }

    if root_id not in by_id:
        root_id = nodes[0]["id"]

    center_x = width / 2
    center_y = height / 2

    positions = {
        root_id: (
            center_x,
            center_y,
        )
    }

    others = [
        node
        for node in nodes
        if node["id"]
        != root_id
    ]

    radius_x = 175
    radius_y = 120

    for index, node in enumerate(
        others
    ):
        angle = (
            2
            * math.pi
            * index
            / max(
                1,
                len(others),
            )
        )

        positions[
            node["id"]
        ] = (
            center_x
            + radius_x
            * math.cos(angle),

            center_y
            + radius_y
            * math.sin(angle),
        )

    for edge in (
        visual.get(
            "edges",
            [],
        )
        or []
    ):
        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        if (
            source not in positions
            or target not in positions
        ):
            continue

        sx, sy = positions[source]
        tx, ty = positions[target]

        drawing.add(
            Line(
                sx,
                sy,
                tx,
                ty,
                strokeColor=colors.HexColor(
                    "#91A4BA"
                ),
                strokeWidth=1.2,
            )
        )

    for node in nodes:
        node_id = node["id"]
        x, y = positions[
            node_id
        ]

        is_root = (
            node_id == root_id
        )

        box_width = (
            130
            if is_root
            else 110
        )

        box_height = (
            54
            if is_root
            else 44
        )

        drawing.add(
            Rect(
                x
                - box_width / 2,
                y
                - box_height / 2,
                box_width,
                box_height,
                rx=8,
                ry=8,
                fillColor=(
                    colors.HexColor(
                        "#DDEBFF"
                    )
                    if is_root
                    else colors.HexColor(
                        "#F4F8FD"
                    )
                ),
                strokeColor=colors.HexColor(
                    "#4387CE"
                ),
                strokeWidth=(
                    1.4
                    if is_root
                    else 1
                ),
            )
        )

        draw_label(
            drawing,
            text=node.get(
                "label",
                "",
            ),
            x=x,
            y=y - 3,
            width=(
                20
                if is_root
                else 16
            ),
            size=(
                8.5
                if is_root
                else 7.5
            ),
        )

    return drawing


def watermark_reader():
    if not LOGO_PATH.exists():
        return None

    image = PILImage.open(
        LOGO_PATH
    ).convert("RGBA")

    alpha = image.getchannel(
        "A"
    ).point(
        lambda value:
            int(
                value * 0.055
            )
    )

    image.putalpha(alpha)

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    buffer.seek(0)

    return (
        ImageReader(buffer),
        buffer,
    )


def render_notes_pdf(
    *,
    content: dict,
    visuals: list[dict],
    style: str,
) -> bytes:
    register_fonts()

    output = BytesIO()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "FlashCutTitle",
        parent=styles["Title"],
        fontName="FlashCut-Bold",
        fontSize=22,
        leading=27,
        textColor=colors.HexColor(
            "#15234A"
        ),
        spaceAfter=8,
    )

    heading_style = ParagraphStyle(
        "FlashCutHeading",
        parent=styles[
            "Heading2"
        ],
        fontName="FlashCut-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor(
            "#15234A"
        ),
        spaceBefore=12,
        spaceAfter=7,
    )

    body_style = ParagraphStyle(
        "FlashCutBody",
        parent=styles["BodyText"],
        fontName="FlashCut",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor(
            "#2B3548"
        ),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "FlashCutBullet",
        parent=body_style,
        leftIndent=13,
        firstLineIndent=-9,
        spaceAfter=5,
    )

    watermark = watermark_reader()

    def page(canvas, doc):
        canvas.saveState()

        if watermark:
            reader, _buffer = watermark

            size = 92 * mm

            canvas.drawImage(
                reader,
                (
                    A4[0]
                    - size
                )
                / 2,
                (
                    A4[1]
                    - size
                )
                / 2,
                width=size,
                height=size,
                mask="auto",
                preserveAspectRatio=True,
            )

        canvas.setFont(
            "FlashCut",
            7,
        )

        canvas.setFillColor(
            colors.HexColor(
                "#7A8494"
            )
        )

        canvas.drawCentredString(
            A4[0] / 2,
            10 * mm,
            (
                "DT-FlashCut Notes"
                f" | Page {doc.page}"
            ),
        )

        canvas.restoreState()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=str(
            content.get(
                "title",
                "Video Notes",
            )
        ),
        author="DT-FlashCut",
    )

    story = []

    if LOGO_PATH.exists():
        logo = Image(
            str(LOGO_PATH),
            width=28 * mm,
            height=28 * mm,
        )

        story.append(logo)
        story.append(
            Spacer(
                1,
                3 * mm,
            )
        )

    story.append(
        Paragraph(
            safe_text(
                content.get(
                    "title",
                    "Video Notes",
                )
            ),
            title_style,
        )
    )

    story.append(
        Paragraph(
            (
                f"Automatic {safe_text(style)} "
                "notes generated from the "
                "video transcript."
            ),
            body_style,
        )
    )

    overview = str(
        content.get(
            "overview",
            "",
        )
    ).strip()

    if overview:
        story.append(
            Spacer(
                1,
                2 * mm,
            )
        )

        story.append(
            Paragraph(
                safe_text(
                    overview
                ),
                body_style,
            )
        )

    for section in (
        content.get(
            "sections",
            [],
        )
        or []
    ):
        story.append(
            Paragraph(
                safe_text(
                    section.get(
                        "heading",
                        "",
                    )
                ),
                heading_style,
            )
        )

        for bullet in (
            section.get(
                "bullets",
                [],
            )
            or []
        ):
            story.append(
                Paragraph(
                    (
                        "&bull; "
                        + safe_text(
                            bullet.get(
                                "text",
                                "",
                            )
                        )
                    ),
                    bullet_style,
                )
            )

    takeaways = (
        content.get(
            "key_takeaways",
            [],
        )
        or []
    )

    if takeaways:
        story.append(
            Paragraph(
                "Key takeaways",
                heading_style,
            )
        )

        for bullet in takeaways:
            story.append(
                Paragraph(
                    (
                        "&bull; "
                        + safe_text(
                            bullet.get(
                                "text",
                                "",
                            )
                        )
                    ),
                    bullet_style,
                )
            )

    for visual in visuals or []:
        kind = visual.get(
            "kind"
        )

        story.append(
            Spacer(
                1,
                5 * mm,
            )
        )

        story.append(
            Paragraph(
                safe_text(
                    visual.get(
                        "title",
                        (
                            "Mind Map"
                            if kind
                            == "mindmap"
                            else "Flowchart"
                        ),
                    )
                ),
                heading_style,
            )
        )

        if kind == "mindmap":
            story.append(
                mindmap_drawing(
                    visual
                )
            )

        elif kind == "flowchart":
            story.append(
                flowchart_drawing(
                    visual
                )
            )

    document.build(
        story,
        onFirstPage=page,
        onLaterPages=page,
    )

    return output.getvalue()


def safe_pdf_name(
    value: str,
) -> str:
    stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        str(value or "notes"),
    ).strip("-._")

    return (
        stem
        or "notes"
    )
