const S={n:1,chat:[],qi:0,hc:"",cardState:"none",authorized:false,ref:""};
const TOTAL=8;
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function show(n){S.n=n;if(n!==4)stopCam();if(n===7||n===8)refreshStatus();$$(".step").forEach(e=>e.classList.toggle("active",+e.dataset.n===n));
 $("#bar").style.width=(n/TOTAL*100)+"%";$("#stepLabel").textContent=`Step ${n} of ${TOTAL}`;
 if(n===3&&!S.started)startChat(); if(n===5)review(); window.scrollTo(0,0);}
$$("[data-go]").forEach(b=>b.onclick=()=>show(+b.dataset.go));
$("#tText").onclick=()=>document.body.classList.toggle("big");
$("#tCon").onclick=()=>document.body.classList.toggle("contrast");
$("#f2").onsubmit=e=>{e.preventDefault();let ok=true;
 const bad=(id,c)=>{$(id).classList.toggle("is-invalid",!c);if(!c)ok=false};
 bad("#fn",$("#fn").value.trim());bad("#ln",$("#ln").value.trim());
 const d=new Date($("#dob").value);bad("#dob",$("#dob").value&&d<=new Date()&&d.getFullYear()>1900);
 bad("#ph",/^\D*(\d\D*){10}$/.test($("#ph").value));
 bad("#em",!$("#em").value||/^\S+@\S+\.\S+$/.test($("#em").value));
 if(ok)show(3);};
function add(c,t){const d=document.createElement("div");d.className="msg "+c;d.textContent=t;$("#chat").append(d);$("#chat").scrollTop=1e9}
function bot(t){add("bot",t)}
async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error(r.status);return r.json()}
const post=(p,b)=>api(p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)});
const DOWN="<strong>The symptom assistant is unavailable. Tell staff about your symptoms in person. If this may be an emergency, call 911.</strong>";
function showWarn(msgs){const w=$("#warn");w.classList.remove("d-none");w.innerHTML=(Array.isArray(msgs)?msgs.map(m=>"<p class='mb-1'><strong>"+esc(m)+"</strong></p>").join(""):msgs)}
async function startChat(){S.started=true;
 try{S.Q=(await api("/api/symptoms/questions")).questions;bot(S.Q[0])}
 catch(e){showWarn(DOWN);$("#to4").disabled=false}}
$("#redo").onclick=()=>{S.chat=[];S.started=false;S.Q=null;$("#chat").innerHTML="";$("#warn").classList.add("d-none");$("#to4").disabled=true;startChat()};
$("#chatForm").onsubmit=async e=>{e.preventDefault();const v=$("#ans").value.trim();if(!v||!S.Q)return;$("#ans").value="";
 add("me",v);S.chat.push(v);
 try{const t=await post("/api/symptoms/turn",{answers:S.chat});
  if(t.emergency||t.degraded)showWarn(t.messages);
  if(t.next_question)bot(t.next_question);else{bot("Thank you. A preliminary summary appears on the review page. It is not a diagnosis.");$("#to4").disabled=false}
 }catch(err){showWarn(DOWN);$("#to4").disabled=false}};
let stream=null,blob=null;
function stopCam(){if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}$("#camBox").classList.add("d-none")}
function clearImg(){blob=null;const u=$("#prev").getAttribute("src");if(u)URL.revokeObjectURL(u);$("#prev").removeAttribute("src");$("#prevBox").classList.add("d-none");$("#upProg").classList.add("d-none")}
function setCard(state,msg,box){S.cardState=state;$("#cardMsg").textContent=msg;$("#cardBox").classList.toggle("d-none",!box)}
function setBlob(b){blob=b;$("#prev").src=URL.createObjectURL(b);$("#prevBox").classList.remove("d-none");$("#cardMsg").textContent=""}
$("#scan").onclick=async()=>{clearImg();
 if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)return setCard("none","The camera is not available here. Upload a photo or enter the details manually.",false);
 try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});$("#cam").srcObject=stream;await $("#cam").play();$("#camBox").classList.remove("d-none")}
 catch(e){setCard("none","Camera permission was not granted. Upload a photo or enter the details manually.",false)}};
