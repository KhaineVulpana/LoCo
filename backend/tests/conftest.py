import builtins
import fnmatch
import os
import sys
import types
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, get_args, get_origin

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

try:
    import structlog  # noqa: F401
except ModuleNotFoundError:
    structlog_module = types.ModuleType("structlog")

    class _DummyLogger:
        def debug(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    def get_logger(*args, **kwargs):
        return _DummyLogger()

    structlog_module.get_logger = get_logger
    sys.modules["structlog"] = structlog_module

try:
    import pydantic_settings  # noqa: F401
except Exception:
    pydantic_settings_module = types.ModuleType("pydantic_settings")

    def SettingsConfigDict(**kwargs):
        return kwargs

    def _cast_env_value(value: str, target_type: Any) -> Any:
        origin = get_origin(target_type)
        if origin is None:
            cast_type = target_type
        else:
            args = [arg for arg in get_args(target_type) if arg is not type(None)]
            cast_type = args[0] if len(args) == 1 else target_type

        if cast_type is bool:
            return value.strip().lower() in ("1", "true", "yes", "on")
        if cast_type is int:
            try:
                return int(value)
            except ValueError:
                return value
        if cast_type is float:
            try:
                return float(value)
            except ValueError:
                return value
        return value

    class BaseSettings:
        def __init__(self, **kwargs):
            annotations = getattr(self, "__annotations__", {})
            for field, field_type in annotations.items():
                if field in kwargs:
                    value = kwargs[field]
                else:
                    env_value = os.getenv(field)
                    if env_value is not None:
                        value = _cast_env_value(env_value, field_type)
                    else:
                        value = getattr(self.__class__, field, None)
                setattr(self, field, value)

    pydantic_settings_module.BaseSettings = BaseSettings
    pydantic_settings_module.SettingsConfigDict = SettingsConfigDict
    sys.modules["pydantic_settings"] = pydantic_settings_module

try:
    import sentence_transformers  # noqa: F401
except Exception:
    import numpy as np

    st_module = types.ModuleType("sentence_transformers")

    class SentenceTransformer:
        def __init__(self, model_name, cache_folder=None):
            self._dimensions = 3

        def get_sentence_embedding_dimension(self):
            return self._dimensions

        def encode(self, texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True):
            return np.zeros((len(texts), self._dimensions))

    st_module.SentenceTransformer = SentenceTransformer
    sys.modules["sentence_transformers"] = st_module

try:
    import chardet  # noqa: F401
except ModuleNotFoundError:
    chardet_module = types.ModuleType("chardet")

    def detect(_raw):
        return {"encoding": "utf-8"}

    chardet_module.detect = detect
    sys.modules["chardet"] = chardet_module

try:
    import aiofiles  # noqa: F401
except ModuleNotFoundError:
    aiofiles_module = types.ModuleType("aiofiles")

    class _AsyncFile:
        def __init__(self, file_obj):
            self._file = file_obj

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self._file.close()

        async def read(self):
            return self._file.read()

        async def write(self, data):
            return self._file.write(data)

    def open(file, mode="r", encoding=None, errors=None):
        file_obj = builtins.open(file, mode, encoding=encoding, errors=errors)
        return _AsyncFile(file_obj)

    aiofiles_module.open = open
    sys.modules["aiofiles"] = aiofiles_module

try:
    import pathspec  # noqa: F401
except Exception:
    pathspec_module = types.ModuleType("pathspec")

    class PathSpec:
        def __init__(self, patterns: List[str]):
            self._patterns = patterns

        @classmethod
        def from_lines(cls, _pattern_type: str, lines: List[str]):
            patterns = []
            for line in lines:
                if line is None:
                    continue
                text = str(line).strip()
                if not text or text.startswith("#"):
                    continue
                patterns.append(text)
            return cls(patterns)

        def match_file(self, file_path: str) -> bool:
            normalized = str(file_path).replace("\\", "/").lstrip("./")
            for pattern in self._patterns:
                negated = pattern.startswith("!")
                pat = pattern[1:] if negated else pattern
                if not pat:
                    continue
                if self._matches(pat, normalized):
                    return not negated
            return False

        def _matches(self, pattern: str, path: str) -> bool:
            if pattern.startswith("/"):
                pattern = pattern.lstrip("/")
                return fnmatch.fnmatch(path, pattern)
            if pattern.endswith("/"):
                base = pattern[:-1]
                return path == base or path.startswith(pattern)
            if "/" not in pattern:
                return fnmatch.fnmatch(path.split("/")[-1], pattern)
            return fnmatch.fnmatch(path, pattern)

    pathspec_module.PathSpec = PathSpec
    sys.modules["pathspec"] = pathspec_module

try:
    import qdrant_client  # noqa: F401
except ModuleNotFoundError:
    qdrant_module = types.ModuleType("qdrant_client")
    models_module = types.ModuleType("qdrant_client.models")

    class QdrantClient:
        def __init__(self, host=None, port=None):
            self._collections = []

        def get_collections(self):
            return types.SimpleNamespace(collections=self._collections)

    class Distance:
        COSINE = "COSINE"

    class VectorParams:
        def __init__(self, size, distance):
            self.size = size
            self.distance = distance

    class PointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    class MatchValue:
        def __init__(self, value):
            self.value = value

    class FieldCondition:
        def __init__(self, key, match):
            self.key = key
            self.match = match

    class Filter:
        def __init__(self, must=None):
            self.must = must or []

    class SearchParams:
        pass

    class PointIdsList:
        def __init__(self, points):
            self.points = points

    qdrant_module.QdrantClient = QdrantClient
    qdrant_module.models = models_module

    models_module.Distance = Distance
    models_module.VectorParams = VectorParams
    models_module.PointStruct = PointStruct
    models_module.Filter = Filter
    models_module.FieldCondition = FieldCondition
    models_module.MatchValue = MatchValue
    models_module.SearchParams = SearchParams
    models_module.PointIdsList = PointIdsList

    sys.modules["qdrant_client"] = qdrant_module
    sys.modules["qdrant_client.models"] = models_module

if "app.main" not in sys.modules:
    main_stub = types.ModuleType("app.main")

    def _missing_embedding_manager():
        raise RuntimeError("app.main get_embedding_manager stub used in tests")

    def _missing_vector_store():
        raise RuntimeError("app.main get_vector_store stub used in tests")

    main_stub.get_embedding_manager = _missing_embedding_manager
    main_stub.get_vector_store = _missing_vector_store
    sys.modules["app.main"] = main_stub


repo_root = Path(__file__).resolve().parents[2]
backend_root = repo_root / "backend"
sys.path.insert(0, str(backend_root))


@dataclass
class FakeEmbedding:
    data: List[float]

    def tolist(self) -> List[float]:
        return list(self.data)


class FakeEmbeddingManager:
    def __init__(self, dimensions: int = 6):
        self._dimensions = dimensions

    def get_dimensions(self) -> int:
        return self._dimensions

    def get_model_name(self) -> str:
        return "fake-embedding"

    def _embed_text(self, text: str) -> FakeEmbedding:
        base = sum(ord(c) for c in text) % 97
        vec = [((base + i * 7) % 97) / 97.0 for i in range(self._dimensions)]
        return FakeEmbedding(vec)

    def embed(self, texts: List[str]) -> List[FakeEmbedding]:
        return [self._embed_text(text) for text in texts]

    def embed_single(self, text: str) -> FakeEmbedding:
        return self._embed_text(text)

    def embed_query(self, text: str) -> FakeEmbedding:
        return self._embed_text(text)


@dataclass
class FakePoint:
    id: str
    vector: List[float]
    payload: Dict[str, Any]


class FakeVectorStore:
    def __init__(self):
        self.collections: Dict[str, OrderedDict[str, FakePoint]] = {}
        self.vector_sizes: Dict[str, int] = {}

    def create_collection(self, collection_name: str, vector_size: int, distance: Any = None) -> bool:
        if collection_name in self.collections:
            return False
        self.collections[collection_name] = OrderedDict()
        self.vector_sizes[collection_name] = vector_size
        return True

    def upsert_vectors(self, collection_name: str, points: List[Any]) -> bool:
        if collection_name not in self.collections:
            self.create_collection(collection_name, vector_size=0)
        for point in points:
            point_id = getattr(point, "id", None) or point.get("id")
            vector = getattr(point, "vector", None) or point.get("vector")
            payload = getattr(point, "payload", None)
            if payload is None:
                payload = point.get("payload")
            self.collections[collection_name][str(point_id)] = FakePoint(
                id=str(point_id),
                vector=list(vector),
                payload=dict(payload or {})
            )
        return True

    def _score(self, a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        points = list(self.collections.get(collection_name, {}).values())
        results = []
        for point in points:
            if filter_conditions:
                if any(point.payload.get(k) != v for k, v in filter_conditions.items()):
                    continue
            score = self._score(point.vector, query_vector)
            if score_threshold is not None and score < score_threshold:
                continue
            results.append({
                "id": point.id,
                "score": score,
                "payload": point.payload
            })
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def scroll(self, collection_name: str, limit: int = 100, offset: Optional[int] = None) -> Dict[str, Any]:
        points = list(self.collections.get(collection_name, {}).values())
        start = int(offset or 0)
        end = start + limit
        page = points[start:end]
        next_offset = end if end < len(points) else None
        return {
            "points": [
                {"id": point.id, "vector": point.vector, "payload": point.payload}
                for point in page
            ],
            "next_offset": next_offset
        }

    def delete_points(self, collection_name: str, point_ids: List[str]) -> bool:
        if collection_name not in self.collections:
            return False
        for pid in point_ids:
            self.collections[collection_name].pop(str(pid), None)
        return True

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        points = self.collections.get(collection_name, {})
        return {
            "name": collection_name,
            "vector_size": self.vector_sizes.get(collection_name, 0),
            "distance": "COSINE",
            "points_count": len(points),
            "status": "green"
        }


@pytest.fixture()
def fake_embedding_manager() -> FakeEmbeddingManager:
    return FakeEmbeddingManager()


@pytest.fixture()
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture()
def fake_point() -> FakePoint:
    return FakePoint(id="point-1", vector=[0.1, 0.2, 0.3], payload={"content": "example"})


@pytest_asyncio.fixture()
async def async_session_maker(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    schema_sql = (repo_root / "backend" / "schema.sql").read_text(encoding="utf-8")

    async with engine.begin() as conn:
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_maker
    finally:
        await engine.dispose()
