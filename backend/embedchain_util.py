# based on embedchain==0.0.69
# curl -X POST http://localhost:5007/api7/embed_local_pdf  -H 'Content-Type: application/json' -d '{"file_name":"自由的魂魄所在.pdf", "current_month": "202310", "file_id":"1697615870"}'

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
            chunk_size=100,
            chunk_overlap=0,
            length_function=len,
        )
        super().__init__(text_splitter)



import hashlib
from embedchain import App as EcApp
from embedchain.loaders.local_text import LocalTextLoader
from embedchain.config import BaseLlmConfig
from embedchain.models.data_type import DataType
import config

os.environ["OPENAI_API_KEY"] = f"sk-{config.API_KEY}"


def embed_doc(app: EcApp, file_id, txt_content):
    chunker = ChineseTextChunker()
    chunker.set_data_type(DataType.TEXT)
    
    # The input parameter may not take a list longer than 2048 elements (chunks of text).
    # The total number of tokens across all list elements of the input parameter cannot exceed 1,000,000. 
    # (Because the rate limit is 1,000,000 tokens per minute.)
    logging.info(f'len(txt_content)={len(txt_content)}')
    lst = chunker.text_splitter.split_text(txt_content)

    batch_size = 2000
    batch_idx = 0
    for i in range(0, len(lst), batch_size):
        batch = lst[i:i+batch_size]
        batch_txt_content = '\n\n'.join(batch)
        batch_idx += 1

        txt1_hash = hashlib.md5(str(batch_txt_content).encode("utf-8"))
        app.load_and_embed(LocalTextLoader(), chunker, batch_txt_content, {'file_id': file_id}, txt1_hash.hexdigest())
        logging.info(f'batch={batch_idx}, app.db.cnt={app.db.count()}')


def ask_doc_generator(app:EcApp, file_id_list, query_str):

    if (len(file_id_list) == 1):
        where = {"file_id": file_id_list[0]}
    else:
        cond_list = []
        for file_id in file_id_list:
            cond_list.append({"file_id": file_id})
        where={"$or": cond_list}

    logging.info(f'query db, where={where}')
    appQuery  = app
    contexts = appQuery.retrieve_from_database(input_query=query_str, config=BaseLlmConfig(number_documents=5), where=where)
    if len(contexts) == 0:
        raise Exception('no_query_result')
    logging.info(f'query db result: {contexts}')

    response = appQuery.llm.query(input_query=query_str, contexts=contexts, config=BaseLlmConfig(stream=True, model='gpt-4'), dry_run=False)
    for s in response:
        yield str(s)

from fastapi.responses import StreamingResponse

def ask_doc(ecapp, file_id_list, query_str):
    generator = ask_doc_generator(ecapp, file_id_list, query_str)
    return StreamingResponse(generator)


from embedchain.config import ChromaDbConfig

def create_embedchain_app(db_name):
    app = EcApp(db_config=ChromaDbConfig(collection_name=db_name, dir=db_name))
    logging.info('embedchain-app started')
    return app
