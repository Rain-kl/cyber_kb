from functools import wraps
from typing import Callable

from fastapi import Request

from api.model import QueryResponseModel
from config import OLLAMA_API_URL, OLLAMA_MODEL_NAME
from utils.embedding import AsyncOllamaEmbeddingModel

embedding_model = AsyncOllamaEmbeddingModel(OLLAMA_API_URL, OLLAMA_MODEL_NAME)


def require_authorization(func: Callable):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        # if not authorization:
        #     raise HTTPException(
        #         status_code=401, detail="Authorization token is required"
        #     )
        # 将授权令牌传递给原始函数，以便它可以使用
        authorization = "test"
        # 使用request.state存储授权信息，这样在接口中可以读取
        request.state.authorization = authorization
        return await func(request, *args, **kwargs)

    return wrapper


def parse_query_response(results: dict) -> list[QueryResponseModel]:
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    response_items = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        response_items.append(
            QueryResponseModel(
                **{"content": doc, "metadata": meta, "relevance_score": 1 - dist}
            )
        )

    return response_items
