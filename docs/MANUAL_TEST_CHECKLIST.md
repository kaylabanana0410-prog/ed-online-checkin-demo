# Manual browser walkthrough (synthetic data only)

Start: `python -m app.manage seed-demo` (copy the passwords), then `uvicorn app.main:app --reload --port 8001`.
Open http://127.0.0.1:8001 (patient) and http://127.0.0.1:8001/staff (staff, second tab). Keep the browser console open: no red "Content Security Policy" messages should appear.

## Patient
- [ ] Step 1 shows the title, subtitle, 911 notice, "does not reserve a place" text, privacy link (opens the draft notice), and "Register another way" expands.
- [ ] Larger text and high contrast buttons work; Tab key reaches every control with a visible focus ring.
- [ ] Step 2: empty names, a future birth date, a 5-digit phone, and a bad email each show a clear error. Email can be left blank.
- [ ] Step 3: answer all 7 questions; "Start questions over" resets. Typing "chest pain" shows the red 911 warning and does not block Continue.
- [ ] Step 4: upload a JPEG (fields appear for you to check, number is masked with a Show button); upload a .txt renamed to .jpg (rejected); "I don't have my card" works. Camera opens and Capture, Retake, Remove work (localhost only).
- [ ] Fallbacks: restart with `MOCK_OCR_MODE=blurry` and `failed` (manual entry opens); `MOCK_AI_MODE=unavailable` (review page says "Not AI-generated").
- [ ] Step 5: submit is refused without the required consent; works with it. AI consent is optional.
- [ ] Step 6: reference number shown, text says pre-registration only, no wait time or queue promise. Print works.
- [ ] Steps 7-8: all statuses Pending, destination says "Please follow the instructions provided by emergency department staff."

## Staff
- [ ] Wrong password shows a generic error; 5 wrong tries for one username locks it for 15 minutes.
- [ ] `demo-clerk`: can tick administrative steps and correct details; clinical boxes and destination are greyed out.
- [ ] `demo-nurse`: can tick clinical steps and set a destination; administrative boxes and corrections are greyed out.
- [ ] `demo-charge`: can do both.
- [ ] Search by part of the reference works; the list shows no names.
- [ ] Detail page labels patient-reported, AI-generated (simulated), and staff-verified sections; action log lists who did what.

## Back to the patient tab
- [ ] Refresh status on step 7 shows ticked steps; step 8 shows the destination staff chose.
