import {renderResearch,stopResearch} from './research.js';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = (value) => `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
const percent = (p) => p == null ? 'unknown' : `${(p * 100).toFixed(p > .01 ? 2 : 6)}%`;
const number = (n, places=3) => n == null ? '—' : Number(n).toFixed(places);
const names = {choice:'Choice',boolean:'Yes / no',score:'Rubric score',candidates:'Grammar branches',controller:'State controller',rerank:'Source ranking',graph:'Document graph',scene:'Scene search',wire:'Token inspector',speculation:'Draft & target',performance:'Latency frontier'};
let catalog, page, aborter, generation = 0, last = null, steps = [], tokenEntries = [];

function field(label, html, note='') {
  return `<label class="field"><span>${esc(label)}</span>${html}${note ? `<small>${esc(note)}</small>` : ''}</label>`;
}
function textField(key, label, value, rows=3) {
  return field(label, `<textarea id="input-${key}" rows="${rows}">${esc(value)}</textarea>`);
}
function callout(title, text, style='') {
  return `<div class="callout ${style}"><strong>${esc(title)}</strong><p>${esc(text)}</p></div>`;
}
function stat(label, value) { return `<div class="stat"><span>${esc(label)}</span><b>${esc(value)}</b></div>`; }
function bar(label, weight, annotation, muted=false) {
  return `<div><div class="bar-label"><span>${esc(label)}</span><strong>${esc(annotation ?? percent(weight))}</strong></div><div class="bar-track"><div class="bar-fill ${muted?'muted':''}" style="width:${Math.max(0,Math.min(100,(weight||0)*100))}%"></div></div></div>`;
}
function details(label, value) { return `<details><summary>${esc(label)}</summary>${json(value)}</details>`; }

function navigate(name, replace=false) {
  stopResearch();
  if (!catalog.pages.some(p => p.id === name)) name = 'choice';
  generation++;
  aborter?.abort();
  page = structuredClone(catalog.pages.find(p => p.id === name));
  last = null;
  steps = [];
  tokenEntries = [];
  if (replace) history.replaceState({}, '', `/lab/${name}`); else history.pushState({}, '', `/lab/${name}`);
  document.title = `${page.name||names[name]} / Strata Control Lab`;
  $('nav').innerHTML = catalog.pages.map((p,i) => `${i===0||i===11?`<div class="nav-section">${i===0?'Foundations':'Research instruments'}</div>`:''}<a href="/lab/${p.id}" data-page="${p.id}" class="${p.id===name?'active':''}" ${p.id===name?'aria-current="page"':''}><span>${String(i+1).padStart(2,'0')}</span>${p.name||names[p.id]}</a>`).join('');
  $('nav').querySelector('.active')?.scrollIntoView({block:'nearest'});
  document.body.classList.toggle('research-page',page.section==='research');
  $('eyebrow').textContent = page.eyebrow;
  $('title').textContent = page.title;
  $('intro').textContent = page.simple;
  $('detail').textContent = page.detail;
  $('next').textContent = page.next_gate;
  $('tags').innerHTML = page.features.map(t=>`<span>${esc(t)}</span>`).join('');
  $('math').innerHTML = `<p><b>Raw token score:</b> log p = logit − logsumexp(all target logits). It is measured before sampling and grammar masking.</p><p><b>Candidate weight:</b> exp(log pᵢ − logsumexp(candidate log p)). This conditions on the listed paths and is not a calibrated truth probability.</p><p><b>Whole path:</b> log P(path) = Σ log P(tokenₜ | prompt, preceding candidate tokens). Path scores include the displayed terminator, where used; no EOS score is invented.</p><p><b>Derived measures:</b> entropy = −Σ p log₂ p; margin = p₁ − p₂; Choice peakedness = (max p − 1/n)/(1 − 1/n). These summarize the same distribution. They add no independent evidence.</p><p><b>Rating:</b> E[value] = Σ pᵢ valueᵢ. A measurement vector may feed a rule, optimizer, or observer; multiplying related judgments does not establish joint reliability.</p><p><a href="https://docs.typesafe.ai/primitives" target="_blank" rel="noopener">TypeSafe primitives</a> provide a useful interface reference. This lab is a generative Strata baseline, not Jev’s trained decision model or a Jev benchmark.</p>`;
  renderFields();
  $('result').innerHTML = `<div class="empty"><span class="empty-icon">∴</span><h3>Make the next step visible.</h3><p>Run the example to see the answer, its alternatives, and the rule connecting them.</p></div>`;
  $('timeline').innerHTML = '<li class="subtle">The trace will appear here.</li>';
  $('download').disabled = true;
  status('Ready');
  busy(false);
  sourceNote();
}

function renderFields() {
  const d = page.defaults;
  let html = '';
  if(page.section==='research'&&!Object.keys(d).length)html+='<div class="instrument-intro"><span>01 / RUN</span><h3>Open the experiment.</h3><p>Load the complete trajectory, then use its controls to step, compare and inspect.</p><div class="mini-loop" aria-hidden="true"><i>state</i><b>→</b><i>rules</i><b>→</b><i>action</i></div><p>The built-in run is reproducible offline. Every model call appears in the receipt.</p></div>';
  if (d.state !== undefined) html += textField('state', page.id==='scene'?'Describe the scene':'State · what is happening?', d.state);
  if (d.question !== undefined) html += textField('question', 'Ask one clear question', d.question, 2);
  if (d.choices) {
    html += `<div class="field"><span>Answer definitions${page.id==='score'?' & values':''}</span>`;
    html += d.choices.map((c,i)=>`<div class="option-edit"><b>${c.label}</b><input id="choice-${i}" type="text" aria-label="Answer ${c.label}" value="${esc(c.description)}">${page.id==='score'?`<input id="value-${i}" aria-label="Value ${c.label}" type="number" step="0.1" value="${c.value}">`:''}</div>`).join('')+'</div>';
  }
  if (d.strategy) html += field('How to measure', `<select id="input-strategy"><option value="complete">Complete labels · one call each</option><option value="fast">Fast probe · one target row</option></select>`, 'The fast probe reports missing alternatives as unknown.');
  if (d.groups) d.groups.forEach((g,i)=>{html += textField(`group-${i}`, `${g.name} · one answer per line`, g.answers.join('\n'));});
  if (d.sources) d.sources.forEach((s,i)=>{html += textField(`source-${i}`, s.id+' · immutable source text', s.text);});
  if (d.parallel) html += field('Concurrent HTTP requests', `<select id="input-parallel"><option value="1">1 · serial</option><option value="2">2</option><option value="4">4</option></select>`, 'The existing engine still serializes inference.');
  if (d.controller_state) html += field('Current simulated state', `<select id="input-controller_state">${['unread','inspected','edited','verified','done'].map(s=>`<option value="${s}">${s}</option>`).join('')}</select>`, 'Each click completes one decision. Use Apply step to advance.');
  if (d.threshold !== undefined) html += field(page.id==='graph'?'Minimum useful edge weight':'Hold when allowed-action weight is below', `<input type="range" id="input-threshold" min="${page.id==='graph'?.05:0}" max="${page.id==='graph'?.95:1}" step="0.05" value="${d.threshold}"><output id="threshold-label">${d.threshold.toFixed(2)}</output>`);
  if (d.case) html += field('Contract example', `<select id="input-case">${['decision','router','ambiguity','stream','grammar','json-schema','reasoning-json','tool-call','tool-result','selected-only'].map(c=>`<option value="${c}" ${c===d.case?'selected':''}>${c}</option>`).join('')}</select>`, 'Force Z is the outside-top-N correctness check. The other pages show applications.');
  if (d.repeats) html += field('Repetitions per path', '<select id="input-repeats"><option value="3">3 · recorded default</option><option value="1">1 · quick</option><option value="5">5 · live</option></select>', 'A warm-up plus six paths. JSON produces a longer answer.');
  if (page.id==='speculation') html += '<p class="subtle">Open the native receipts for target-only, MTP, suffix, and coupled decoding. This page replays evidence; it has no live diagnostics endpoint.</p>';
  $('fields').innerHTML = html;
  $('input-threshold')?.addEventListener('input', e => {$('threshold-label').textContent=Number(e.target.value).toFixed(2);});
}

function values() {
  const d=page.defaults, out={mode:$('mode').value};
  for (const key of ['state','question','strategy','controller_state','case']) if ($(`input-${key}`)) out[key]=$(`input-${key}`).value;
  for (const key of ['threshold','parallel','repeats']) if ($(`input-${key}`)) out[key]=Number($(`input-${key}`).value);
  if (d.choices) out.choices=d.choices.map((c,i)=>({...c, description:$(`choice-${i}`).value, ...(page.id==='score'?{value:Number($(`value-${i}`).value)}:{})}));
  if (d.groups) out.groups=d.groups.map((g,i)=>({...g,answers:$(`input-group-${i}`).value.split('\n').filter(s=>s.length)}));
  if (d.sources) out.sources=d.sources.map((s,i)=>({...s,text:$(`input-source-${i}`).value}));
  return out;
}

function sourceNote() {
  if(page.data_kind==='analytic'){$('source-note').textContent='ANALYTICAL INSTRUMENT / disclosed synthetic inputs or measured receipts with user-controlled assumptions. No model inference.';$('run-note').textContent='The dials recompute the stated formulas locally. Live mode does not add a model call to this instrument.';return;}
  $('source-note').textContent = page.id==='speculation' ? 'NATIVE EVIDENCE / original target, draft, and replay paths, labeled separately.' : $('mode').value==='recorded' ? 'RECORDED NATIVE RUN / exact built-in inputs; measured model results replayed without running inference.' : 'LIVE MODEL / requests go to the Strata address configured on this lab server.';
  $('run-note').textContent = $('mode').value==='recorded' ? 'A recorded run needs no model. Change to Live to try your own inputs.' : 'Stop closes the current request. Strata owns cancellation and engine-output draining.';
}
function status(text, cls='') { $('status').textContent=text; $('status').className='badge '+cls; }
function busy(value) { $('run').disabled=value; $('stop').disabled=!value; $('reset').disabled=value; $('mode').disabled=value;document.body.classList.toggle('is-running',value); }

function addStep(data) {
  let li=$('step-'+data.id);
  if (!steps.length) $('timeline').innerHTML='';
  if (!li) {li=document.createElement('li');li.id='step-'+data.id;$('timeline').append(li);}
  const request=data.request||steps.find(s=>s.id===data.id&&s.request)?.request;
  li.innerHTML=`<span class="step-time">${data.status==='completed'?number(data.wall_ms,0)+' ms':'IN PROGRESS'}</span><b>${data.id}. ${esc(data.title)}</b> · ${esc(data.status)}${details('Inspect request',request)}${data.response?details('Inspect response',data.response):''}`;
  steps.push(data);
  if (data.status==='running') $('result').innerHTML=`<div class="request-progress"><span class="spinner"></span><span>${esc(data.title)}<br><small>Every completed step appears in the receipt below.</small></span></div>`;
}

function distribution(data, target=$('result')) {
  const top=data.rows.filter(r=>r.weight!=null).sort((a,b)=>b.weight-a.weight)[0];
  const summary = !data.complete ? callout('Some labels are outside top-N',data.message,'amber') : data.yes_weight!=null ? callout(percent(data.yes_weight)+' Yes weight','Relative to the explicit Yes / No answers.') : data.statistics?.expected_score!=null ? callout(number(data.statistics.expected_score),'Expected rubric value. Inspect the levels before acting.') : callout(`${top.label} · ${top.description}`,'The model’s strongest preference among these definitions.');
  target.innerHTML = summary+`<div class="view-control"><span>Answer distribution</span><select id="score-view" aria-label="Probability display"><option value="weight">Relative to listed answers</option><option value="raw_probability">Raw vocabulary probability</option></select></div><div id="distribution-bars" class="bars"></div>`;
  const draw=()=>{$('distribution-bars').innerHTML=data.rows.map(r=>bar(`${r.label} · ${r.description}`,r[$('score-view').value],null,r.allowed===false)).join('');};
  draw(); $('score-view').addEventListener('change',draw);
  if (data.statistics) target.insertAdjacentHTML('beforeend',`<div class="stats">${stat('Top-to-next margin',percent(data.statistics.margin))}${stat('Entropy',number(data.statistics.entropy_bits)+' bits')}${stat('Derived peakedness',number(data.statistics.peakedness))}</div>`);
  target.insertAdjacentHTML('beforeend', `<p class="subtle">${esc(data.semantics||'Unknown is not zero. Complete-label scoring can measure each omitted label.')}</p>${details('Exact measured scores and prompt',data)}`);
}

function tokenView(entries, target) {
  if (!entries.length) { target.innerHTML='<p class="subtle">No scored answer content in this response. Inspect its tool or reasoning fields below.</p>'; return; }
  target.innerHTML='<span class="field-label">Select a generated token</span><div class="token-strip"></div><div class="token-readout"></div>';
  const strip=target.querySelector('.token-strip'), readout=target.querySelector('.token-readout');
  entries.forEach((e,i)=>{const button=document.createElement('button');button.type='button';button.className='token';button.textContent=e.token.replace(/\n/g,'↵').replace(/\t/g,'⇥');button.title=`Token ${i}: raw logprob ${e.logprob}`;button.addEventListener('click',()=>{strip.querySelectorAll('button').forEach(b=>b.classList.remove('selected'));button.classList.add('selected');readout.innerHTML=`<p class="subtle">Token ${i} · bytes [${e.bytes.join(', ')}] · raw logprob ${number(e.logprob,8)}</p>${bar('Selected '+JSON.stringify(e.token),Math.exp(e.logprob))}<div class="bars">${e.top_logprobs.map(t=>bar(JSON.stringify(t.token),Math.exp(t.logprob))).join('')}</div><p class="subtle">Alternatives are conditioned on this exact preceding token path. They need not satisfy the grammar. ↵ marks a newline.</p>`;});strip.append(button);});
  strip.querySelector('button').click();
}

function candidates(data) {
  $('result').innerHTML=callout(data.groups.slice().sort((a,b)=>b.weight-a.weight)[0].name,'Group weight sums the measured disjoint paths in that group.')+`<div class="bars">${data.groups.map(g=>bar(g.name,g.weight)).join('')}</div><p class="subtle">${esc(data.semantics)}</p><label class="field"><span>Walk one candidate path</span><select id="path-select">${data.paths.map((p,i)=>`<option value="${i}">${esc(p.text.trim())} · ${percent(p.weight)}</option>`).join('')}</select></label><div id="path-tokens"></div>${details('Both finite GBNF grammars',data.groups)}${details('Greedy union result versus best complete path',{union_generation:data.generated.text,best_path:data.best_path,note:'A locally greedy constrained choice need not maximize the probability of a whole multi-token path.'})}`;
  const draw=()=>{const path=data.paths[Number($('path-select').value)];tokenView(path.tokens,$('path-tokens'));let cumulative=0;const calculation=path.tokens.map(t=>{cumulative+=t.logprob;return {token:t.token,conditional_probability:Math.exp(t.logprob),cumulative_logprob:cumulative,cumulative_probability:Math.exp(cumulative)};});$('path-tokens').insertAdjacentHTML('afterbegin',`<div class="stats">${stat('Raw token-path probability',percent(path.path_probability))}${stat('Weight in this candidate set',percent(path.weight))}${stat('Tokens, including newline',path.token_count)}</div>${details('Follow the multiplication through the path',calculation)}`);};
  $('path-select').addEventListener('change',draw);draw();
}

function controller(data) {
  if(data.done && !data.action){$('result').innerHTML=callout('Task complete','Reset the state to replay the decisions.');return;}
  $('result').innerHTML=callout(data.held?'Decision held':`Next action: ${data.action}`,data.held?'The current threshold requires a pause.':'A legal next step, selected under the current state’s grammar.',data.held?'amber':'')+`<div class="state-steps">${['unread','inspected','edited','verified','done'].map(s=>`<span class="state-step ${s===data.state?'current':''}">${s}</span>`).join('')}</div><pre>${esc(data.observation)}</pre><div class="bars">${data.measure.rows.map(r=>bar(`${r.action} · ${r.allowed?'allowed':'blocked by state'}`,r.weight,null,!r.allowed)).join('')}</div><div class="decision-path"><div>${esc(data.state)}</div><span>→</span><div>${esc(data.next_state)}</div></div><button class="primary" id="apply-step" ${data.held?'disabled':''}>Apply step to simulated state →</button><p class="subtle">Nothing runs on your OS. The next click sends a new request with the updated state and grammar.</p>${details('The exact legal grammar',data.grammar)}${details('All raw label measurements',data.measure)}`;
  $('apply-step').insertAdjacentHTML('beforebegin',`<p class="subtle">Selected action’s weight among legal choices: <b>${percent(data.legal_conditional_weight)}</b> · required: <b>${percent(data.threshold??0)}</b>.</p>`);
  $('apply-step').addEventListener('click',()=>{$('input-controller_state').value=data.next_state;$('apply-step').disabled=true;$('apply-step').textContent='Applied · run the next decision';});
}

function rerank(data) {
  $('result').innerHTML=callout('Useful evidence, without rewriting','Each source keeps its own relevance distribution.')+data.sources.map(s=>`<article class="source-card"><div class="source-head"><h3>${esc(s.id)}</h3><strong>${number(s.score)}</strong></div><p>${esc(s.text)}</p><div class="bars">${s.measure.rows.map(r=>bar(r.description,r.weight)).join('')}</div></article>`).join('')+`<p class="subtle">${esc(data.inference)}. HTTP concurrency: ${data.concurrent_http}.</p>`;
}

function graph(data) {
  const coords={B17:[110,65],B18:[350,65],B19:[110,190],B20:[350,190]};
  const chosen=new Set(data.solver.selected.map(e=>e.source+'-'+e.target+'-'+e.relation));
  let svg='<svg viewBox="0 0 460 255" class="graph-svg" role="img" aria-label="Text block graph; solid green edges are selected"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#31765e"/></marker></defs>';
  for(const e of data.edges){const a=coords[e.source],b=coords[e.target],active=chosen.has(e.source+'-'+e.target+'-'+e.relation);const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),ux=dx/length,uy=dy/length;const edge=Math.min(Math.abs(35/(ux||1e-9)),Math.abs(21/(uy||1e-9)))+5;const x1=a[0]+ux*edge,y1=a[1]+uy*edge,x2=b[0]-ux*edge,y2=b[1]-uy*edge;const bend=dy===0?(dx>0?-13:13):0;svg+=`<path d="M${x1} ${y1} Q${(x1+x2)/2} ${(y1+y2)/2+bend} ${x2} ${y2}" fill="none" stroke="${active?'#31765e':'#d3dbce'}" stroke-width="${active?2:1}" ${active?'marker-end="url(#arrow)"':'stroke-dasharray="5 5"'}><title>${esc(e.source+' → '+e.target+': '+percent(e.weight))}</title></path>`;}
  for(const [id,[x,y]] of Object.entries(coords))svg+=`<rect x="${x-35}" y="${y-21}" width="70" height="42" rx="8" fill="#fff" stroke="#bccdb5"/><text x="${x}" y="${y+4}" text-anchor="middle">${id}</text>`;
  svg+='</svg>';
  $('result').innerHTML=callout(`${data.solver.selected.length} legal links retained`,'Solid links are selected. Dashed alternatives stay available for inspection.')+svg+`<div class="wide-scroll"><table class="small-table"><thead><tr><th>Link</th><th>Weight</th><th>Decision</th></tr></thead><tbody>${data.edges.map(e=>`<tr><td>${e.source} → ${e.target}<br>${e.relation}</td><td>${percent(e.weight)}</td><td>${chosen.has(e.source+'-'+e.target+'-'+e.relation)?'retained':'alternative'}</td></tr>`).join('')}</tbody></table></div>${data.blocks.map(b=>`<p class="subtle"><b>${b.id} · ${esc(b.location)}</b><br>${esc(b.text)}</p>`).join('')}${details('Exact solver objective and constraints',data.solver)}`;
}

function sceneSVG(s) {
  const colors={blue:'#407bab',gold:'#d3ab45'};
  const shape=(kind,color,x)=>kind==='circle'?`<circle cx="${x}" cy="66" r="23" fill="${colors[color]||'#777'}"/>`:`<rect x="${x-23}" y="43" width="46" height="46" rx="2" fill="${colors[color]||'#777'}"/>`;
  const right=92+Math.min(32,Math.max(0,Number(s.gap)||0));
  return `<svg viewBox="0 0 180 132" role="img" aria-label="${esc(s.left_color+' '+s.left_shape+' left of '+s.right_color+' '+s.right_shape)}">${shape(s.left_shape,s.left_color,46)}${shape(s.right_shape,s.right_color,right)}</svg>`;
}
function scene(data) {
  $('result').innerHTML=callout('Code checks. The model measures. You look.',`Search retained: ${data.retained||'no valid candidate'}. Text scoring does not see the rendered image.`)+`<div class="scene-grid">${data.candidates.map(c=>`<article class="scene-card"><h3>${esc(c.name)}</h3><p class="subtle">${esc(c.origin)}</p>${sceneSVG(c.scene)}<p class="subtle">${Object.entries(c.checks).map(([k,v])=>`<span class="${v?'tick':'cross'}">${v?'✓':'×'} ${k}</span>`).join('<br>')}</p><div class="bars">${c.vector.map(v=>bar(v.question,v.value)).join('')}</div><b>Feature mean: ${number(c.score)}</b></article>`).join('')}</div><label class="field" style="margin-top:18px"><span>Your visual judgment</span><select id="human-choice"><option>Which scene better matches the instruction?</option>${data.candidates.map(c=>`<option>${esc(c.name)}</option>`).join('')}<option>Neither</option><option>Equivalent</option></select><small>This judgment stays in your browser. It is not used as model evidence.</small></label>${details('Generated scene, schema and semantic vector',data)}`;
}

function wire(data) {
  const message=data.response.choices[0].message;
  $('result').innerHTML=callout('The answer, byte for byte',data.semantics)+`<pre>${esc(message.content||'(no answer text)')}</pre><div id="wire-tokens"></div>${message.reasoning_content?details('Visible reasoning (not scored answer content)',message.reasoning_content):''}${message.tool_calls?details('Client-owned tool calls',message.tool_calls):''}${details('Request grammar or JSON format',data.request.grammar||data.request.response_format||'No output constraint')}${details('Exact HTTP request',data.request)}`;
  tokenView(data.entries,$('wire-tokens'));
}

function speculation(data) {
  const w=data.oracle.example_rejection;
  $('result').innerHTML=callout('A draft can be sure and still be rejected.','Compare source, vocabulary, prefix, and outcome before comparing numbers.')+`<div class="wide-scroll"><table class="small-table"><thead><tr><th>Proposed token</th><th>Draft head</th><th>Target verifier</th><th>Outcome</th></tr></thead><tbody>${w.proposal.map((p,i)=>`<tr><td>${p.token_id}</td><td>${percent(p.draft_probability)}</td><td>${percent(Math.exp(p.target_logprob))}</td><td>${i<w.accepted_proposals?'accepted':'rejected / after rejection'}</td></tr>`).join('')}</tbody></table></div><p class="subtle">Draft vocabulary: ${w.proposal[0].draft_vocab.toLocaleString()} · target vocabulary: ${w.target_vocab.toLocaleString()}. The emitted correction is scored on its own actual prefix.</p><div class="stats">${stat('Scored proposal tokens',w.scored_length)}${stat('Accepted prefix',w.accepted_proposals)}${stat('Native suffix windows',data.oracle.suffix_windows)}</div>${details('Target-only, MTP, suffix and coupled run timings',data.modes)}${details('Independent teacher-forced replay',data.replay)}${details('Suffix has target scores, no draft distribution',data.suffix_windows)}<p class="subtle">Replay and generation take different numerical paths. Their deltas are reported, not presented as identical computations.</p>`;
}

function performance(data) {
  const max=Math.max(...data.rows.map(r=>r.median_ms));
  $('result').innerHTML=callout('A measured frontier, on this setup.','Lower bars mean lower request latency. Open each path to see cache use, token counts, and engine timings.')+`<div class="bars">${data.rows.map(r=>bar(r.name,r.median_ms/max,number(r.median_ms,0)+' ms')).join('')}</div><p class="subtle">${esc(data.semantics)}</p>${data.rows.map(r=>details(`${r.name}: ${number(r.min_ms,0)}–${number(r.max_ms,0)} ms`,r.runs)).join('')}<details><summary>From latency to a hardware roofline</summary><p>Measure bytes transferred and FLOPs per step. A simple lower bound is max(bytes / sustained bandwidth, FLOPs / sustained compute). Queue, launch, synchronization and network costs sit above that bound. This page does not invent those measurements.</p><p>Branches to test: reduce score-row transfer; gather arbitrary labels on the GPU; share prefixes across candidates; batch teacher-forced scoring; tune MTP lookahead; bound suffix verification; acknowledge grammar updates before committing speculative tokens.</p></details>`;
}

function render(data) {
  if(page.section==='research'){renderResearch(page,data,$('result'));return;}
  const functions={choice:distribution,boolean:distribution,score:distribution,candidates,controller,rerank,graph,scene,wire,speculation,performance};
  functions[page.id](data);
}

async function run(event) {
  event?.preventDefault();
  stopResearch();
  const runId=++generation;
  aborter=new AbortController(); last=null;steps=[];
  $('download').disabled=true;
  $('timeline').innerHTML='<li class="subtle">Preparing the first request…</li>';
  $('result').innerHTML='<div class="request-progress"><span class="spinner"></span>Preparing experiment…</div>';
  status('Running','running');busy(true);
  let sawTerminal=false;
  try {
    const response=await fetch(`/api/run/${page.id}`,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Lab':'1'},body:JSON.stringify(values()),signal:aborter.signal});
    if(!response.ok){const error=await response.json();throw new Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail));}
    const reader=response.body.getReader(), decoder=new TextDecoder();let pending='';
    while(true){const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done});let boundary;
      while((boundary=pending.indexOf('\n\n'))>=0){const block=pending.slice(0,boundary);pending=pending.slice(boundary+2);const line=block.split('\n').filter(l=>l.startsWith('data: ')).map(l=>l.slice(6)).join('\n');if(!line)continue;const data=JSON.parse(line);if(runId!==generation)return;
        if(data.type==='step')addStep(data);
        if(data.type==='token'){const deltas=(data.chunk.choices||[]).map(c=>c.delta?.content||'').join('');if(deltas){let stream=$('live-text');if(!stream){stream=document.createElement('pre');stream.id='live-text';$('result').append(stream);}stream.append(document.createTextNode(deltas));}}
        if(data.type==='error'){sawTerminal=true;throw new Error(data.message);}
        if(data.type==='result'){
          last={experiment:page.id,...data};render(data.result);status('Completed','completed');
          $('download').disabled=false;sawTerminal=true;
          if(!steps.length)$('timeline').innerHTML='';
          const li=document.createElement('li');
          li.textContent=data.receipt.requests
            ? `${data.receipt.requests} model requests · ${data.receipt.mode==='recorded'?'replayed native measurements':'live execution'} · ${data.receipt.completion_tokens} generated tokens`
            : 'No model requests in this run. Inspect the displayed inputs and calculations; the JSON download preserves this result.';
          $('timeline').append(li);
        }
      }
      if(done)break;
    }
    if(!sawTerminal)throw new Error('The connection closed without a completed result.');
  }catch(error){if(runId!==generation)return;if(error.name==='AbortError'){status('Stopped');$('result').innerHTML=callout('Run stopped','Completed steps remain in the trace. The in-flight connection was closed.','amber');}else{status('Failed','error');$('result').innerHTML=callout('This run did not complete',error.message,'error');}}
  finally{if(runId===generation)busy(false);}
}

$('controls').addEventListener('submit',run);
$('stop').addEventListener('click',()=>aborter?.abort());
$('reset').addEventListener('click',()=>navigate(page.id,true));
$('mode').addEventListener('change',sourceNote);
$('download').addEventListener('click',()=>{if(!last)return;const url=URL.createObjectURL(new Blob([JSON.stringify(last,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`strata-control-lab-${page.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
document.addEventListener('click',e=>{const a=e.target.closest('[data-page]');if(a){e.preventDefault();navigate(a.dataset.page);}});
window.addEventListener('popstate',()=>navigate(location.pathname.split('/')[2]||'choice',true));
try{const response=await fetch('/api/catalog');if(!response.ok)throw new Error('Could not load experiment catalog');catalog=await response.json();navigate(location.pathname.split('/')[2]||'choice',true);}catch(error){$('result').textContent=error.message;}