$("#camCancel").onclick=stopCam;
$("#snap").onclick=()=>{const v=$("#cam"),c=document.createElement("canvas");c.width=v.videoWidth;c.height=v.videoHeight;c.getContext("2d").drawImage(v,0,0);
 c.toBlob(b=>{stopCam();setBlob(b)},"image/jpeg",0.9)};
$("#up").onchange=e=>{const f=e.target.files[0];e.target.value="";if(!f)return;clearImg();
 if(!["image/jpeg","image/png"].includes(f.type))return setCard("none","Use a JPEG or PNG image.",false);
 if(f.size>5e6)return setCard("none","That file is over 5 MB. Choose a smaller image.",false);
 setBlob(f)};
$("#retake").onclick=()=>{clearImg();$("#scan").click()};
$("#rmImg").onclick=()=>{clearImg();setCard("none","Image removed.",false)};
$("#useImg").onclick=()=>{if(!blob)return;const fd=new FormData();fd.append("file",blob,"card.jpg");
 const x=new XMLHttpRequest();x.open("POST","/api/documents/card-scan");
 $("#upProg").classList.remove("d-none");$("#upBar").style.width="0";
 x.upload.onprogress=e=>{if(e.lengthComputable)$("#upBar").style.width=(e.loaded/e.total*100)+"%"};
 x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){}
  $("#upProg").classList.add("d-none");
  if(x.status!==200)return setCard("manual",(j.detail||"We could not read that image.")+" You can retake it or enter the details manually.",true);
  const f=Object.fromEntries(j.fields.map(r=>[r.name,r]));
  $("#hc").value=f.health_number?f.health_number.value:"";$("#vc").value=f.version_code?f.version_code.value:"";$("#exp").value=f.expiry_date?f.expiry_date.value:"";
  S.hc=$("#hc").value.replace(/\D/g,"");
  $("#confBadge").textContent=j.fields.map(r=>r.name.replace("_"," ")+": "+r.confidence_label+" confidence").join(" · ");
  clearImg();setCard(j.manual_entry_needed?"manual":"ocr",j.message,true)};
 x.onerror=()=>{$("#upProg").classList.add("d-none");setCard("manual","Could not reach the server. Enter the details manually.",true)};
 x.send(fd)};
$("#manual").onclick=()=>{clearImg();setCard("manual","Enter your details manually.",true)};
$("#nocard").onclick=()=>{clearImg();S.hc="";setCard("unavailable","No problem. Staff will help with insurance information in person.",false)};
$("#hcShow").onclick=()=>{const h=$("#hc"),show=h.type==="password";h.type=show?"text":"password";$("#hcShow").textContent=show?"Hide":"Show"};
$("#hc").oninput=()=>{S.hc=$("#hc").value.replace(/\D/g,"")};
["#hc","#vc","#exp"].forEach(i=>$(i).addEventListener("input",()=>{if(S.cardState==="ocr_confirmed")S.cardState="ocr"}));
$("#confirmCard").onclick=async()=>{S.hc=$("#hc").value.replace(/\D/g,"");
 try{const j=await post("/api/documents/card-validate",{health_number:S.hc,version_code:$("#vc").value||null});
  $("#valMsg").textContent=(j.format_valid?"The format looks valid. ":"The format looks wrong. Please check the number. ")+j.message;
  if(j.format_valid&&S.cardState==="ocr")S.cardState="ocr_confirmed"}
 catch(e){$("#valMsg").textContent="Could not run the format check. You can still continue."}};
