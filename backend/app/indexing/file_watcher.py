"""
Workspace file watcher for incremental indexing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import asyncio
import structlog

try:
    from watchdog.observers import Observer
    from watchdog.observers.polling import PollingObserver
    from watchdog.events import FileSystemEventHandler
except Exception:
    Observer = None
    PollingObserver = None
    FileSystemEventHandler = object

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.indexer import FileIndexer

logger = structlog.get_logger()


def is_watchdog_available() -> bool:
    return Observer is not None


@dataclass
class FileChangeEvent:
    rel_path: Path
    action: str  # "upsert" or "delete"


class _WorkspaceEventHandler(FileSystemEventHandler):
    def __init__(self, enqueue: Callable[[str, str], None]):
        self._enqueue = enqueue

    def on_created(self, event):
        if event.is_directory:
            return
        self._enqueue("upsert", event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._enqueue("upsert", event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self._enqueue("delete", event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        src_path = getattr(event, "src_path", None)
        dest_path = getattr(event, "dest_path", None)
        if src_path:
            self._enqueue("delete", src_path)
        if dest_path:
            self._enqueue("upsert", dest_path)


class WorkspaceFileWatcher:
    def __init__(
        self,
        workspace_id: str,
        module_id: str,
        workspace_path: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore,
        db_session_maker,
        debounce_seconds: float = 0.5,
        use_polling: bool = False
    ):
        self.workspace_id = workspace_id
        self.module_id = module_id
        self.workspace_path = Path(workspace_path)
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.db_session_maker = db_session_maker
        self.debounce_seconds = debounce_seconds
        self.use_polling = use_polling

        self._queue: asyncio.Queue[FileChangeEvent] = asyncio.Queue(maxsize=1000)
        self._stop_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None
        self._observer = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

        self._indexer = FileIndexer(
            workspace_id=self.workspace_id,
            module_id=self.module_id,
            workspace_path=str(self.workspace_path),
            embedding_manager=self.embedder,
            vector_store=self.vector_store,
            db_session=None
        )

    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    async def start(self) -> None:
        if self.is_running():
            return

        if not is_watchdog_available():
            raise RuntimeError("watchdog_not_available")

        self._loop = asyncio.get_running_loop()
        observer_cls = PollingObserver if self.use_polling and PollingObserver else Observer
        self._observer = observer_cls()
        handler = _WorkspaceEventHandler(self._enqueue_event)
        self._observer.schedule(handler, str(self.workspace_path), recursive=True)
        self._observer.start()

        self.vector_store.create_collection(
            collection_name=self._indexer._get_collection_name(),
            vector_size=self.embedder.get_dimensions()
        )

        self._stop_event.clear()
        self._worker_task = self._loop.create_task(self._worker())

        logger.info("workspace_watcher_started",
                    workspace_id=self.workspace_id,
                    path=str(self.workspace_path))

    async def stop(self) -> None:
        if not self._observer:
            return

        self._stop_event.set()
        if self._worker_task:
            await self._worker_task
            self._worker_task = None

        self._observer.stop()
        await asyncio.to_thread(self._observer.join, 5)
        self._observer = None

        logger.info("workspace_watcher_stopped", workspace_id=self.workspace_id)

    def _enqueue_event(self, action: str, path_str: str) -> None:
        if not self._loop or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._queue_event, action, path_str)

    def _queue_event(self, action: str, path_str: str) -> None:
        abs_path = Path(path_str)
        try:
            rel_path = abs_path.relative_to(self.workspace_path)
        except ValueError:
            return

        if not self._should_process(action, rel_path):
            return

        try:
            self._queue.put_nowait(FileChangeEvent(rel_path=rel_path, action=action))
        except asyncio.QueueFull:
            logger.warning("workspace_watcher_queue_full", workspace_id=self.workspace_id)

    def _should_process(self, action: str, rel_path: Path) -> bool:
        return self._indexer._is_path_allowed(rel_path)

    async def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            pending = {event.rel_path: event.action}
            start = self._loop.time() if self._loop else 0.0

            while True:
                remaining = self.debounce_seconds - ((self._loop.time() if self._loop else 0.0) - start)
                if remaining <= 0:
                    break
                try:
                    next_event = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                pending[next_event.rel_path] = next_event.action

            for rel_path, action in pending.items():
                try:
                    await self._process_event(rel_path, action)
                except Exception as e:
                    logger.error("workspace_watcher_event_failed",
                                 workspace_id=self.workspace_id,
                                 path=str(rel_path),
                                 error=str(e))

    async def _process_event(self, rel_path: Path, action: str) -> None:
        async with self._lock:
            async with self.db_session_maker() as session:
                self._indexer.db = session
                if action == "delete":
                    await self._indexer._delete_file(rel_path, recalculate=True)
                else:
                    await self._indexer.index_file(rel_path)
                self._indexer.db = None
