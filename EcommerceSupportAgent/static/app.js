const chat = document.getElementById("chat");
const q = document.getElementById("q");
let pending = null; // {case_id, order_id}

function esc(s){ return (s||"").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'})[c]); }
function md(s){
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>');
}

function bubble(role, html, meta){
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.innerHTML = html + (meta ? `<div class="meta">${meta}</div>` : "");
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
  return d;
}

function preset(t){ q.value = t; q.focus(); }
function reset(){ chat.innerHTML=""; pending=null; }

async function send(){
  const text = q.value.trim();
  if (!text) return;
  bubble("user", esc(text));
  q.value = "";
  bubble("system", "…thinking");
  const t = chat.lastChild;
  try {
    const r = await fetch("/api/chat", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({message:text})
    });
    const j = await r.json();
    t.remove();
    render(j);
  } catch(e){
    t.innerHTML = "Network error: " + esc(String(e));
  }
}

function pill(txt, cls){ return `<span class="pill ${cls||''}">${txt}</span>`; }

function render(j){
  const intent = j.intent || "?";
  const cat = j.category || "";
  const pills = [
    pill(intent),
    pill(cat, cat === "irreversible" ? "write" : "read"),
    pill("case " + (j.case_id||"").slice(0,8)),
  ];
  if (j.safety_flags && j.safety_flags.length) pills.push(pill("safety⚠", "human"));
  if (j.awaiting_human) pills.push(pill("HUMAN GATE", "human"));

  bubble("bot", md(j.reply||""), pills.join(" "));

  if (j.awaiting_human && j.proposed_action){
    pending = { case_id: j.case_id, order_id: j.proposed_action.order_id };
    const box = bubble("system",
      `<b>Human review required</b><br/>Order: <code>${pending.order_id}</code>
       · Refund: <b>$${(j.proposed_action.refund_amount||0).toFixed(2)}</b>
       · Payment: <code>${j.proposed_action.payment_id||"-"}</code><br/>
       <button onclick="humanDecide(true)">Approve refund</button>
       <button class="secondary" onclick="humanDecide(false)">Deny</button>`);
  }
}

async function humanDecide(approve){
  if (!pending) return;
  const r = await fetch("/api/human/approve", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({...pending, approve})
  });
  const j = await r.json();
  render({...j, intent:"return_refund", category:"irreversible"});
  pending = null;
}
