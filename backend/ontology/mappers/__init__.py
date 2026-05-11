"""
Ontology mappers.

Each mapper is a thin function that hydrates an ontology object from a
persistence-layer row (Supabase). Mappers live OUTSIDE the ontology object
files because the ontology is meant to be persistence-agnostic: the object
declares its shape, the mapper handles the impedance mismatch with whatever
schema currently holds the data.

If a mapper grows complex enough that you're tempted to put logic in the
ontology object to make the mapper simpler — stop. The complexity belongs
on the mapper side. The ontology stays clean.
"""
