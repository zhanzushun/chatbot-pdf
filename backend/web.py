from fastapi import FastAPI, UploadFile, File, Request,BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
from typing import Dict
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import os

import embed
import config

import hashlib

def generate_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

app = FastAPI(timeout=600)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

STATIC_FOLDER_PATH = "/opt/disk2/github/embedchain/static/"
os.makedirs(STATIC_FOLDER_PATH, exist_ok=True)

app.mount("/api7/static", StaticFiles(directory=STATIC_FOLDER_PATH), name="static")

UPLOAD_LOCAL_FOLDER = STATIC_FOLDER_PATH + 'uploaded/'
os.makedirs(UPLOAD_LOCAL_FOLDER, exist_ok=True)

UPLOAD_URL_FOLDER = f'{config.UPLOAD_HOST_PORT}/api7/static/uploaded/'

# -------------files_db-----------------

files_db: Dict[str, Dict[str, str]] = {}

def save_to_file():
    with open("files_db.json", "w") as f:
        json.dump(files_db, f, indent=2)

scheduler = BackgroundScheduler()
scheduler.add_job(save_to_file, 'interval', minutes=2)
scheduler.start()

@app.on_event("startup")
async def load_db():
    global files_db
    try:
        with open("files_db.json", "r") as f:
            files_db = json.load(f)
    except FileNotFoundError:
        pass

# ---------------------------------------

import os
from datetime import datetime
from typing import List
from datetime import datetime
from pathlib import Path

from work import proxy_sync, proxy

def get_file_content(file_path):
    with open(file_path, "r") as f:
        return f.read()
    
def get_full_txt(file_id):
    file_url = files_db[str(file_id)]['url']
    local_file_path = file_url.replace(UPLOAD_URL_FOLDER, UPLOAD_LOCAL_FOLDER)
    file_ext = Path(local_file_path).suffix
    if (file_ext != '.txt'):
        local_file_path = os.path.join(os.path.dirname(local_file_path), 'tmp_files', f'{str(file_id)}{file_ext}.txt')
    logging.info(f'local txt file={local_file_path}')
    MAX_SIZE = 6000
    return get_file_content(local_file_path)[:MAX_SIZE]


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
        return await proxy(user_name + '.chat', query_str, 'gpt-3.5-turbo')

    prompt = """判断以下输入【问题】的类别，总共有两种类别，一种是【适合向量搜索的具体问题】，另一种是【不适合向量搜索且是概括总结类问题】请仔细分析进行判断。
你只需要输出最终答案，无需给出分析过程，最终答案采用json格式返回，格式为 {"类别":"适合向量搜索的具体问题"} 或者 {"类别":"不适合向量搜索且是概括总结类问题"}。【问题】如下: """
    prompt = prompt + query_str

    question_type = await proxy_sync(user_name + ".judge", prompt, 'gpt-4')
    logging.info(f'question_type={question_type}')

    ask_full_txt = False
    if ('适合向量搜索的具体问题' in question_type):
        logging.info('适合向量搜索的具体问题')
        file_id = file_id_list[0]
        full_txt = get_full_txt(file_id)
        try:
            return embed.ask_doc(file_id_list, query_str, full_txt)
        except Exception as e:
            if str(e) == 'no_query_result':
                ask_full_txt = True
    else:
        ask_full_txt = True

    if ask_full_txt:
        logging.info('概括总结类问题')
        file_id = file_id_list[0]
        full_txt = get_full_txt(file_id)
        query_txt = f"""基于文件/书/文章的内容回答【问题】，【文件/书/文章内容】如下:
{full_txt}

【问题】:
{query_str}
"""
        return await proxy(str(int(time.time())), query_txt, 'gpt-3.5-turbo-16k')



@app.post(f"/api7/chat2_private_use")
async def chat(request: Request):

    data = await request.body()
    data = json.loads(data)
    logging.info(data)

    prompt = data.get('prompt')
    user_name = data.get('user')

    return await proxy(user_name + '.chat', prompt, 'gpt-4')

# ----------------------------------------------------------


@app.post("/api7/getfiles")
async def read_files():
    return list(files_db.values())


@app.post("/api7/uploadfile")
async def create_upload_file(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    file = files[0]
    contents = await file.read()
    file_id = str(int(time.time()))
    current_month = datetime.now().strftime("%Y%m")
    file_name = file.filename
    file_ext = Path(file_name).suffix
    new_file_name = str(file_id) + file_ext

    file_url = f'{UPLOAD_URL_FOLDER}{current_month}/{new_file_name}'
    directory = f"{UPLOAD_LOCAL_FOLDER}{current_month}"
    os.makedirs(directory, exist_ok=True)
    
    local_file_path = f"{directory}/{new_file_name}"
    with open(local_file_path, "wb") as f:
        f.write(contents)

    file_md5 = generate_md5(local_file_path)
    for file1 in files_db:
        t = files_db[file1]
        if (t['file_md5'] == file_md5):
            return t
        
    background_tasks.add_task(process_file_task, file_id, file_md5, file_ext, file_name, new_file_name, file_url, local_file_path)
    return {"task_id": file_id}


def format_timestamp(file_id):
    return datetime.fromtimestamp(int(file_id)).strftime("%m/%d-%H:%M")


task_status = {}

def process_file_task(file_id, file_md5, file_ext, file_name, new_file_name, file_url, local_file_path):

    task_status[file_id] = 'processing'
    if (file_ext.lower() == '.pdf'):
        iter = embed.pdf_to_txt_stream(local_file_path)
        first = True
        pages = 0
        for msg in iter:
            logging.info(f'msg={msg}')
            if first and msg:
                first = False
                pages = msg.split(',')[0]
                local_txt_file = msg.split(',')[1]
                task_status[file_id] = f"总页数: {pages}, 解析第1页文本"
            else:
                task_status[file_id] = f'共{pages}页,已解析{msg}/{pages}'
        txt_content = embed.read_txt_file(local_txt_file)
    else:
        task_status[file_id] = '解析文本中'
        txt_content = embed.notpdf_to_txt_content(file_ext, local_file_path)

    task_status[file_id] = '训练内容中'
    embed.embed_text(file_id, txt_content)

    files_db[file_id] = {
        "filename": file_name,
        "newfilename": new_file_name,
        "file_id": file_id,
        "file_md5": file_md5,
        "selected": False,
        "uploadtime": format_timestamp(file_id),
        'url': file_url,
    }
    task_status[file_id] = "完成"
    logging.info(f'process file done, id={file_id}')


@app.get("/api7/status/{file_id}")
async def get_task_status(file_id: str):
    def event_stream():
        prev_status = None
        if file_id not in task_status:
            logging.error(f'file_id={file_id} not in task_status, force closing')
            yield f"data: done\n\n"
            return
        
        while task_status.get(str(file_id)) != "完成":
            status = task_status.get(str(file_id))
            if (status != prev_status):
                logging.info(f'file_id={file_id}, status={status}')
                yield f"data: {status}\n\n"
                prev_status = status
            time.sleep(1)

        yield f"data: done\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
