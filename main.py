from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import requests
import zipfile
import tempfile
import shutil
import threading
import os
import uuid

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# session_id -> temp_dir, files
sessions = {}


@app.get("/")
def home():
    return {"status": "ok"}


def cleanup(session_id: str):
    session = sessions.pop(session_id, None)

    if session:
        shutil.rmtree(session["dir"], ignore_errors=True)
        print(f"Удалена сессия {session_id}")


def send_file(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return StreamingResponse(
            open(file_path, "rb"),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline"
            }
        )

    media_types = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".html": "text/html",
        ".htm": "text/html",
        ".xml": "application/xml"
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(ext, "application/octet-stream")
    )


@app.get("/view/{file_id}")
def prepare(request: Request, file_id: str):

    session_id = str(uuid.uuid4())

    temp_dir = os.path.join(
        tempfile.gettempdir(),
        "msfo",
        session_id
    )

    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, "report.zip")

    url = f"https://www.e-disclosure.ru/portal/FileLoad.ashx?Fileid={file_id}"

    r = requests.get(url, timeout=120)

    if r.status_code != 200:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(404, "Файл не найден")

    with open(zip_path, "wb") as f:
        f.write(r.content)

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(500, "Получен не ZIP")

    files = []

    priority = (
        ".pdf",
        ".xlsx",
        ".xls",
        ".html",
        ".htm",
        ".xml",
    )

    for root, _, filenames in os.walk(temp_dir):
        for filename in filenames:

            if filename == "report.zip":
                continue

            ext = os.path.splitext(filename)[1].lower()

            if ext in priority:
                files.append({
                    "name": filename,
                    "path": os.path.join(root, filename)
                })

    if not files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(404, "Подходящих файлов не найдено")

    files.sort(
        key=lambda f: priority.index(
            os.path.splitext(f["name"])[1].lower()
        )
    )

    sessions[session_id] = {
        "dir": temp_dir,
        "files": files
    }

    threading.Timer(
        600,
        cleanup,
        args=[session_id]
    ).start()

    return templates.TemplateResponse(
    request=request,
    name="viewer.html",
    context={
        "session": session_id,
        "files": [
            {
                "id": i,
                "name": f["name"]
            }
            for i, f in enumerate(files)
        ],
        "default_file": 0
    }
)


@app.get("/open/{session_id}/{file_index}")
def open_file(session_id: str, file_index: int):

    if session_id not in sessions:
        raise HTTPException(404, "Сессия истекла")

    files = sessions[session_id]["files"]

    if file_index < 0 or file_index >= len(files):
        raise HTTPException(404, "Файл не найден")

    return send_file(files[file_index]["path"])
