const $=s=>document.querySelector(s);
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let csrf="",me=null,cur=null,dests=[],timer=null;
const errText=j=>!j?"":j.errors?j.errors.map(e=>e.message).join("; "):(j.detail||"");
async function api(path,method="GET",body){const o={method,headers:{}};if(method!=="GET")o.headers["X-CSRF-Token"]=csrf;
 if(body!==undefined){o.headers["Content-Type"]="application/json";o.body=JSON.stringify(body)}
 const r=await fetch(path,o);let j=null;try{j=await r.json()}catch(e){}
 if(r.status===401&&path!=="/api/staff/login"){signedOut();throw new Error("Please sign in.")}
 if(!r.ok)throw new Error(errText(j)||("Error "+r.status));return j}
function signedOut(){me=null;cur=null;$("#app").classList.add("d-none");$("#login").classList.remove("d-none");$("#detail").textContent="Select a submission."}
function signedIn(j){me=j;csrf=j.csrf_token;$("#who").textContent=j.username+" ("+j.role.replace("_"," ")+")";
 $("#login").classList.add("d-none");$("#app").classList.remove("d-none");loadList();api("/api/staff/destinations").then(d=>dests=d.destinations)}
$("#lf").onsubmit=async e=>{e.preventDefault();$("#lerr").textContent="";
 try{signedIn(await api("/api/staff/login","POST",{username:$("#u").value,password:$("#p").value}));$("#p").value=""}catch(err){$("#lerr").textContent=err.message}};
$("#out").onclick=async()=>{try{await api("/api/staff/logout","POST",{})}catch(e){}signedOut()};
$("#q").oninput=()=>{clearTimeout(timer);timer=setTimeout(loadList,250)};
async function loadList(){const rows=await api("/api/staff/submissions"+($("#q").value?"?q="+encodeURIComponent($("#q").value):""));
 $("#list").innerHTML=rows.length?rows.map(r=>`<button type="button" class="list-group-item list-group-item-action" data-ref="${esc(r.reference)}"><strong>${esc(r.reference)}</strong><br><small>${new Date(r.submitted_at).toLocaleString()} · admin ${r.admin_done}/${r.admin_total}${r.clinical_assessment_complete?" · assessed":""}${r.destination?" · destination set":""}${r.missing.length?"<br><span class='text-danger'>Missing: "+esc(r.missing.join(", "))+"</span>":""}</small></button>`).join(""):"<div class='p-2'>No matches.</div>";
 $("#list").querySelectorAll("[data-ref]").forEach(b=>b.onclick=()=>openRef(b.dataset.ref))}
