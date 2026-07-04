// Epis-KG schema constraints and indexes.
// Applied idempotently on startup by graph_layer.constraints.apply_constraints_and_indexes.

// --- Uniqueness / key constraints (guarantee data integrity) ---------------
CREATE CONSTRAINT claim_id IF NOT EXISTS
FOR (c:Claim) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT source_id IF NOT EXISTS
FOR (s:Source) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT evidence_id IF NOT EXISTS
FOR (e:Evidence) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT rhetoric_id IF NOT EXISTS
FOR (r:Rhetoric) REQUIRE r.id IS UNIQUE;

// --- Existence constraints on the properties we always score on -----------
CREATE CONSTRAINT claim_statement_exists IF NOT EXISTS
FOR (c:Claim) REQUIRE c.statement IS NOT NULL;

CREATE CONSTRAINT source_name_exists IF NOT EXISTS
FOR (s:Source) REQUIRE s.name IS NOT NULL;

// --- Range / lookup indexes -----------------------------------------------
CREATE INDEX claim_eis IF NOT EXISTS FOR (c:Claim) ON (c.epistemic_integrity_score);
CREATE INDEX rhetoric_category IF NOT EXISTS FOR (r:Rhetoric) ON (r.category);
CREATE INDEX document_timestamp IF NOT EXISTS FOR (d:Document) ON (d.timestamp);

// --- Vector index on chunk embeddings for GraphRAG retrieval --------------
// 1536 dims matches text-embedding-3-small; change to match EMBEDDING_MODEL.
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
