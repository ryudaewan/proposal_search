import logging
from datetime import datetime, timezone

import azure.functions as func

from indexer import index_slides
from pptx_parser import parse_slides

app = func.FunctionApp()


@app.blob_trigger(
    arg_name="pptx",
    path="raw-proposal/{name}",
    connection="PptxRepoConnection",
    source="EventGrid"
)
def blob_trigger(pptx: func.InputStream):
    logging.info(f"Blob trigger: name={pptx.name}, size={pptx.length} bytes")

    blob_name = pptx.name.split("/")[-1]
    slides = parse_slides(pptx.read())

    title = slides[0][0] if slides and slides[0] else blob_name
    uploaded_at = datetime.now(timezone.utc).isoformat()

    count = index_slides(blob_name, title, uploaded_at, slides)
    logging.info(f"Indexed {count} slides from {blob_name}")
