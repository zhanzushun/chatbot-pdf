from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
from typing import Dict
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import os

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

# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

from fastapi.staticfiles import StaticFiles

STATIC_FOLDER_PATH = config.STATIC_DIR
os.makedirs(STATIC_FOLDER_PATH, exist_ok=True)

app.mount("/api7/static", StaticFiles(directory=STATIC_FOLDER_PATH), name="static")

UPLOAD_LOCAL_FOLDER = STATIC_FOLDER_PATH + 'uploaded/'
os.makedirs(UPLOAD_LOCAL_FOLDER, exist_ok=True)

UPLOAD_URL_FOLDER = f'{config.UPLOAD_HOST_PORT}/api7/static/uploaded/'

# -------------files_db-----------------

files_db: Dict[str, Dict[str, str]] = {}

def save_to_file():
    with open(config.APP_NAME + "_files_db.json", "w") as f:
        json.dump(files_db, f, indent=2)

scheduler = BackgroundScheduler()
scheduler.add_job(save_to_file, 'interval', minutes=2)
scheduler.start()

@app.on_event("startup")
async def load_db():
    global files_db
    try:
        with open(config.APP_NAME + "_files_db.json", "r") as f:
            files_db = json.load(f)
    except FileNotFoundError:
        pass

# ---------------------------------------

import os
from datetime import datetime
from typing import List
from datetime import datetime
from pathlib import Path

import openai_proxy
import convert_to_txt
import embedchain_util


def get_full_txt(file_id):
    file_url = files_db[str(file_id)]['url']
    local_file_path = file_url.replace(UPLOAD_URL_FOLDER, UPLOAD_LOCAL_FOLDER)
    full_txt = _get_full_txt(file_id, local_file_path)
    MAX_SIZE = 6000
    return full_txt[:MAX_SIZE]


def _get_full_txt(file_id, local_file_path):
    file_ext = Path(local_file_path).suffix
    if (file_ext != '.txt'):
        local_file_path = os.path.join(os.path.dirname(local_file_path), 'tmp_files', f'{str(file_id)}{file_ext}.txt')
    logging.info(f'local txt file={local_file_path}')
    return convert_to_txt.read_txt_file(local_file_path)


import re
import json
from typing import List, Union

def extract_json(s: str) -> Union[dict, None]:
    # 正则表达式匹配最外层的大括号包围的内容，即JSON对象
    matches = re.findall(r'{.*?}', s, re.DOTALL)
    if matches:
        # 假设最后一个匹配项是我们需要的JSON对象
        json_str = matches[-1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            print("Found JSON is not valid.")
    return None

def parse_pages_from_json(json_obj: dict) -> List[int]:
    if "pages" in json_obj and isinstance(json_obj["pages"], list):
        return json_obj["pages"]
    return []


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
        return await openai_proxy.proxy(user_name + '.chat', query_str, 'gpt-3.5-turbo')

    prompt = """判断以下输入【问题】的类别，总共有三种类别: 
    1.【适合向量搜索的具体问题】
    2.【指定页面问题】
    3.【未指定任何具体信息的全文总结类问题】
    问题中出现指定页面，则属于【指定页面问题】
    问题中出现具体的任何名词、实体、具体段落、具体标题都属于【适合向量搜索的具体问题】

你只需要输出最终答案，无需给出分析过程，最终答案采用json格式返回，格式为
{"类别":"适合向量搜索的具体问题"}
或者 {"类别":"未指定任何具体信息的全文总结类问题"}
或者 {"类别":"指定页面问题", "pages":[17,23]}

举例:
    '详细总结关于 inequality and economics 的观点', 返回json: {"类别":"适合向量搜索的具体问题"}
    '基于命名实体识别构建内容摘要', 返回json: {"类别":"未指定任何具体信息的全文总结类问题"}
    '总结第17页到第18页 What Caused Elite Polarization? 下的7个观点', 返回json: {"类别":"指定页面问题", "pages": [17,18]}

【问题】如下: """
    prompt = prompt + query_str

    try:
        question_type = await openai_proxy.proxy_sync(user_name + ".judge", prompt, 'gpt-4')
        logging.info(f'question_type={question_type}')
    except Exception as e:
        return f'Exception: {e}'

    ask_full_txt = False
    file_id = file_id_list[0]

    try:
        if ('适合向量搜索的具体问题' in question_type):
            logging.info('适合向量搜索的具体问题')
            return await embedchain_util.ask_doc(user_name + '.ask_doc', file_id_list, query_str)
        
        elif ('指定页面问题' in question_type):
            json_obj = extract_json(question_type)
            page_number_list = parse_pages_from_json(json_obj)
            return await embedchain_util.ask_doc_context(user_name + '.ask_doc', 
                embedchain_util.get_context_list(file_id, page_number_list), query_str)
        else:
            logging.info('概括总结类问题')
        
    except Exception as e:
        if str(e) == 'no_query_result':
            logging.error('no_query_result')
            logging.info('未找到答案，则发送全文')
        else:
            logging.error(str(e))
            return {"code": 500, "msg": str(e)}
    
    # 最后全文提问
    full_txt = get_full_txt(file_id)
    query_txt = f"""基于文件/书/文章的内容回答【问题】，【文件/书/文章内容】如下:
{full_txt}

请基于以上【文件/书/文章内容】，回答下面的【问题】

【问题】:
{query_str}
"""
    return await openai_proxy.proxy(str(int(time.time())), query_txt, 'gpt-3.5-turbo')



@app.post(f"/api7/chat2_private_use")
async def chat(request: Request):

    data = await request.body()
    data = json.loads(data)
    logging.info(data)

    prompt = data.get('prompt')
    user_name = data.get('user')

    return await openai_proxy.proxy(user_name + '.chat', prompt, 'gpt-4')

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


@app.post("/api7/embed_local_pdf")
async def embed_local_pdf(background_tasks: BackgroundTasks, 
                          file_name:str = Body(...), current_month:str = Body(...), file_id: str = Body(...)):
    file_ext = '.pdf'
    new_file_name = str(file_id) + file_ext

    file_url = f'{UPLOAD_URL_FOLDER}{current_month}/{new_file_name}'
    directory = f"{UPLOAD_LOCAL_FOLDER}{current_month}"
    os.makedirs(directory, exist_ok=True)
    local_file_path = f"{directory}/{new_file_name}"
    file_md5 = generate_md5(local_file_path)
    txt_content = _get_full_txt(file_id, local_file_path)

    background_tasks.add_task(process_file_task, file_id, file_md5, file_ext, file_name, new_file_name, file_url, local_file_path, txt_content)
    return {"task_id": file_id}


def format_timestamp(file_id):
    return datetime.fromtimestamp(int(file_id)).strftime("%m/%d-%H:%M")


task_status = {}

def process_file_task(file_id, file_md5, file_ext, file_name, new_file_name, file_url, local_file_path, txt_content = None):

    task_status[file_id] = 'processing'
    if txt_content is None:
        if (file_ext.lower() == '.pdf'):
            iter = convert_to_txt.pdf_to_txt_stream(local_file_path)
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
            txt_content = convert_to_txt.read_txt_file(local_txt_file)
        else:
            task_status[file_id] = '解析文本中'
            txt_content = convert_to_txt.notpdf_to_txt_content(file_ext, local_file_path)

    task_status[file_id] = '训练内容中'
    embedchain_util.embed_doc(file_id, txt_content)

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
