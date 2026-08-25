# Comprehensive Viva Voce Preparation Guide

This guide prepares B.Tech students to defend the project architecture, tech stack choices, security controls, and design decisions during external university viva examinations.

---

## 1. Core Technical Viva Questions & Answers

### Q1: Why did you choose FastAPI over Flask or Django for the backend?
**Answer**: FastAPI was selected because:
1. **Native AsyncIO Support**: Asynchronous request handling allows concurrent candidate interviews and async database queries without thread blocking.
2. **Pydantic Data Validation**: Automatic type validation and OpenAPI schema generation for all request and response payloads.
3. **High Performance**: ASGI (Uvicorn) performance comparable to Node.js and Go.

### Q2: Why is the interview timer controlled by the backend rather than the frontend JavaScript?
**Answer**: In technical assessment platforms, client-side timers can be manipulated by altering local browser clocks or JavaScript variables. Controlling the timer on the backend ensures authoritative state integrity, preventing time manipulation attacks during university placement tests.

### Q3: How does your RAG system work, and why use pgvector over a standalone vector database?
**Answer**:
1. Company job specs are chunked into sliding text windows and converted into 1536-dimensional embeddings.
2. Embeddings are stored in PostgreSQL using the `pgvector` extension.
3. Cosine similarity queries (`<=>` operator) retrieve top relevant context fragments matching candidate topics.
4. Using `pgvector` inside PostgreSQL avoids maintaining a separate vector database (like Pinecone/Qdrant), preserving ACID transactional consistency and reducing operational complexity.

### Q4: Why shouldn't an LLM be asked directly to "give a score out of 100"?
**Answer**: Unconstrained LLM scoring leads to high variance and inconsistency. Our platform forces the LLM to evaluate 5 specific rubric dimensions (Correctness, Relevance, Reasoning, Depth, Communication) on a 0-10 scale and extract evidence quotes. The backend then computes the weighted final score deterministically using fixed weights.

### Q5: How do you handle prompt injection attacks from malicious candidate answers?
**Answer**: Candidate inputs pass through `sanitize_input()` which strips system keywords and injection tokens. Furthermore, system prompts wrap candidate answers inside delimited untrusted data blocks and explicitly instruct the LLM model to treat them purely as text to be evaluated rather than executable instructions.

### Q6: Why are facial emotion and appearance explicitly excluded from interview scoring?
**Answer**: Computer vision facial emotion recognition is scientifically unreliable, biased, and ethical compliance standards prohibit using facial appearance or facial expressions as automated hiring or technical capability scores. Technical evaluation must be strictly grounded in spoken/written technical accuracy and rationale.
