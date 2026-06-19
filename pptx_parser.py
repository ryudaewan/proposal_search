import io

from pptx import Presentation


def parse_slides(data: bytes) -> list[list[str]]:
    prs = Presentation(io.BytesIO(data))
    result = []
    for slide in prs.slides:
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        texts.append(text)
        result.append(texts)
    return result
