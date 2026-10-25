"""Add workspace credentials and persistent repository metadata.

Revision ID: 20261025_0003
Revises: 20261025_0002
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0003"
down_revision: Union[str, None] = "20261025_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Password hashes are nullable to keep pre-existing Phase 2 workspace rows
    # migratable. Legacy rows cannot authenticate until credentials are set.
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    op.add_column("repositories", sa.Column("github_repository_id", sa.BigInteger(), nullable=True))
    op.add_column("repositories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("repositories", sa.Column("language", sa.String(length=100), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("stargazers_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("forks_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("open_issues_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("size", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("repositories", sa.Column("license_name", sa.String(length=255), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("github_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("selected_branch", sa.String(length=255), server_default="main", nullable=False),
    )
    op.execute(
        "UPDATE repositories SET selected_branch = COALESCE(default_branch, 'main')"
    )

    op.create_check_constraint(
        op.f("ck_repositories_stargazers_nonnegative"),
        "repositories",
        "stargazers_count >= 0",
    )
    op.create_check_constraint(
        op.f("ck_repositories_forks_nonnegative"),
        "repositories",
        "forks_count >= 0",
    )
    op.create_check_constraint(
        op.f("ck_repositories_open_issues_nonnegative"),
        "repositories",
        "open_issues_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_repositories_open_issues_nonnegative"), "repositories", type_="check")
    op.drop_constraint(op.f("ck_repositories_forks_nonnegative"), "repositories", type_="check")
    op.drop_constraint(op.f("ck_repositories_stargazers_nonnegative"), "repositories", type_="check")
    op.drop_column("repositories", "selected_branch")
    op.drop_column("repositories", "github_updated_at")
    op.drop_column("repositories", "archived")
    op.drop_column("repositories", "license_name")
    op.drop_column("repositories", "size")
    op.drop_column("repositories", "open_issues_count")
    op.drop_column("repositories", "forks_count")
    op.drop_column("repositories", "stargazers_count")
    op.drop_column("repositories", "language")
    op.drop_column("repositories", "description")
    op.drop_column("repositories", "github_repository_id")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
