from azure.storage.blob import BlobServiceClient

conn = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OiduX+d0/dY=;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
client = BlobServiceClient.from_connection_string(conn)

with open("test.pptx", "rb") as f:
    client.get_blob_client("raw-proposal", "test.pptx").upload_blob(f)