# Security Policy & University Pilot Protection Guidelines

## 1. Authentication & Session Security
- **Algorithm**: Password hashing via `PBKDF2-SHA256` with automatic work-factor calibration.
- **Tokens**: Stateless JWT tokens (`HS256`) with configurable expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Storage**: Client-side localStorage for bearer tokens; credentials and passwords are never cached in plaintext.

## 2. Role-Based Authorization & IDOR Protection
- **Role Enforcement**: Backend routes enforce user roles (`candidate`, `placement_staff`, `admin`) via `require_role(...)`.
- **Direct Object Reference (IDOR) Protection**:
  - Candidates can only retrieve and modify their own interviews, resumes, profiles, and reports.
  - Placement staff and administrators have read access across candidate performance dashboards.
  - Unauthorized direct-ID access attempts return `403 Forbidden`.

## 3. Resume & Document Upload Validation
- **Allowed Formats**: `.pdf`, `.docx`, `.txt` only.
- **MIME & Header Verification**: File byte signatures (e.g. `%PDF-`, `PK\x03\x04`) are verified before parsing.
- **Size Limit**: Maximum 10MB per upload.
- **Path Traversal Defense**: All uploads are stored under randomly generated UUID filenames in isolated `uploads/user_{id}/` subdirectories; client-provided filenames are sanitized for display only.

## 4. Secrets Protection & Audit Logging
- **Environment Driven**: All API keys (Gemini, ElevenLabs, OpenAI) and database credentials reside strictly in `.env`.
- **Audit Trails**: Sensitive actions (logins, password updates, admin exports) are recorded via `AuditLogger` with automatic redaction of passwords, tokens, and keys.

## 5. Vulnerability Reporting
For security audits or potential vulnerability reports during university pilot deployment, contact the administrative engineering team directly.
