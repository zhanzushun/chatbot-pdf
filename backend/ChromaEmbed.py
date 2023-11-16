from typing import Dict, Any, Optional
import hashlib
import logging

from ChromaDB import ChromaDB
from ChineseRecursiveTextSplitter import ChineseRecursiveTextSplitter

def _create_chunks(text_splitter: ChineseRecursiveTextSplitter, text_content: str, metadata: Dict[str, Any]):
    documents = []
    chunk_ids = []
    metadatas = []

    chunks = text_splitter.split_text(text_content)

    for chunk in chunks:
        chunk_id = hashlib.sha256((chunk + str(metadata)).encode()).hexdigest()
        if (chunk_id in chunk_ids):
            continue
        chunk_ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append(metadata)

    return {
        "documents": documents,
        "ids": chunk_ids,
        "metadatas": metadatas,
    }


def load_and_embed(
    db: ChromaDB,
    text_splitter: ChineseRecursiveTextSplitter,
    text_content: str,
    file_id: str,
    metadata: Dict[str, Any]
):
    embeddings_data = _create_chunks(text_splitter, text_content, metadata)

    documents = embeddings_data["documents"]
    metadatas = embeddings_data["metadatas"]
    ids = embeddings_data["ids"]

    where = {"file_id": file_id}

    db_result = db.get(ids=ids, where=where)
    existing_ids = set(db_result["ids"])

    if len(existing_ids):
        all_data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
        new_data_dict = {id: value for id, value in all_data_dict.items() if id not in existing_ids}

        if not new_data_dict:
            logging.info(f"All chunks already exists in the database.")
            return [], [], [], 0
        else:
            logging.info(f"all chunks={len(all_data_dict)}, old={len(existing_ids)}, new={len(new_data_dict)}")

        documents, metadatas = zip(*new_data_dict.values())
        ids = list(new_data_dict.keys())

    chunks_before_addition = db.count()

    db.add(
        documents=list(documents),
        metadatas=list(metadatas),
        ids=ids
    )
    count_new_chunks = db.count() - chunks_before_addition

    logging.info(f"Successfully saved to db. New chunks count: {count_new_chunks}")
    return list(documents), metadatas, ids, count_new_chunks
