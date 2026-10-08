"""`SqlApprovedEmailsRepository` against a real (temporary) database."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.persistence.repositories.approved_emails_repository import (
    SqlApprovedEmailsRepository,
)

_AT = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)


async def test_an_added_address_is_approved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    await repository.add("reader@example.com", at=_AT)

    assert await repository.is_approved("reader@example.com")


async def test_an_address_never_added_is_not_approved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    assert not await repository.is_approved("stranger@example.com")


async def test_matching_is_case_and_whitespace_insensitive(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    await repository.add("  Reader@Example.COM  ", at=_AT)

    assert await repository.is_approved("reader@example.com")
    assert await repository.is_approved("READER@EXAMPLE.COM")


async def test_adding_the_same_address_twice_does_not_duplicate_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    await repository.add("reader@example.com", at=_AT)
    await repository.add("reader@example.com", at=_AT)

    assert await repository.list_all() == ("reader@example.com",)


async def test_removing_an_approved_address_revokes_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)
    await repository.add("reader@example.com", at=_AT)

    removed = await repository.remove("reader@example.com")

    assert removed
    assert not await repository.is_approved("reader@example.com")


async def test_removing_an_address_never_added_reports_it_was_not_there(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    assert not await repository.remove("stranger@example.com")


async def test_list_all_is_empty_until_something_is_approved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)

    assert await repository.list_all() == ()


async def test_list_all_is_oldest_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlApprovedEmailsRepository(session_factory)
    await repository.add("first@example.com", at=_AT)
    await repository.add("second@example.com", at=_AT.replace(hour=10))

    assert await repository.list_all() == ("first@example.com", "second@example.com")
