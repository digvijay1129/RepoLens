"""Persist repository chat conversations and grounded answer messages.

Revision ID: 20261025_0007
Revises: 20261025_0006
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0007"
down_revision: Union[str, None] = "20261025_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 160", name=op.f("ck_chat_conversations_title_length_valid")),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_chat_conversations_repository_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversations")),
        sa.UniqueConstraint("id", "repository_id", "user_id", name="uq_chat_conversations_id_repo_user"),
    )
    op.create_index(
        "ix_chat_conversations_user_repository_updated",
        "chat_conversations",
        ["user_id", "repository_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_chat_messages_role_allowed")),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 20000", name=op.f("ck_chat_messages_content_length_valid")),
        sa.ForeignKeyConstraint(
            ["conversation_id", "repository_id", "user_id"],
            ["chat_conversations.id", "chat_conversations.repository_id", "chat_conversations.user_id"],
            name="fk_chat_messages_conversation_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        "ix_chat_messages_conversation_created",
        "chat_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_messages_user_repository_created",
        "chat_messages",
        ["user_id", "repository_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_user_repository_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_repository_updated", table_name="chat_conversations")
    op.drop_table("chat_conversations")
