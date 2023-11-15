import os
from typing import Dict, Optional, List, Any
import logging

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from chromadb import Collection, QueryResult
from chromadb.errors import InvalidDimensionException

from langchain.docstore.document import Document


class ChromaDB:
    def __init__(self, my_dir, collection_name):
        chromadb_settings = Settings()

        use_server = False
        if use_server:
            chromadb_settings.chroma_server_host = ''
            chromadb_settings.chroma_server_http_port = ''
            chromadb_settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI" # Can be "chromadb.api.segment.SegmentAPI" or "chromadb.api.fastapi.FastAPI"
        else:
            chromadb_settings.persist_directory = my_dir
            chromadb_settings.is_persistent = True

        self.client = chromadb.Client(chromadb_settings)

        self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization_id=os.getenv("OPENAI_ORGANIZATION"),
            model_name="text-embedding-ada-002",
        )
        self.switch_to_collection(collection_name)


    def switch_to_collection(self, collection_name: str):
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
        )
    

    def _generate_where_clause(self, where: Dict[str, any]) -> str:
        if len(where.keys()) == 1:
            return where
        where_filters = []
        for k, v in where.items():
            if isinstance(v, str):
                where_filters.append({k: v})
        return {"$and": where_filters}

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        args = {}
        if ids:
            args["ids"] = ids
        if where:
            args["where"] = self._generate_where_clause(where)
        if limit:
            args["limit"] = limit
        return self.collection.get(**args)

    def add(
        self,
        documents: List[str],
        metadatas: List[object],
        ids: List[str]
    ) -> Any:
        BATCH_SIZE = 100
        size = len(documents)

        if len(documents) != size or len(metadatas) != size or len(ids) != size:
            raise ValueError(
                "Cannot add documents to chromadb with inconsistent sizes. Documents size: {}, Metadata size: {},"
                " Ids size: {}".format(len(documents), len(metadatas), len(ids))
            )

        for i in range(0, len(documents), BATCH_SIZE):
            logging.info("Inserting batches from {} to {} in chromadb".format(i, min(len(documents), i + BATCH_SIZE)))
            self.collection.add(
                documents=documents[i : i + BATCH_SIZE],
                metadatas=metadatas[i : i + BATCH_SIZE],
                ids=ids[i : i + BATCH_SIZE],
            )

    def _format_result(self, results: QueryResult) -> list[tuple[Document, float]]:
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def query(self, input_query: str, n_results: int, where: Dict[str, any]) -> list[tuple[Document, float]]:
        try:
            result = self.collection.query(
                query_texts=[
                    input_query,
                ],
                n_results=n_results,
                where=self._generate_where_clause(where),
            )
        except InvalidDimensionException as e:
            raise InvalidDimensionException(
                e.message()
                + ". This is commonly a side-effect when an embedding function, different from the one used to add the"
                " embeddings, is used to retrieve an embedding from the database."
            ) from None
        return self._format_result(result)


    def count(self) -> int:
        return self.collection.count()

    def delete(self, where):
        return self.collection.delete(where=where)

    def reset(self):
        collection_name = self.collection.name
        try:
            self.client.reset()
        except ValueError:
            raise ValueError(
                "For safety reasons, resetting is disabled. "
                "Please enable it by setting `allow_reset=True` in your ChromaDbConfig"
            ) from None
        self.switch_to_collection(collection_name)


