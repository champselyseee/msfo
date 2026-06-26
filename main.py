from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import requests
import zipfile
import tempfile
import shutil
import threading
import os
import uuid

app = FastAPI()


@app.get("/")
def home():
    return {"status": "ok"}


def cleanup(path: str):
    try:
        shutil.rmtree(path, ignore_errors=True)
        print(f"Удалена временная папка {path}")
    except Exception as e:
        print(e)


@app.get("/view/{file_id}")
def view_file(file_id: str):

    # создаем временную папку
    temp_dir = os.path.join(tempfile.gettempdir(), "msfo", str(uuid.uuid4()))
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, "report.zip")

    url = f"https://www.e-disclosure.ru/portal/FileLoad.ashx?Fileid={file_id}"

    # скачиваем архив
    r = requests.get(url, timeout=120)

    if r.status_code != 200:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=404, detail="Файл не найден")

    with open(zip_path, "wb") as f:
        f.write(r.content)

    # распаковываем
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Получен не ZIP")

    # ищем нужный файл
    target = None

    priority = [
        ".html",
        ".htm",
        ".pdf",
        ".xlsx",
        ".xls",
        ".xml"
    ]

    for ext in priority:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(ext):
                    target = os.path.join(root, file)
                    break
            if target:
                break
        if target:
            break

    if not target:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=404, detail="В архиве нет подходящего файла")

    # удалить папку через 10 минут
    threading.Timer(600, cleanup, args=[temp_dir]).start()

    return FileResponse(
        target,
        filename=os.path.basename(target)
    )
