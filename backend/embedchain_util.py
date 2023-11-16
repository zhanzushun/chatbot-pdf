import os
import logging
import uuid
from typing import List

from langchain.docstore.document import Document
from ChineseRecursiveTextSplitter import ChineseRecursiveTextSplitter
from ChromaDB import ChromaDB
import ChromaEmbed

import config

os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}"

g_db = ChromaDB(config.APP_NAME + "_db", config.APP_NAME + "_db")


import re
index_number_pattern = re.compile(r'^\d+')
http_pattern = re.compile(r'http')

def is_index_page(page_text, number_threshold=0.35, http_cnt_threshold=5):
    lines = page_text.strip().split('\n')

    number_lines = sum(bool(index_number_pattern.search(line)) for line in lines)
    http_cnt = page_text.count('http')
    logging.info(f'is_index_page, lines={len(lines)}, number_lines={number_lines}, http_lines={http_cnt}')

    number_ratio = number_lines / len(lines)
    if (number_ratio >= number_threshold and http_cnt >= http_cnt_threshold):
        return True
    return False

def _save_page(file_id, page_index, page_text):
    os.makedirs(config.STATIC_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.STATIC_DIR, file_id), exist_ok=True)
    with open(os.path.join(config.STATIC_DIR, file_id, str(page_index) + '.txt'), 'w') as f:
        f.write(page_text)


def _load_page(file_id, page_index):
    f1 = os.path.join(config.STATIC_DIR, file_id, str(page_index) + '.txt')
    if os.path.exists(f1):
        with open(f1, 'r') as f:
            return f.read()
    else:
        logging.info(f'page not exist, file={f1}')
    return None


def _embed_one_page(file_id, text_page, page_index_key):
    text_splitter = ChineseRecursiveTextSplitter(
        chunk_size=150,
        chunk_overlap=0,
        length_function=len,
    )

    _1,_2,_3,_4 = ChromaEmbed.load_and_embed(g_db, text_splitter, text_page, file_id,
        {'file_id': file_id, 'page_index': page_index_key})
    
    for i,doc in enumerate(_1):
        logging.info(f'page_key={page_index_key}, doc=[{i}/{len(_1)}], doc.chars={len(doc)}, doc.content={doc}')
    logging.info(f'end page_key={page_index_key}, app.db.cnt={g_db.count()}')


def embed_doc(file_id, txt_content):
    text_pages = txt_content.split('<|startofpage|>')

    if len(text_pages) == 1: 
        # 未分页的文章, 按大段分页
        parent_splitter = ChineseRecursiveTextSplitter(chunk_size=1000)
        documents = parent_splitter.split_text(txt_content)
        logging.info(f'file is split to size={len(documents)}')
        for _i, _doc in enumerate(documents):
            page_index_key = f'{_i}_{str(uuid.uuid4())}'
            _save_page(file_id, page_index_key, _doc)
            _embed_one_page(file_id, _doc, page_index_key)
        return

    page_index = 0
    for text_page in text_pages:
        logging.info(f'process page_index = {page_index}')
        page_index_copy = page_index
        page_index += 1

        if text_page.strip() == '':
            logging.info(f'ignore empty page, page_index={page_index_copy}')
            continue

        page_number = -1
        try:
            page_number = int(text_page[1:text_page.find('页')])
        except:
            pass
        if page_number == -1:
            page_index_key = 'page_index_' + str(page_index_copy)
        else:
            page_index_key = 'page_number_' + str(page_number)

        _save_page(file_id, page_index_key, text_page)
        if (is_index_page(text_page)):
            logging.warn(f'忽略索引! page_index={page_index_copy}, page_number={page_number}')
            continue
        _embed_one_page(file_id, text_page, page_index_key)


def query_doc(file_id_list, query_str):

    if (len(file_id_list) == 1):
        where = {"file_id": file_id_list[0]}
    else:
        cond_list = []
        for file_id in file_id_list:
            cond_list.append({"file_id": file_id})
        where={"$or": cond_list}

    logging.info(f'query db, where={where}, query_str={query_str}')
    doc_and_dist_list = g_db.query(query_str, n_results=2, where=where)
    if len(doc_and_dist_list) == 0:
        raise Exception('no_query_result')
    
    # 根据查出来的 page_index 反过来找整页给到 gpt
    context_list = []
    page_list = []
    i=0
    for doc_and_dist in doc_and_dist_list:
        i+=1
        logging.info(f'query db result, i={i} doc_and_dist={doc_and_dist}')
        doc = doc_and_dist[0]

        page_index = doc.metadata['page_index']
        file_id = doc.metadata['file_id']

        if is_index_page(_load_page(file_id, page_index)):
            logging.warn(f'检查出page_index={page_index}是整页索引，排除掉')
            continue

        if (file_id, page_index) not in page_list:
            page_list.append((file_id, page_index))
    
    logging.info(f'page_list={page_list}')
    for (file_id, page_index) in page_list:
        c1 = _load_page(file_id, page_index)
        if c1:
            context_list.append(c1)

    if len(context_list) == 0:
        raise Exception('no_query_result')
    
    return context_list


from fastapi.responses import StreamingResponse
import openai_proxy

async def ask_doc(user_name, file_id_list: List[str], query_str) -> StreamingResponse:
    context_list = query_doc(file_id_list, query_str)
    return await ask_doc_context(user_name, context_list, query_str)


def get_context_list(file_id, page_number_list):
    context_list = []
    for page_number in page_number_list:
        c1 = _load_page(file_id, 'page_number_' + str(page_number))
        if c1:
            context_list.append(c1)
    if len(context_list) == 0:
        raise Exception('no_query_result')
    return context_list


async def ask_doc_context(user_name, context_list, query_str) -> StreamingResponse:

    prompt = f"""
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.

{' | '.join(context_list)}

  Query: {query_str}

  Helpful Answer:
"""
    logging.info(f'prompt={prompt[:1000]}')
    #return prompt
    return await openai_proxy.proxy(user_name, prompt, 'gpt-4')



async def _main():
    with open('embedchain_util.py', 'r') as f:
        file_content = f.read()
    embed_doc('file_id_1', file_content)
    await ask_doc('user1', ['file_id_1'], "查找整页")


if __name__ == '__main__':
    import asyncio
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
        level=logging.INFO
    )
    asyncio.run(_main())