const mask=h=>h?"******"+h.slice(-4):"not provided";
async function review(){const cs={none:"Not provided",ocr:"Read from a card photo, not yet confirmed by you",ocr_confirmed:"Read from a card photo and confirmed by you (not verified)",manual:"Entered manually, not verified",unavailable:"Card unavailable"}[S.cardState];
 $("#review").innerHTML=`<div class="verified-tag mb-2"><strong>Patient-reported details</strong><br>${esc($("#fn").value)} ${esc($("#ln").value)} · born ${esc($("#dob").value)} · ${esc($("#ph").value)}</div>
 <div class="ai-tag mb-2" id="sum">Preparing symptom summary…</div>
 <div class="verified-tag"><strong>Health card</strong>: ${cs}; number ${mask(S.hc)}. Verification: simulated, not performed.</div>`;
 const plain=S.chat.map(esc).join("<br>")||"No answers yet";
 try{const j=await post("/api/symptoms/summary",{answers:S.chat,ai_consent:$("#c2").checked});
  $("#sum").innerHTML=`<strong>${j.source==="ai"?"AI-generated summary (simulated)":"Patient-reported answers (not AI-generated)"}</strong><br>${esc(j.summary).replace(/\n/g,"<br>")}<br><small>${esc(j.disclaimer)}</small>`;
  if(j.emergency||j.degraded)showWarn(j.messages)}
 catch(e){$("#sum").innerHTML="<strong>Patient-reported answers (summary unavailable)</strong><br>"+plain}}
$("#c2").onchange=review;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
S.key=crypto.randomUUID().replace(/-/g,"");
$("#submit").onclick=async()=>{
 if(!$("#c1").checked){$("#err5").textContent="Required consent is needed to submit.";return}
 $("#err5").textContent="";$("#submit").disabled=true;
 const cs={none:"not_provided",ocr:"scanned_unconfirmed",ocr_confirmed:"scanned_confirmed",manual:"manual_entry",unavailable:"unavailable"}[S.cardState];
 const body={completing_for:$("#who").value,legal_first_name:$("#fn").value,legal_last_name:$("#ln").value,preferred_name:$("#pn").value||null,date_of_birth:$("#dob").value,phone:$("#ph").value,email:$("#em").value||null,accessibility_needs:$("#needs").value||null,symptom_answers:S.chat,health_card_status:cs,consent_registration:true,consent_ai_processing:$("#c2").checked,idempotency_key:S.key};
 try{const r=await fetch("/api/preregistrations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await r.json();
  if(!r.ok){$("#err5").textContent=r.status===422?"Please fix: "+j.errors.map(e=>e.message).join("; "):"Submission failed. Try again or register in person.";return}
  S.ref=j.reference;S.token=j.access_token;$("#ref").textContent=j.reference;$("#when").textContent="Submitted "+new Date(j.submitted_at).toLocaleString();show(6);
 }catch(e){$("#err5").textContent="Cannot reach the server. Register in person if this continues."}
 finally{$("#submit").disabled=false}};
async function refreshStatus(){if(!S.token)return;
 try{const j=await api("/api/preregistrations/"+encodeURIComponent(S.ref),{headers:{"X-Access-Token":S.token}});
  $("#steps7").innerHTML=j.steps.map(x=>`<li class="list-group-item d-flex justify-content-between">${esc(x.label)} <span class="badge ${x.completed?"text-bg-success":"text-bg-secondary"}">${x.completed?"Done":"Pending"}</span></li>`).join("");
  $("#dest").innerHTML=j.destination?`<strong>Staff-authorized destination:</strong> ${esc(j.destination)}${j.destination_instructions?"<br>"+esc(j.destination_instructions):""}`:"Please follow the instructions provided by emergency department staff."}
 catch(e){$("#steps7").innerHTML="<li class='list-group-item'>Status could not be loaded. Please ask staff.</li>"}}
$("#refresh").onclick=refreshStatus;$("#refresh8").onclick=refreshStatus;
show(1);
$("#printBtn").onclick=()=>window.print();
