import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from indexer import index_slides, search_proposals
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


@app.route(route="search", methods=["GET", "POST"])
def search(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "GET":
        query = req.params.get("q", "").strip()
        top = req.params.get("top", "5")
    else:
        try:
            body = req.get_json()
        except ValueError:
            return _error("요청 본문이 올바른 JSON이 아닙니다.", 400)
        query = body.get("query", "").strip()
        top = str(body.get("top", 5))

    if not query:
        return _error("query가 필요합니다. GET: ?q=..., POST: {\"query\": \"...\"}", 400)

    try:
        top = int(top)

        if top < 1 or top > 50:
            raise ValueError
        
    except ValueError:
        return _error("top은 1 이상 50 이하의 정수여야 합니다.", 400)

    results = search_proposals(query, top=top)
    
    return func.HttpResponse(
        json.dumps({"query": query, "count": len(results), "results": results}, ensure_ascii=False),
        mimetype="application/json",
    )


def _error(message: str, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": message}, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
    )
