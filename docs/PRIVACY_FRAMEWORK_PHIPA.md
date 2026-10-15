# Privacy framework for review (PHIPA and hospital policy)

Status: draft checklist for a privacy officer and legal counsel. It describes what this prototype does and what must be decided. It is not legal advice and makes no claim of PHIPA compliance. The prototype uses synthetic data only.

## 1. Data inventory
| Data | Why collected | Where it lives | Retention (prototype) | Who sees it |
|---|---|---|---|---|
| Legal and preferred name, date of birth, phone, optional email | Administrative registration | `patients` table | `RETENTION_DAYS` (30) | Staff roles with view access |
| Accessibility or communication needs (optional) | Support at arrival | `patients` | Same | Same |
| Symptom answers | Preliminary information for staff | `symptom_responses` | Same | Same |
| AI-style summary (only with consent) | Convenience for staff, labelled as AI | `summaries` | Same | Same |
| Health card status only | Know what is still needed | `submissions` | Same | Same |
| Consent choices | Record of what the patient agreed to | `consents` | Same | Staff view |
| Staff actions and views | Accountability | `audit_events` (no names or health data) | Not yet purged: set a policy | Staff view of a record's own log |

Deliberately not collected or kept: health card numbers, health card images, passwords in plaintext, attempted login names, identifying data sent to any AI service, personal data in URLs or logs.

## 2. Consent and notice
- Required processing (registration) and optional AI summarizing are separate checkboxes; the form works without AI consent.
- The privacy notice is a draft at `/static/privacy.html`; wording, contact details, and public information statement need the privacy office.
- Open questions: when implied vs express consent applies to online pre-registration; withdrawal mechanics; handling for minors, substitute decision-makers, and capacity; verifying someone who completes the form for another person.

## 3. Use and disclosure limits
- Submitted data is shown to signed-in staff only; the list view omits names.
- Patient-reported, AI-generated, and staff-verified information are shown in separate labelled sections.
- No data is sent outside the application. Any external AI provider would need approval, contracts, and a privacy review first.
- Decide: which staff roles may see symptom text, how access is justified, and how inappropriate access is detected and followed up.

## 4. AI safeguards in the design
- Warning signs come from a configurable rules engine, never from the AI; the AI cannot call any clinical endpoint.
- The AI sees symptom answers only, is blocked from diagnosis or "safe to wait" wording, and falls back to the patient's own words when unavailable or unsure.
- Nothing from the AI sets priority, a CTAS score, a destination, or "assessment complete". Only a signed-in nurse or charge nurse can mark clinical steps.
- No demographic or insurance characteristic is used anywhere to change priority.

## 5. Safeguards in the prototype (mapping to review)
| Topic | Control |
|---|---|
| Access control | Server-enforced roles, session cookies (HttpOnly, SameSite=Strict), CSRF tokens |
| Authentication | scrypt hashing, no default passwords, lockout and rate limits |
| Input and uploads | Server-side validation, size and signature checks, private temp files deleted at once |
| Errors and logs | Generic errors, no submitted values echoed, no personal data in logs |
| Web hardening | CSP without inline scripts, nosniff, frame denial, no-store caching |
| Auditing | Action log with actor and event type, field names only |
| Retention | Configurable purge at startup; patient-initiated deletion with token |

## 6. Individual rights and openness
- Patient can view status and delete their submission using the access token shown once at submission.
- Still needed: a general access/correction request route, a written public statement of information practices, and an escalation path for complaints.

## 7. Incidents
- Define breach detection, containment, assessment, and notification steps, including duties to individuals and the privacy regulator (confirm triggers and timelines with counsel).

## 8. Review checklist
- [ ] Privacy impact assessment completed and approved
- [ ] Custodian and agent roles, and any service-provider agreements, confirmed
- [ ] Notice and consent wording approved (including AI consent)
- [ ] Rules for minors, substitute decision-makers, capacity decided
- [ ] Staff role design and access monitoring approved
- [ ] Retention schedule and deletion (including backups) approved
- [ ] Data residency and hosting approved
- [ ] Health number collection and use confirmed with the privacy office
- [ ] External AI use, if any, approved with contracts and de-identification testing
- [ ] Breach response procedure written and rehearsed
