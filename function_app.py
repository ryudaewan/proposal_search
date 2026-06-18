import azure.functions as func
import logging

app = func.FunctionApp()

@app.blob_trigger(arg_name="pptx", path="raw-proposal/{name}", connection="PptxRepoConnection", source="EventGrid")
def blob_trigger(pptx: func.InputStream):
    logging.info(f"Blob trigger: name={pptx.name}, size={pptx.length} bytes")
