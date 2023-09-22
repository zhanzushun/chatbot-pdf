from embedchain import App
from embedchain.config import AppConfig,QueryConfig
import os
from fastapi.responses import StreamingResponse
import json
import config

os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}"
import logging

def read_txt_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def embed_file(file_id, file_url, file_name, is_local):
    appConfig1 = AppConfig(log_level="DEBUG", id=file_id)
    app1  = App(appConfig1)
    audio_list = ['.mp3','.mp4','.m4a','.wav']
    if file_url.endswith('.txt') and is_local:
        app1.add_local('text', read_txt_file(file_url))
    elif file_url.endswith('.pdf'):
        logging.info(f'embed pdf file={file_url}')
        app1.add_local('text', pdf_to_txt(file_url))
        # app1.add('pdf_file', file_url)
    elif file_url.endswith('.docx') or file_url.endswith('.doc'):
        logging.info(f'embed docx file={file_url}')
        app1.add_local('text', pdf_to_txt(file_url))
        # app1.add('docx', file_url)
    else:
        fnd = False
        for audio in audio_list:
            if file_url.endswith(audio):
                app1.add_local('text', audio_to_script(file_url))
                fnd = True
                break
        if not fnd:
            logging.info(f'unknown file format ={file_url}')
            return
        
    logging.info(f'embed-ed {file_name}.token={app1.count()}')

def ask_doc_generator(file_id_list, query_str):
    app2  = App(AppConfig(log_level="DEBUG"))
    query_config = QueryConfig(stream = True, number_documents=10, doc_id_list=file_id_list)
    response = app2.query(query_str, query_config,  dry_run=False)
    for s in response:
        print(s)
        yield s

def ask_doc(file_id_list, query_str):
    generator = ask_doc_generator(file_id_list, query_str)
    return StreamingResponse(generator)

import requests

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

def pdf_to_txt(local_file_path):
    data = {
        'local_file': local_file_path,
    }
    response = requests.post('http://localhost:8002/parse_pdf', data=json.dumps(data), headers = {'Content-Type': 'application/json', 'Accept': '*/*'})
    txt = response.text
    logging.info(f'pdf_to_txt, txt={txt[:1000]}, txt.size={len(txt)}')
    return txt
