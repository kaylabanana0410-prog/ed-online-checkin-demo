# Requirements for eventual hospital deployment

Status: draft checklist for a demonstration prototype built on synthetic data. It is not a legal or clinical opinion. Nothing here has been reviewed by St. Joseph's Health Centre, and the prototype is not affiliated with or approved by it.

## 1. Governance and approvals
- [ ] Executive and clinical sponsor; named privacy officer and security lead.
- [ ] Privacy impact assessment and threat/risk assessment completed and signed off.
- [ ] Agreements covering any vendor or hosting provider that handles personal health information (agent and electronic service provider obligations under PHIPA, to be confirmed by privacy counsel).
- [ ] Hospital policy review: data residency, retention schedule, AI use, patient-facing digital tools.

## 2. Clinical safety
- [ ] Replace `app/rules/warning_signs.json` with a hospital-approved, clinically reviewed rule set under change control. Current phrases are placeholders and matching is deliberately crude.
- [ ] Clinical safety case: expected false-negative and false-positive behaviour, review of real (de-identified) free-text answers, ongoing monitoring.
- [ ] Confirm the online form never delays care: 911 notice, no required steps for people who may be unwell, in-person registration always available.
- [ ] CTAS scoring and destination/zone decisions stay inside the hospital's authorized workflow. Zone names (Blue, Green, Rainbow) and rules must be verified with the hospital before use.
- [ ] Assess whether any decision-support function would count as regulated medical device software (Health Canada) before adding one.
- [ ] Usability testing with stressed, older, low-vision, and non-English-speaking users. Downtime procedure (paper process) documented and rehearsed.

## 3. Integration
- [ ] Registration/ADT and EMR integration through interfaces the hospital supports, replacing `MockClinicalWorkflow`. Patient-submitted data enters as unverified; staff verification stays a separate recorded step.
- [ ] Health card eligibility checks only through an authorized provincial service and agreements, replacing `MockCardValidation`. Confirm rules on collecting and using health numbers with the privacy office.
- [ ] Identity matching against the hospital's patient index, with staff resolving duplicates.
- [ ] Destination list sourced from the hospital (replacing `DESTINATIONS` placeholders), with its own change control.

## 4. Security
- [ ] TLS everywhere, HSTS (`COOKIE_SECURE=true`), secure cookies, current protocol versions.
- [ ] Encryption at rest (database or disk) plus field-level encryption for direct identifiers; keys in a managed key service, rotated; secrets in a vault, never in env files or source.
- [ ] Move SQLite to PostgreSQL (the SQLAlchemy models are portable); add migrations (e.g. Alembic) in place of `create_all`.
- [ ] Staff sign-in through the hospital identity provider (SSO) with multi-factor authentication; map roles to hospital roles with least privilege; session and idle timeout policy; remove local passwords.
- [ ] Access monitoring: alert on unusual record viewing; periodic access reviews.
- [ ] Shared-store rate limiting (e.g. Redis) plus gateway/WAF limits; review lockout design (it can be abused to lock a real user out).
- [ ] Self-host Bootstrap and any other assets (with integrity checks); keep the strict CSP; request-size limits at the proxy; configure trusted proxy headers so client IPs are correct.
- [ ] Dependency and container scanning, static and dynamic testing, independent penetration test before launch, vulnerability management process.
- [ ] Encrypted backups, tested restores, and a deletion process that covers backups. Logs go to a SIEM and exclude personal information (the app already logs only paths and error class names).
- [ ] Incident response and breach notification procedure, including notifying patients and the privacy regulator where required (confirm exact duties with counsel).

## 5. Privacy operations
- [ ] Privacy notice and consent wording written and approved by the privacy office (`app/static/privacy.html` is a draft). Separate optional AI consent preserved.
- [ ] Process for access, correction, withdrawal, and deletion requests; retention schedule set (`RETENTION_DAYS`) with documented legal basis.
- [ ] Rules for minors, substitute decision-makers, and capacity set by hospital policy; the form's "another person" option needs a defined verification step.
- [ ] If any external AI provider is ever used: approved contract, data residency, no identifiable data unless explicitly approved, de-identification tested, outputs still guarded.

## 6. Accessibility and language
- [ ] Independent accessibility audit against the applicable standard (WCAG 2.x AA is the usual target; confirm the Ontario requirement that applies), screen reader and keyboard testing on real devices.
- [ ] Clinically reviewed translations and French language service requirements as applicable; interpreter and phone alternatives for people who cannot use the web.

## 7. Operations
- [ ] Hosting with monitored availability, capacity planning, alerting, on-call support.
- [ ] Staff training, SOPs, and a feedback route; metrics for registration time saved and for safety events.
- [ ] Release and change management; rollback plan; periodic review of rules, copy, and AI behaviour.

## 8. What this prototype mocks
| Area | Prototype behaviour | Needed for production |
|---|---|---|
| Symptom AI | Local mock that reformats answers | Approved provider or model, validated, still advisory |
| Warning rules | Placeholder keyword file | Clinically approved rules |
| OCR | Mock (or optional local Tesseract) | Validated against real cards, accuracy monitored |
| Card validation | Format check only, labelled simulated | Authorized provincial service |
| Clinical workflow | Mock receipt, no priority field | Hospital integration |
| Destinations | Two placeholder names | Hospital-verified list |
| Staff auth | Local passwords, scrypt, cookies | SSO and MFA |
| Rate limiting | In-process memory | Shared store and gateway |
| Database | SQLite file | Managed PostgreSQL |
