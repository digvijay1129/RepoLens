"""Import all models here so SQLAlchemy and Alembic discover their tables."""

from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.repository_chunk_embedding import RepositoryChunkEmbedding
from app.models.user import User

__all__ = [
    "User",
    "Repository",
    "RepositoryChunk",
    "RepositoryChunkEmbedding",
    "IndexingJob",
    "ChatConversation",
    "ChatMessage",
]
