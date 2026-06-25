from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import requests

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}

@app.get("/view/{file_id}")
def view_pdf(file_id: str):
    url = f"https://www.e-disclosure.ru/portal/FileLoad.ashx?Fileid={file_id}"

    r = requests.get(
        url,
        stream=True,
        timeout=60
    )

    if r.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline"
        }
    )