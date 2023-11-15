import os
import json
import config
import requests
import logging
from typing import Iterator
import sseclient
from urllib.parse import urlencode


os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}" # for audio


def read_txt_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content


def _audio_to_script(local_file_path):
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


def _img_or_doc_to_txt(local_file_path):
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
            return _audio_to_script(local_file)

    return _img_or_doc_to_txt(local_file)
