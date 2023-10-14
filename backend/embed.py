from embedchain import App
from embedchain.config import AppConfig,BaseLlmConfig
import os
from fastapi.responses import StreamingResponse
import json
import config
import requests
import logging
from typing import Iterator
import sseclient
from urllib.parse import urlencode


os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}"


def read_txt_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content


def audio_to_script(local_file_path):
    headers = {
        'Authorization': f'Bearer {os.environ["OPENAI_API_KEY"]}',
    }
    data = {
        'model': 'whisper-1',
    }
    files = {
        'file': open(local_file_path, 'rb'),
    }
    response = requests.post('https://api.openai.com/v1/audio/transcriptions', headers=headers, data=data, files=files)
    dict1 = response.json()
    return dict1['text']


def img_or_doc_to_txt(local_file_path):
    data = {
        'local_file': local_file_path,
    }
    headers = {'Content-Type': 'application/json', 'Accept': '*/*'}
    response = requests.post('http://localhost:5008/api8/parse_img_or_doc', data=json.dumps(data), headers = headers)
    local_txt_file = response.json()['local_txt_file']
    logging.info(f'local txt file = {local_txt_file}')
    text_file_contents = read_txt_file(local_txt_file)
    logging.info(f'txt.size={len(text_file_contents)}, txt content={text_file_contents[:1000]}')
    return text_file_contents


def pdf_to_txt_stream(local_file_path) -> Iterator[str]:
    params = {
        'local_file': local_file_path,
    }
    client = sseclient.SSEClient(f'http://localhost:5008/api8/parse_pdf_stream?{urlencode(params)}')
    for msg in client:
        if msg.data == "done":
            break
        yield msg.data


def notpdf_to_txt_content(file_ext, local_file):
    if file_ext == '.txt':
        return read_txt_file(local_file)
    
    audio_list = ['.mp3','.mp4','.m4a','.wav']
    for audio in audio_list:
        if local_file.endswith(audio):
            return audio_to_script(local_file)

    return img_or_doc_to_txt(local_file)


def embed_text(file_id, text_content):
    appConfig1 = AppConfig(log_level="DEBUG", id=file_id)
    app1  = App(appConfig1)
    app1.add(text_content, data_type = 'text')
    logging.info(f'embed_text done, file_id={file_id}, count={app1.count()}')


def ask_doc_generator(doc_id_list, query_str, full_txt):
    if (len(doc_id_list) == 1):
        where = {"app_id": doc_id_list[0]}
    else:
        cond_list = []
        for doc_id in doc_id_list:
            cond_list.append({"app_id": doc_id})
        where={"$or": cond_list}
    
    app2  = App(AppConfig(log_level="DEBUG"))
    response = app2.query(query_str, BaseLlmConfig(stream = True, number_documents=10),  dry_run=False, where=where, full_txt = full_txt)
    for s in response:
        logging.info(f's={s}')
        if s:
            yield str(s)


def ask_doc(file_id_list, query_str, full_txt):
    generator = ask_doc_generator(file_id_list, query_str, full_txt)
    return StreamingResponse(generator)