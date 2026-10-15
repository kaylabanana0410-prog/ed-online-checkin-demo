"""Workflow steps and role permissions. Only staff roles can change these: the AI has no path to them."""
STEPS = {  # step -> (kind, label)
    "identity_confirmed": ("administrative", "Identity confirmed by staff"),
    "health_card_verified": ("administrative", "Health card verified through an authorized process"),
    "missing_info_resolved": ("administrative", "Missing administrative information resolved"),
    "wristband_issued": ("administrative", "Hospital wristband issued by staff"),
    "summary_reviewed": ("clinical", "Symptom summary reviewed by staff"),
    "clinical_assessment_complete": ("clinical", "Clinical assessment completed by authorized staff"),
}
ROLES = ("clerk", "nurse", "charge_nurse")
PERMS = {
    "view": set(ROLES),
    "administrative": {"clerk", "charge_nurse"},
    "clinical": {"nurse", "charge_nurse"},
    "destination": {"nurse", "charge_nurse"},
    "edit_patient": {"clerk", "charge_nurse"},
}

def step_view(sub):
    done = {s.step: s for s in sub.steps}
    return [{"step": k, "label": lab, "kind": kind, "completed": bool(k in done and done[k].completed),
             "by": done[k].completed_by if k in done and done[k].completed else None,
             "at": done[k].updated_at if k in done and done[k].completed else None}
            for k, (kind, lab) in STEPS.items()]