async function openRef(ref){cur=await api("/api/staff/submissions/"+encodeURIComponent(ref));render(cur)}
function render(d){const p=d.patient,ed=d.can_edit_patient?"":"disabled",dd=d.can_set_destination?"":"disabled";
 $("#detail").innerHTML=`<h2 class="h5">${esc(d.reference)} <small class="text-muted">submitted ${new Date(d.submitted_at).toLocaleString()}</small></h2>
<div class="tag-patient p-2 mb-2"><strong>Patient-reported (not verified)</strong><br>${esc(p.legal_first_name)} ${esc(p.legal_last_name)}${p.preferred_name?" (preferred: "+esc(p.preferred_name)+")":""} · born ${esc(p.date_of_birth)} · ${esc(p.phone)}${p.email?" · "+esc(p.email):""}<br>Completed for: ${esc(d.completing_for)}${p.accessibility_needs?" · Needs: "+esc(p.accessibility_needs):""}<br>Symptom answers:<ol class="mb-0">${d.symptom_answers.map(a=>"<li>"+esc(a)+"</li>").join("")||"<li>None</li>"}</ol></div>
<div class="tag-ai p-2 mb-2"><strong>${d.summary&&d.summary.source==="ai"?"AI-generated summary (simulated). Not a diagnosis or clinical assessment.":"Not AI-generated (patient answers laid out)"}</strong><br>${d.summary?esc(d.summary.text).replace(/\n/g,"<br>"):"None"}</div>
<div class="tag-staff p-2 mb-2"><strong>Staff-verified steps</strong> · Health card: ${esc(d.health_card_status.replace(/_/g," "))} (no number stored)${d.missing.length?" · <span class='text-danger'>Missing: "+esc(d.missing.join(", "))+"</span>":""}
${d.steps.map(s=>`<div class="form-check"><input class="form-check-input" type="checkbox" id="st-${s.step}" data-step="${s.step}" ${s.completed?"checked":""} ${s.can_edit?"":"disabled"}><label class="form-check-label" for="st-${s.step}">${esc(s.label)} <small class="text-muted">[${s.kind}]${s.completed?" by "+esc(s.by)+", "+new Date(s.at).toLocaleString():""}</small></label></div>`).join("")}</div>
<div class="tag-staff p-2 mb-2"><strong>Authorized destination</strong>${d.destination?" (by "+esc(d.destination.authorized_by)+")":""}
<select id="dsel" class="form-select my-1" aria-label="Destination" ${dd}><option value="">None: patient is told to follow staff instructions</option>${dests.map(x=>`<option ${d.destination&&d.destination.destination===x?"selected":""}>${esc(x)}</option>`).join("")}</select>
<input id="dins" class="form-control mb-1" maxlength="300" aria-label="Additional instruction" placeholder="Additional instruction (optional)" value="${esc(d.destination?d.destination.instructions:"")}" ${dd}>
<button id="dsave" class="btn btn-sm btn-primary" type="button" ${dd}>Save destination</button> <span id="dmsg" class="small" role="status"></span></div>
<details class="mb-2"><summary>Correct administrative details</summary><div class="row g-2 mt-1">
${[["legal_first_name","First name",p.legal_first_name],["legal_last_name","Last name",p.legal_last_name],["preferred_name","Preferred name",p.preferred_name],["date_of_birth","Date of birth",p.date_of_birth],["phone","Phone",p.phone],["email","Email",p.email],["accessibility_needs","Accessibility needs",p.accessibility_needs]].map(f=>`<div class="col-sm-6"><label class="form-label small" for="c-${f[0]}">${f[1]}</label><input class="form-control form-control-sm" id="c-${f[0]}" data-f="${f[0]}" ${f[0]==="date_of_birth"?'type="date"':""} value="${esc(f[2])}" ${ed}></div>`).join("")}
<div class="col-12"><button id="csave" class="btn btn-sm btn-outline-primary" type="button" ${ed}>Save corrections</button> <span id="cmsg" class="small" role="status"></span></div></div></details>
<div class="mb-2"><strong>Action log</strong><table class="table table-sm"><tbody>${d.audit.map(a=>`<tr><td>${new Date(a.at).toLocaleString()}</td><td>${esc(a.actor)}</td><td>${esc(a.event)}</td></tr>`).join("")}</tbody></table></div>`;
 $("#detail").querySelectorAll("[data-step]").forEach(c=>c.onchange=async()=>{
  try{await api(`/api/staff/submissions/${encodeURIComponent(cur.reference)}/steps/${c.dataset.step}`,"PUT",{completed:c.checked});loadList()}catch(e){alert(e.message)}openRef(cur.reference)});
 $("#dsave").onclick=async()=>{try{await api(`/api/staff/submissions/${encodeURIComponent(cur.reference)}/destination`,"PUT",{destination:$("#dsel").value||null,instructions:$("#dins").value||null});await openRef(cur.reference);loadList()}catch(e){$("#dmsg").textContent=e.message}};
 $("#csave").onclick=async()=>{const body={};$("#detail").querySelectorAll("[data-f]").forEach(i=>{const k=i.dataset.f,old=p[k]||"";if(i.value!==old)body[k]=i.value===""?null:i.value});
  if(!Object.keys(body).length){$("#cmsg").textContent="No changes.";return}
  try{await api(`/api/staff/submissions/${encodeURIComponent(cur.reference)}/patient`,"PATCH",body);await openRef(cur.reference)}catch(e){$("#cmsg").textContent=e.message}}}
api("/api/staff/me").then(signedIn).catch(()=>{});
