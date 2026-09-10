# My contribution — Pooria / Hasan Jalili

## Attribution basis

This statement records the project owner's supplied attribution. It is not an independent authorship audit: a source snapshot and commit identities do not establish exclusive personal ownership. The code paths below show the areas of work, not proof that every line was authored by one person.

## Primary implementation and technical work

- **Web application:** primary implementation of the Next.js application, including the UI and associated product, administrative, authentication, and chat experiences. Review `web/src/app/`, `web/src/components/`, `web/src/hooks/`, and `web/src/store/`.
- **Product API:** implementation of API functionality, including AI-assisted development. Review `api/app/api/`, `api/app/services/`, `api/app/repositories/`, and `api/alembic/`.
- **AI Engine:** implementation of the service and model integration, with conversational discovery, request interpretation, and response generation. Review `ai-engine/app/routers/chat.py` and `ai-engine/app/services/llm_client.py`.
- **RAG/search and embeddings:** work on retrieval, embedding providers, Qdrant integration, search quality mechanisms, and evaluation. Review `ai-engine/app/services/rag.py`, `ai-engine/app/services/embedding/`, and `api/app/services/search_eval_service.py`.
- **Platform setup and improvements:** Docker-related setup, RabbitMQ-related setup, GitHub/repository setup, and technical and operational improvements associated with these areas. The presence of broker code does not imply that all event-driven workflows are implemented.

## Collaborative and team work

Product architecture and major product decisions were collaborative. Pooria does not claim exclusive ownership of those decisions or authorship of the entire system, and is not represented as CTO.

The mobile application was primarily implemented by **Mohammad**. It is included to explain the complete platform and client/API contract. Other infrastructure work may also include Mohammad's contribution; the infrastructure directory should not be read as an exclusive Pooria authorship claim.

## AI-assisted development

The owner reports use of **Claude Code, Codex, Cursor, and OpenCode** for implementation assistance, code generation, refactoring, review, testing, and iterative development. Architecture decisions, validation, review, testing, and business correctness remained under human engineering responsibility.

These tools were part of the engineering workflow. Their use does not establish that a particular tool wrote any specific file. This snapshot does not invent productivity percentages, independent audit results, or individual ownership beyond the attribution supplied by the owner.
