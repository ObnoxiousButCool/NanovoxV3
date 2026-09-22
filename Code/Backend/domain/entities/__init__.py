"""Reference-data entities: frozen, immutable, no I/O.

Cardinality (Data Model sheet): a broker has many employers; an employer has
many members and 1-3 contacts; a member never stores a broker — it's
inherited through the employer.
"""
