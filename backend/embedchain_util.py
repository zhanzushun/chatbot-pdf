# based on embedchain==0.0.69
# curl -X POST http://localhost:5007/api7/embed_local_pdf  -H 'Content-Type: application/json' -d '{"file_name":"Kassenova_Chinese_Aid_FINAL_1.pdf", "current_month": "202311", "file_id":"1699352458"}'

import os

import re
from typing import List, Optional, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)

def _split_text_with_regex_from_end(
        text: str, separator: str, keep_separator: bool
) -> List[str]:
    # Now that we have the separator, split the text
    if separator:
        if keep_separator:
            # The parentheses in the pattern keep the delimiters in the result.
            _splits = re.split(f"({separator})", text)
            splits = ["".join(i) for i in zip(_splits[0::2], _splits[1::2])]
            if len(_splits) % 2 == 1:
                splits += _splits[-1:]
            # splits = [_splits[0]] + splits
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s != ""]
    
class ChineseRecursiveTextSplitter(RecursiveCharacterTextSplitter):
    def __init__(
            self,
            separators: Optional[List[str]] = None,
            keep_separator: bool = True,
            is_separator_regex: bool = True,
            **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        super().__init__(keep_separator=keep_separator, **kwargs)
        self._separators = separators or [
            "\n\n",
            #"\n", # 因为pdf解析出来的换行不是真的换行，只是排版放不下
            "。|！|？",
            "\.\s|\!\s|\?\s",
            "；|;\s",
            "，|,\s"
        ]
        self._is_separator_regex = is_separator_regex

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            _separator = _s if self._is_separator_regex else re.escape(_s)
            if _s == "":
                separator = _s
                break
            if re.search(_separator, text):
                separator = _s
                new_separators = separators[i + 1:]
                break

        _separator = separator if self._is_separator_regex else re.escape(separator)
        splits = _split_text_with_regex_from_end(text, _separator, self._keep_separator)

        # Now go merging things, recursively splitting longer texts.
        _good_splits = []
        _separator = "" if self._keep_separator else separator
        for s in splits:
            if self._length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = self._merge_splits(_good_splits, _separator)
                    final_chunks.extend(merged_text)
                    _good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_info = self._split_text(s, new_separators)
                    final_chunks.extend(other_info)
        if _good_splits:
            merged_text = self._merge_splits(_good_splits, _separator)
            final_chunks.extend(merged_text)
        lst = [re.sub(r"\n{2,}", "\n", chunk.strip()) for chunk in final_chunks if chunk.strip()!=""]
        return lst


from typing import Optional
from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class ChineseTextChunker(BaseChunker):
    """Chunker for text."""
    def __init__(self):
        text_splitter = ChineseRecursiveTextSplitter(
            chunk_size=200,
            chunk_overlap=0,
            length_function=len,
        )
        super().__init__(text_splitter)



import hashlib
from embedchain import App as EcApp
from embedchain.loaders.local_text import LocalTextLoader
from embedchain.config import BaseLlmConfig
from embedchain.models.data_type import DataType
from langchain.docstore.document import Document
import config

os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}"

def _save_page(file_id, page_index, page_text):
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

import re
index_number_pattern = re.compile(r'^\d+')
http_pattern = re.compile(r'http')

def _is_index_page(page_text, number_threshold=0.3, http_threshold=0.2):
    lines = page_text.strip().split('\n')
    # 计算行首数字的行数和含http的行数
    number_lines = sum(bool(index_number_pattern.search(line)) for line in lines)
    http_lines = sum(bool(http_pattern.search(line)) for line in lines)
    # 计算行首数字和含http的行数是否分别超过行数的阈值
    number_ratio = number_lines / len(lines)
    http_ratio = http_lines / len(lines)
    return number_ratio >= number_threshold and http_ratio >= http_threshold


def embed_doc(app: EcApp, file_id, txt_content):

    # The input parameter may not take a list longer than 2048 elements (chunks of text).
    # The total number of tokens across all list elements of the input parameter cannot exceed 1,000,000. 
    # (Because the rate limit is 1,000,000 tokens per minute.)

    chunker = ChineseTextChunker()
    chunker.set_data_type(DataType.TEXT)
    
    text_pages = txt_content.split('<|startofpage|>')
    text_pages = text_pages[1:]

    page_index = 0
    for text_page in text_pages:
        logging.info(f'process page_index = {page_index}')
        page_index_copy = page_index
        page_index += 1
        _save_page(file_id, page_index_copy, text_page)
        if (_is_index_page(text_page)):
            logging.warn(f'this is an index page, just ignore! page_index={page_index_copy}')
            continue

        txt1_hash = hashlib.md5(str(text_page).encode("utf-8"))
        _1,_2,_3,_4 = app.load_and_embed(LocalTextLoader(), chunker, text_page, 
            {'file_id': file_id, 'page_index': page_index_copy}, txt1_hash.hexdigest())
        for doc in _1:
            logging.info(f'doc.size={len(doc)}, doc.content={doc}')
        logging.info(f'app.db.cnt={app.db.count()}')


def query_doc(app:EcApp, file_id_list, query_str):

    if (len(file_id_list) == 1):
        where = {"file_id": file_id_list[0]}
    else:
        cond_list = []
        for file_id in file_id_list:
            cond_list.append({"file_id": file_id})
        where={"$or": cond_list}

    logging.info(f'query db, where={where}, query_str={query_str}')
    appQuery  = app
    results = appQuery.db.collection.query(query_texts=[query_str,], n_results=2, where=where)
    documents = [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
    if len(documents) == 0:
        raise Exception('no_query_result')
    
    # 根据查出来的 page_index 反过来找整页文本，再发出去前后共三页文本，如果有两个答案，则共6页文本给到 gpt
    context_list = []
    page_list = []
    i=0
    for doc in documents:
        i+=1
        logging.info(f'query db result, i={i} doc={doc}')
        doc = doc[0]
        page_index = doc.metadata['page_index']
        file_id = doc.metadata['file_id']
        if _is_index_page(_load_page(file_id, page_index)):
            logging.warn(f'检查出page_index={page_index}是整页索引，排除掉')
            continue
        if (file_id, page_index) not in page_list:
            page_list.append((file_id, page_index))
        # if (file_id, page_index-1) not in page_list:
        #     page_list.append((file_id, page_index-1))
        # if (file_id, page_index+1) not in page_list:
        #     page_list.append((file_id, page_index+1))
    
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

async def ask_doc(user_name, ecapp, file_id_list, query_str) -> StreamingResponse:

    context_list = query_doc(ecapp, file_id_list, query_str)
    prompt = f"""
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.

{' | '.join(context_list)}

  Query: {query_str}

  Helpful Answer:
"""
    logging.info(f'prompt={prompt[:1000]}')
    #return prompt
    return await openai_proxy.proxy(user_name, prompt, 'gpt-3.5-turbo')


from embedchain.config import ChromaDbConfig

def create_embedchain_app(db_name):
    app = EcApp(db_config=ChromaDbConfig(collection_name=db_name, dir=db_name))
    logging.info('embedchain-app started')
    return app
