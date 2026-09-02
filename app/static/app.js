const input = document.getElementById('fileInput');
const preview = document.getElementById('preview');
const dropText = document.getElementById('dropText');
const btn = document.getElementById('identifyBtn');
const healthBadge = document.getElementById('healthBadge');
const acceptedPill = document.getElementById('acceptedPill');
let selectedFile = null;

fetch('/health').then(r=>r.json()).then(h=>{
  healthBadge.textContent = h.artifacts_ready ? '● model ready' : '○ training required';
  healthBadge.classList.add(h.artifacts_ready ? 'ready':'not-ready');
});

input.addEventListener('change', () => {
  selectedFile = input.files[0];
  if (!selectedFile) return;
  preview.src = URL.createObjectURL(selectedFile);
  preview.hidden = false; dropText.hidden = true; btn.disabled = false;
});

btn.addEventListener('click', async () => {
  if (!selectedFile) return;
  btn.disabled = true; btn.textContent = 'Embedding specimen…';
  const fd = new FormData(); fd.append('file', selectedFile);
  try {
    const res = await fetch('/predict', {method:'POST', body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Prediction failed');
    render(data);
  } catch (e) {
    document.getElementById('predictionArea').innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
    acceptedPill.textContent = 'no fabricated result';
  } finally {
    btn.disabled = false; btn.textContent = 'Identify specimen';
  }
});

function render(data){
  const accepted = data.accepted || {};
  acceptedPill.textContent = accepted.taxon ? `${accepted.rank}: ${accepted.taxon}` : 'needs morphology';
  const area = document.getElementById('predictionArea');
  area.className='';
  area.innerHTML = ['family','genus','species'].map(rank => {
    const cs = data.predictions[rank] || [];
    if (!cs.length) return '';
    return `<div class="rank"><div class="rank-title"><span>${rank}</span><span>model score</span></div>${cs.slice(0,4).map(c=>candidate(c)).join('')}</div>`;
  }).join('');

  const n = document.getElementById('neighbours'); n.className='thumb-grid';
  n.innerHTML = (data.similar_specimens||[]).map(x=>`<div class="thumb">${x.image_url?`<img loading="lazy" src="${escapeAttr(x.image_url)}" alt="reference specimen">`:''}<div class="meta"><strong>${escapeHtml(x.species||x.genus||x.family||'reference')}</strong>${(x.similarity*100).toFixed(1)}% visual similarity<br>${escapeHtml(x.source||'')} ${x.photo_license?`· ${escapeHtml(x.photo_license)}`:''}</div></div>`).join('') || '<div class="empty">No reference index yet.</div>';

  const d = document.getElementById('diagnostics'); d.className='';
  const chars = data.diagnostics?.characters || [];
  const keys = data.diagnostics?.keys || [];
  d.innerHTML = `${chars.length?`<ul class="chars">${chars.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul>`:'<p class="empty">No family-specific morphology notes yet.</p>'}${keys.length?`<div class="keys"><strong>Keys & references</strong>${keys.map(k=>`<p><em>${escapeHtml(k.title)}</em><br><span class="micro">${escapeHtml(k.type||'')}</span></p>`).join('')}</div>`:''}`;
}
function candidate(c){ const p=Math.max(0,Math.min(1,c.probability)); return `<div class="candidate"><div><div class="name">${escapeHtml(c.taxon)}</div><div class="bar"><i style="width:${(p*100).toFixed(1)}%"></i></div></div><div class="score">${(p*100).toFixed(1)}%</div></div>`; }
function escapeHtml(s){return String(s??'').replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));}
function escapeAttr(s){return escapeHtml(s);}
