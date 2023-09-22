from fastapi import FastAPI, UploadFile, File, Request
from typing import Dict
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import os

import embed
import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

app = FastAPI(timeout=600)

# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

from fastapi.staticfiles import StaticFiles

STATIC_FOLDER_PATH = "/opt/disk2/github/embedchain/static/"
os.makedirs(STATIC_FOLDER_PATH, exist_ok=True)

app.mount("/api7/static", StaticFiles(directory=STATIC_FOLDER_PATH), name="static")

UPLOAD_LOCAL_FOLDER = STATIC_FOLDER_PATH + 'uploaded/'
os.makedirs(UPLOAD_LOCAL_FOLDER, exist_ok=True)

UPLOAD_URL_FOLDER = f'{config.UPLOAD_HOST_PORT}/api7/static/uploaded/'

# Our "database" of files
files_db: Dict[str, Dict[str, str]] = {}

def save_to_file():
    with open("files_db.json", "w") as f:
        json.dump(files_db, f)

# Schedule the function to be called every 2 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(save_to_file, 'interval', minutes=2)
scheduler.start()

# Load the database from file at startup
@app.on_event("startup")
async def load_db():
    global files_db
    try:
        with open("files_db.json", "r") as f:
            files_db = json.load(f)
    except FileNotFoundError:
        pass  # It's okay if the file doesn't exist yet

import os
from datetime import datetime

@app.post("/api7/getfiles")
async def read_files():
    return list(files_db.values())

from typing import List
from datetime import datetime
from pathlib import Path

def format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y.%m.%d")


@app.post("/api7/uploadfile")
async def create_upload_file(files: List[UploadFile] = File(...)):
    timestamps = []
    cnt = 0
    for file in files:
        cnt += 1
        contents = await file.read()
        timestamp = int(time.time()) + cnt
        current_month = datetime.now().strftime("%Y%m")
        file_ext = Path(file.filename).suffix
        new_file_name = str(timestamp) + file_ext

        file_url = f'{UPLOAD_URL_FOLDER}{current_month}/{new_file_name}'

        files_db[str(timestamp)] = {
            "filename": file.filename,
            "newfilename": new_file_name,
            "timestamp": timestamp,
            "selected": False,
            "uploadtime": format_timestamp(timestamp),
            'url': file_url,
        }
        
        # Save the file to disk
        directory = f"{UPLOAD_LOCAL_FOLDER}{current_month}"
        os.makedirs(directory, exist_ok=True)
        local_file_path = f"{directory}/{new_file_name}"
        with open(local_file_path, "wb") as f:
            f.write(contents)
        
        timestamps.append(timestamp)
        embed.embed_file(str(timestamp), local_file_path, file.filename, True)

    return {"filenames": [file.filename for file in files], "timestamps": timestamps}

from work import proxy_sync, proxy

def get_file_content(file_path):
    with open(file_path, "r") as f:
        return f.read()

@app.post("/api7/askdoc")
async def ask_doc(request: Request):
    data = await request.body()
    data = json.loads(data)
    logging.info(data)
    file_id_list = data.get('file_id_list')
    query_str = data.get('query')
    user_name = data.get('user')

    if (file_id_list is None) or len(file_id_list) == 0:
        logging.info('未选择文件，转发到普通对话')
        return await proxy(user_name, query_str, 'gpt-3.5-turbo')

    prompt = """判断以下输入【问题】的类别，总共有两种类别，一种是【做总结】，另一种是【普通问答】，
只有明显中文或英文提到“总结”“小结”时才是【做总结】，如“业务回顾”属于普通问答。你只需要输出最终答案，无需给出分析过程，最终答案采用json格式返回，
格式为 {"类别":"做总结"} 或者 {"类别":"普通问答"}，【问题】如下【问题】如下:"""

    prompt = prompt + query_str
    question_type = await proxy_sync(user_name, prompt, 'gpt-4')
    logging.info(f'question_type={question_type}')
    if ('做总结' in question_type):
        logging.info('问题是总结类')
        file_id = file_id_list[0]
        file_url = files_db[str(file_id)]['url']
        local_file_path = file_url.replace(UPLOAD_URL_FOLDER, UPLOAD_LOCAL_FOLDER)
        file_ext = Path(local_file_path).suffix
        if (file_ext != '.txt'):
            local_file_path = os.path.join(os.path.dirname(local_file_path), 'tmp_files', f'{str(file_id)}{file_ext}.txt')
        logging.info(f'local txt file={local_file_path}')
        MAX_SIZE = 6000
        content = get_file_content(local_file_path)[:MAX_SIZE]
        query_txt = f"""基于文件的内容回答【问题】，【文件内容】如下:
{content}

【问题】:
{query_str}
"""
        logging.info(f'发送整个文章做总结')
        return await proxy(str(int(time.time())), query_txt, 'gpt-3.5-turbo-16k')
    else:
        logging.info('问题是文档问答类型')
        return embed.ask_doc(file_id_list, query_str)

@app.post("/api7/embed")
async def embed_file(request: Request):
    data = await request.body()
    data = json.loads(data)
    logging.info(data)

    file_id = data.get('file_id')
    file_url = data.get('file_url')
    return embed.embed_file(file_id, file_url, 'temp', True)


from work import proxy
@app.post(f"/api7/chat2_private_use")
async def chat(request: Request):

    data = await request.body()
    data = json.loads(data)
    logging.info(data)

    prompt = data.get('prompt')
    user_name = data.get('user')

    return await proxy(user_name, prompt, 'gpt-4')




