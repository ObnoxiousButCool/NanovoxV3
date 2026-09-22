"""ORM table definitions.

Imported for its side effect: importing a table module registers it on
``Base.metadata``, which is what lets Alembic's autogenerate and
``Base.metadata.create_all`` see the schema. Empty until Phase 1 defines the
first entities (``Broker``, ``Employer``, ``Member``, ...).
"""

from __future__ import annotations
