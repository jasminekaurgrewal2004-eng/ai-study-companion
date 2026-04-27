// =================== GLOBAL CONFIG ===================
const API_URL = '/api/';
let conversationHistory = [];
let currentSessionId = null;
let currentUser = JSON.parse(localStorage.getItem('asc-user') || 'null');
let authToken = localStorage.getItem('asc-token');
const SYSTEM_PROMPT = `You are Sage, a world-class AI learning assistant inside the AI Study Companion app. You help people from every domain and background — school and university students, working professionals, researchers, developers, creatives, language learners, hobbyists, and lifelong learners. You adapt your tone, depth, and examples to whatever the user is learning. Always be helpful, clear, and encouraging.`;

// Syllabus state
let syllabi = [];
let currentSyllabusId = null;

// =================== ROUTING ===================
const labels = {dashboard:'Dashboard',syllabus:'My Plan',calendar:'Calendar',tests:'Test Arena',flashcards:'Flashcards',tutor:'AI Tutor',billing:'Billing & Plan',groups:'Study Groups',journal:'My Journal',videos:'Video Library'};
function switchView(view){
  document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
  const navBtn = document.querySelector(`.nav-item[data-view="${view}"]`);
  if(navBtn) navBtn.classList.add('active');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  const target = document.getElementById('view-'+view);
  if(target){target.classList.add('active');document.getElementById('crumb').textContent=labels[view];}
  // Hide FAB on tutor page
  document.getElementById('fab').style.display = view==='tutor' ? 'none' : 'grid';
  // Load syllabi when switching to syllabus view
  if(view === 'syllabus') fetchSyllabi();
  // Load chat history when switching to tutor view
  if(view === 'tutor') loadChatHistory();
  // Load flashcards when switching to flashcards view
  if(view === 'flashcards') fcInit();
  // Show arena landing when switching to test arena
  if(view === 'tests') showArenaLanding();
  // Load calendar
  if(view === 'calendar') calLoad();
  window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('.nav-item[data-view]').forEach(item=>{
  item.addEventListener('click',()=>switchView(item.dataset.view));
});

// =================== THEME TOGGLE (LIGHT/DARK) ===================
const themeToggle = document.getElementById('theme-toggle');
const themeIcon = document.getElementById('theme-icon');
const themeText = document.getElementById('theme-text');

function updateThemeUI(isLight) {
  if (isLight) {
    document.body.classList.add('light');
    themeIcon.innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.343l-.707-.707M12 5a7 7 0 100 14 7 7 0 000-14z"/>';
    themeText.textContent = 'Dark Theme';
  } else {
    document.body.classList.remove('light');
    themeIcon.innerHTML = '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>';
    themeText.textContent = 'Light Theme';
  }
}

if(themeToggle){
  themeToggle.addEventListener('click', ()=>{
    const isLightNow = document.body.classList.contains('light');
    updateThemeUI(!isLightNow);
    localStorage.setItem('ai-study-companion-theme', !isLightNow ? 'light' : 'dark');
  });
}
// Restore preference
const savedTheme = localStorage.getItem('ai-study-companion-theme');
if(savedTheme === 'light'){
  updateThemeUI(true);
} else {
  updateThemeUI(false);
}

// =================== MODAL LOGIC ===================
function closeModal(){
  const newsModal = document.getElementById('news-modal');
  if (newsModal) newsModal.classList.remove('show');
  localStorage.setItem('ai-study-companion-news-dismissed', 'true');
}
window.closeModal = closeModal;

window.addEventListener('load', ()=>{
  if(!localStorage.getItem('ai-study-companion-news-dismissed')){
    setTimeout(()=>{
      const newsModal = document.getElementById('news-modal');
      if (newsModal) newsModal.classList.add('show');
    }, 1500);
  }
});

// =================== COMMAND PALETTE ===================
const cmdOverlay = document.getElementById('cmd-palette');
const cmdInput = document.getElementById('cmdInput');

window.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    if (cmdOverlay) { cmdOverlay.classList.add('show'); }
    if (cmdInput) { cmdInput.focus(); }
  }
  if (e.key === 'Escape') {
    if (cmdOverlay) cmdOverlay.classList.remove('show');
    const newsModal = document.getElementById('news-modal');
    if (newsModal) newsModal.classList.remove('show');
  }
});

if (cmdOverlay) {
  cmdOverlay.addEventListener('click', e => {
    if (e.target === cmdOverlay) cmdOverlay.classList.remove('show');
  });
}

// =================== CALENDAR HEATMAP ===================
(function(){
  const grid = document.getElementById('calGrid');
  if (!grid) return;
  // 13 cols × 7 rows = 91 cells
  for(let i=0;i<91;i++){
    const cell = document.createElement('div');
    cell.className = 'cal-cell';
    const r = Math.random();
    if(r>0.25){
      if(r>0.85) cell.classList.add('l4');
      else if(r>0.65) cell.classList.add('l3');
      else if(r>0.45) cell.classList.add('l2');
      else cell.classList.add('l1');
    }
    if(i===90) cell.classList.add('today','l2');
    grid.appendChild(cell);
  }
})();

// =================== TEST LOGIC ===================
const questions = [
  {
    q: "What is the best strategy for learning something completely new?",
    opts: ["Read the same notes repeatedly", "Active recall + spaced repetition", "Watch videos without taking notes", "Memorise definitions first"],
    correct: 1,
    diff: "EASY · +4/−1",
    hint: "Think about how the brain stores and retrieves information long-term.",
    explain: "Active recall (testing yourself) strengthens memory far more than re-reading. Spaced repetition ensures you review material just before you'd forget it."
  },
  {
    q: "In <i>Python</i>, what does the <code>len()</code> function return for a string?",
    opts: ["Number of words", "Number of characters", "Memory size in bytes", "Number of lines"],
    correct: 1,
    diff: "EASY · +4/−1",
    hint: "Think about what 'length' means for a sequence of characters.",
    explain: "<code>len('hello')</code> returns 5 — the number of characters including spaces and special characters."
  },
  {
    q: "Which of these is a <i>primary source</i> in academic research?",
    opts: ["A textbook summarising studies", "A Wikipedia article", "An original research paper", "A documentary film"],
    correct: 2,
    diff: "MEDIUM · +4/−1",
    hint: "Primary sources are original, uninterpreted materials from first-hand accounts.",
    explain: "Original research papers, raw data, and firsthand accounts are primary sources. Textbooks and encyclopaedias are secondary — they interpret primary sources."
  },
  {
    q: "What does <i>ROI</i> stand for in business?",
    opts: ["Rate of Inflation", "Return on Investment", "Revenue over Income", "Risk of Insolvency"],
    correct: 1,
    diff: "EASY · +4/−1",
    hint: "It measures how much profit you get relative to the cost of an investment.",
    explain: "ROI = (Net Profit / Cost of Investment) × 100. It's one of the most widely used metrics in finance, marketing, and operations."
  },
  {
    q: "Which principle states that objects in motion stay in motion unless acted on by an external force?",
    opts: ["Newton's Second Law", "Law of Conservation of Energy", "Newton's First Law (Inertia)", "Hooke's Law"],
    correct: 2,
    diff: "MEDIUM · +4/−1",
    hint: "This law explains why you lurch forward when a car brakes suddenly.",
    explain: "Newton's First Law — the Law of Inertia — states that a body remains at rest or in uniform motion unless an unbalanced external force acts on it."
  },
  {
    q: "In <i>graphic design</i>, what does 'negative space' refer to?",
    opts: ["Dark colours in a composition", "The empty area around a subject", "Low-resolution images", "Colours that clash"],
    correct: 1,
    diff: "MEDIUM · +4/−1",
    hint: "Think about what surrounds the main subject, not the subject itself.",
    explain: "Negative space is the empty or open area surrounding the main subject. Skilled designers use it intentionally to create balance, emphasis, and visual interest."
  },
  {
    q: "What does HTML stand for?",
    opts: ["Hyper Transfer Markup Language", "HyperText Markup Language", "High-Tech Modern Language", "HyperText Management Language"],
    correct: 1,
    diff: "EASY · +4/−1",
    hint: "It's the standard language for creating web pages.",
    explain: "HTML (HyperText Markup Language) is the skeleton of every webpage — it defines structure and content using tags like <code>&lt;h1&gt;</code>, <code>&lt;p&gt;</code>, and <code>&lt;div&gt;</code>."
  },
  {
    q: "Which psychological concept describes adjusting new information to fit existing mental frameworks?",
    opts: ["Accommodation", "Assimilation", "Equilibration", "Scaffolding"],
    correct: 1,
    diff: "HARD · +4/−1",
    hint: "Piaget described two ways of dealing with new knowledge — one changes the framework, one doesn't.",
    explain: "Assimilation = fitting new info into existing schemas. Accommodation = changing your schema to handle new info. Both are part of Piaget's theory of cognitive development."
  }
];

const _defaultQuestions = questions.slice(); // backup of hardcoded questions
let _smartQuizQuestions = null;              // staged by startSmartQuiz(); consumed by startTest()
let _smartQuizMeta = null;                   // {topic, prediction} for result insights
let _selectedTopic = null;                   // selected in quiz setup screen
let _selectedQCount = 5;                     // selected question count
let _quizDuration = 600;                     // seconds — 600 = quick quiz, longer for mock
let _mockTopic = '';
let _mockDuration = 60;
let _mockCount = 30;
let _mockMcq  = 12;
let _mockTf   = 8;
let _mockFitb = 6;
let _mockAr   = 4;

let currentQ = 0;
let answers = Array(questions.length).fill(null); // index of selected option, or null
let flagged = new Set();
let timeLeft = 600; // 10 min
let timerInterval = null;
let startTime = 0;

function startTest(){
  // Swap in ML questions if startSmartQuiz staged them, else reset to defaults
  if (_smartQuizQuestions) {
    questions.length = 0;
    _smartQuizQuestions.forEach(q => questions.push(q));
    _smartQuizQuestions = null;
  } else {
    questions.length = 0;
    _defaultQuestions.forEach(q => questions.push(q));
  }
  currentQ = 0;
  answers = Array(questions.length).fill(null);
  flagged.clear();
  timeLeft = _quizDuration;
  startTime = Date.now();
  document.getElementById('arena-landing-screen').style.display='none';
  document.getElementById('quiz-setup-screen').style.display='none';
  document.getElementById('mock-setup-screen').style.display='none';
  document.getElementById('test-hub-screen').style.display='none';
  document.getElementById('quiz-screen').style.display='block';
  document.getElementById('result-screen').style.display='none';
  renderQuestion();
  renderMap();
  updateSummary();
  if(timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(tickTimer, 1000);
}

function tickTimer(){
  timeLeft--;
  if(timeLeft<=0){timeLeft=0;clearInterval(timerInterval);submitTest();}
  const m = String(Math.floor(timeLeft/60)).padStart(2,'0');
  const s = String(timeLeft%60).padStart(2,'0');
  const t = document.getElementById('timer'); if(t) t.textContent = `${m}:${s}`;
}

function renderQuestion(){
  const q = questions[currentQ];
  document.getElementById('q-count-lbl').textContent = `Question ${currentQ+1} of ${questions.length}`;
  document.getElementById('q-num-cur').textContent = `Q.${String(currentQ+1).padStart(2,'0')}`;
  document.getElementById('q-diff').textContent = q.diff;
  document.getElementById('q-text').innerHTML = q.q;
  document.getElementById('progressFill').style.width = `${((currentQ+1)/questions.length)*100}%`;

  const keys = ['A','B','C','D'];
  const optsHtml = q.opts.map((o,i)=>{
    const selected = answers[currentQ]!==null;
    let cls = 'option';
    if(selected){
      if(i===q.correct) cls += ' correct';
      else if(i===answers[currentQ]) cls += ' wrong';
    }
    return `<button class="${cls}" onclick="selectOption(${i})" ${selected?'disabled':''}>
      <span class="opt-key">${keys[i]}</span>
      <span>${o}</span>
      <span class="opt-status check">✓</span>
      <span class="opt-status cross">✗</span>
    </button>`;
  }).join('');
  document.getElementById('q-options').innerHTML = optsHtml;

  const fb = document.getElementById('feedback');
  if(answers[currentQ]!==null){
    const isCorrect = answers[currentQ]===q.correct;
    fb.className = 'feedback show ' + (isCorrect?'correct':'wrong');
    document.getElementById('fb-title').innerHTML = isCorrect ? '✨ Correct!' : '🤔 Not quite';
    document.getElementById('fb-text').textContent = q.explain;
  } else {
    fb.className = 'feedback';
  }

  const nextBtn = document.getElementById('nextBtn');
  nextBtn.textContent = currentQ === questions.length-1 ? 'Submit →' : 'Next →';
}

function selectOption(idx){
  if(answers[currentQ]!==null) return;
  answers[currentQ] = idx;
  renderQuestion();
  renderMap();
  updateSummary();
}

function renderMap(){
  const map = document.getElementById('qMap');
  map.innerHTML = questions.map((q,i)=>{
    let cls='q-dot';
    if(i===currentQ) cls+=' cur';
    else if(answers[i]!==null){
      cls += answers[i]===q.correct ? ' answered' : ' wrong';
    }
    if(flagged.has(i)) cls+=' flagged';
    return `<span class="${cls}" onclick="goToQ(${i})">${i+1}</span>`;
  }).join('');
}

function goToQ(i){currentQ=i;renderQuestion();renderMap();}

function updateSummary(){
  const answered = answers.filter(a=>a!==null).length;
  const correct = answers.filter((a,i)=>a!==null && a===questions[i].correct).length;
  const wrong = answered - correct;
  const marks = correct*4 - wrong*1;
  document.getElementById('ms-answered').textContent = `${answered} / ${questions.length}`;
  document.getElementById('ms-correct').textContent = correct;
  document.getElementById('ms-wrong').textContent = wrong;
  document.getElementById('ms-flag').textContent = flagged.size;
  document.getElementById('ms-marks').textContent = marks;
  if(answered>0){
    const elapsed = Math.floor((Date.now()-startTime)/1000);
    const avg = Math.floor(elapsed/answered);
    document.getElementById('ms-avg').textContent = `${Math.floor(avg/60)}:${String(avg%60).padStart(2,'0')}`;
  }
}

function nextQuestion(){
  if(currentQ < questions.length-1){currentQ++; renderQuestion(); renderMap();}
  else submitTest();
}
function prevQuestion(){
  if(currentQ>0){currentQ--; renderQuestion(); renderMap();}
}

function showHint(){
  const q = questions[currentQ];
  document.getElementById('hintPreview').innerHTML = `<strong>💡 Hint:</strong> ${q.hint}`;
}

function submitTest(){
  clearInterval(timerInterval);
  const correct = answers.filter((a,i)=>a!==null && a===questions[i].correct).length;
  const wrong = answers.filter((a,i)=>a!==null && a!==questions[i].correct).length;
  const skipped = answers.filter(a=>a===null).length;
  const score = correct*4 - wrong*1;
  const accuracy = correct+wrong>0 ? Math.round(correct/(correct+wrong)*100) : 0;
  const elapsed = 600 - timeLeft;
  const mins = Math.floor(elapsed/60), secs = elapsed%60;
  const avg = answers.filter(a=>a!==null).length > 0
    ? Math.floor(elapsed / answers.filter(a=>a!==null).length)
    : 0;

  document.getElementById('resultScore').textContent = score;
  document.getElementById('rs-correct').textContent = correct;
  document.getElementById('rs-wrong').textContent = wrong;
  document.getElementById('rs-skip').textContent = skipped;
  document.getElementById('rs-accuracy').textContent = accuracy+'%';
  document.getElementById('rs-time').textContent = `${mins}:${String(secs).padStart(2,'0')}`;
  document.getElementById('rs-avgTime').textContent = `${Math.floor(avg/60)}:${String(avg%60).padStart(2,'0')}`;

  let emoji='🎉', msg='Nice work! Here\'s your breakdown.';
  if(accuracy>=80){emoji='🏆';msg='Outstanding! You\'re in the top bracket.';}
  else if(accuracy>=60){emoji='💪';msg='Solid performance. Minor gaps to close.';}
  else if(accuracy>=40){emoji='📚';msg='Decent try — let\'s dive into the concepts you missed.';}
  else {emoji='🌱';msg='Early days. Every mistake is a lesson — keep going.';}
  document.getElementById('resultEmoji').textContent = emoji;
  document.getElementById('resultMsg').textContent = msg;

  document.getElementById('quiz-screen').style.display='none';
  document.getElementById('result-screen').style.display='block';
  window.scrollTo({top:0,behavior:'smooth'});

  // AI Insights panel — only for ML-powered smart quizzes
  const _aiPanel = document.getElementById('ai-insights-panel');
  if (_aiPanel) {
    if (_smartQuizMeta && _smartQuizMeta.prediction) {
      const _p = _smartQuizMeta.prediction;
      _aiPanel.style.display = 'block';
      document.getElementById('ai-pred-score').textContent = _p.predicted_score + ' / ' + _p.max_score;
      document.getElementById('ai-actual-score').textContent = score + ' / ' + _p.max_score;
      const _diff = score - _p.predicted_score;
      const _diffStr = _diff > 0
        ? '+' + _diff + ' above AI prediction'
        : _diff < 0 ? Math.abs(_diff) + ' below AI prediction'
        : 'Exactly as predicted';
      const _topicName = _smartQuizMeta.topic.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
      document.getElementById('ai-topic-focus').innerHTML =
        '<span style="font-size:13px;"><strong>' + _topicName + '</strong> &middot; '
        + '<span style="color:' + (_diff >= 0 ? 'var(--mint)' : 'var(--coral)') + ';">' + _diffStr + '</span></span>';
      document.getElementById('ai-next-review').textContent =
        'Model predicted ' + _p.predicted_accuracy + '% accuracy based on your review history (' + _p.confidence + ' confidence).';
    } else {
      _aiPanel.style.display = 'none';
    }
  }
}

function exitTest(){
  if(timerInterval) clearInterval(timerInterval);
  questions.length = 0;
  _defaultQuestions.forEach(q => questions.push(q));
  _smartQuizMeta = null;
  _selectedTopic = null;
  _selectedQCount = 5;
  const _pc = document.getElementById('ml-prediction-card');
  if (_pc) _pc.style.display = 'none';
  const _ap = document.getElementById('ai-insights-panel');
  if (_ap) _ap.style.display = 'none';
  _quizDuration = 600;
  showArenaLanding();
}

// Keyboard shortcuts
document.addEventListener('keydown',e=>{
  if(document.getElementById('quiz-screen').style.display==='none') return;
  if(document.activeElement.tagName==='TEXTAREA' || document.activeElement.tagName==='INPUT') return;
  if(e.key==='ArrowRight'){nextQuestion();}
  if(e.key==='ArrowLeft'){prevQuestion();}
  if(e.key==='f'||e.key==='F'){
    if(flagged.has(currentQ)) flagged.delete(currentQ); else flagged.add(currentQ);
    renderMap(); updateSummary();
  }
});

// Plan checkbox interaction
document.querySelectorAll('.plan-item:not(.done)').forEach(item=>{
  item.addEventListener('click',()=>{
    const check = item.querySelector('.p-check');
    check.classList.toggle('on');
    if(check.classList.contains('on')){
      check.innerHTML='<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>';
      item.classList.add('done');
    } else {
      check.innerHTML='';
      item.classList.remove('done');
    }
  });
});

// Perf tabs
document.querySelectorAll('.perf-tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.perf-tab').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
  });
});

// =================== CHATBOT LOGIC (GROQ API) ===================

function currentTime(){
  const d = new Date();
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

function addUserMessage(text){
  const msgs = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `
    <div class="msg-avatar">A</div>
    <div>
      <div class="msg-bubble">${escapeHtml(text)}</div>
      <div class="msg-time">${currentTime()}</div>
    </div>`;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
}

function addBotMessage(html, quickReplies=[]){
  const msgs = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.className = 'msg bot';
  const quickHtml = quickReplies.length ?
    `<div class="msg-quick">${quickReplies.map(q=>`<button class="quick-btn" onclick="useSuggestion('${q.replace(/'/g,"\\'")}')">${q}</button>`).join('')}</div>` : '';
  el.innerHTML = `
    <div class="msg-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2"/></svg></div>
    <div>
      <div class="msg-bubble">${html}</div>
      ${quickHtml}
      <div class="msg-time">${currentTime()}</div>
    </div>`;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTyping(){
  const msgs = document.getElementById('chatMessages');
  const el = document.createElement('div');
  el.className = 'msg bot';
  el.id = 'typing';
  el.innerHTML = `
    <div class="msg-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2"/></svg></div>
    <div class="typing"><span></span><span></span><span></span></div>`;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
}
function hideTyping(){
  const t = document.getElementById('typing'); if(t) t.remove();
}

function escapeHtml(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// Markdown to HTML converter
function mdToHtml(md) {
  let html = md;
  // Code blocks
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Headings (must run before bold so ## **text** works)
  html = html.replace(/^#{4}\s+(.+)$/gm, '<h5 class="ins-h5">$1</h5>');
  html = html.replace(/^#{3}\s+(.+)$/gm, '<h4 class="ins-h4">$1</h4>');
  html = html.replace(/^#{2}\s+(.+)$/gm, '<h3 class="ins-h3">$1</h3>');
  html = html.replace(/^#{1}\s+(.+)$/gm, '<h2 class="ins-h2">$1</h2>');
  // Bold / italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Bullet lists — collect consecutive <li> into a <ul>
  html = html.replace(/^\s*[-•*]\s+(.+)/gm, '<li>$1</li>');
  html = html.replace(/^\s*\d+\.\s+(.+)/gm, '<li class="ins-ol">$1</li>');
  html = html.replace(/(<li(?:[^>]*)>[\s\S]*?<\/li>(?:\n<li(?:[^>]*)>[\s\S]*?<\/li>)*)/g, '<ul>$1</ul>');
  // Strip stray newlines next to block tags
  html = html.replace(/(<\/(h[2-5]|ul|pre)>)\n/g, '$1');
  html = html.replace(/\n(<(h[2-5]|ul|pre))/g, '$1');
  // Remaining newlines
  html = html.replace(/\n\n/g, '<br>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

// API Key management
function saveApiKey(){
  const input = document.getElementById('apiKeyInput');
  const key = input.value.trim();
  if(!key){
    updateApiKeyStatus(false, 'Please enter a key');
    return;
  }
  GROQ_API_KEY = key;
  localStorage.setItem('asc-groq-key', key);
  input.value = '';
  input.type = 'password';
  updateApiKeyStatus(true, 'Connected · Key saved');
}

function updateApiKeyStatus(connected, text){
  const status = document.getElementById('apiKeyStatus');
  if(!status) return;
  status.className = 'api-key-status ' + (connected ? 'connected' : 'disconnected');
  status.textContent = text || (connected ? 'Connected' : 'Not connected');
}

// =================== BACKEND INTEGRATION ===================

async function handleLogin() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value.trim();
    
    try {
        const res = await fetch(`${API_URL}auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        
        if (res.ok) {
            authToken = data.token;
            currentUser = data.user;
            localStorage.setItem('asc-token', authToken);
            localStorage.setItem('asc-user', JSON.stringify(currentUser));
            hideAuthModal();
            updateUIForUser();
            window.location.reload();
            closeModal();
        } else {
            alert(data.msg || 'Login failed');
        }
    } catch (err) {
        console.error(err);
        alert('Server connection error');
    }
}

async function handleSignup() {
    const username = document.getElementById('signup-username').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    
    try {
        const res = await fetch(`${API_URL}auth/signup/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });
        const data = await res.json();
        
        if (res.ok) {
            alert('Account created! Please login.');
            toggleAuthMode();
        } else {
            alert(data.msg || 'Registration failed');
        }
    } catch (err) {
        console.error(err);
        alert('Server connection error');
    }
}

function logout() {
    localStorage.removeItem('asc-token');
    localStorage.removeItem('asc-user');
    location.reload();
}

function toggleAuthMode() {
    const login = document.getElementById('login-form');
    const signup = document.getElementById('signup-form');
    if (login.style.display === 'none') {
        login.style.display = 'block';
        signup.style.display = 'none';
    } else {
        login.style.display = 'none';
        signup.style.display = 'block';
    }
}

function showAuthModal() {
    document.getElementById('auth-modal').style.display = 'grid';
}

function hideAuthModal() {
    document.getElementById('auth-modal').style.display = 'none';
}

function updateUIForUser() {
    if (currentUser) {
        document.querySelector('.profile-name').textContent = currentUser.username;
        document.querySelector('.profile-plan').textContent = currentUser.plan + ' Plan';
        document.querySelector('.avatar').textContent = currentUser.username[0].toUpperCase();
    }
}

// Relative time label for sidebar items
function relativeTime(isoString) {
    const d = new Date(isoString);
    const diff = Math.floor((Date.now() - d) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'Yesterday';
    return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
}

// Render conversation sessions in the sidebar
function renderChatSessions(sessions) {
    const list = document.getElementById('chat-history-list');
    if (!list) return;
    if (!sessions || sessions.length === 0) {
        list.innerHTML = '<div class="chat-history-label" style="font-size:11px;opacity:0.6;">No conversations yet</div>';
        return;
    }

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterdayStart = new Date(todayStart - 86400000);
    const weekStart = new Date(todayStart - 6 * 86400000);

    const groups = { Today: [], Yesterday: [], 'This week': [], Older: [] };
    sessions.forEach(s => {
        const d = new Date(s.updated_at);
        if (d >= todayStart) groups['Today'].push(s);
        else if (d >= yesterdayStart) groups['Yesterday'].push(s);
        else if (d >= weekStart) groups['This week'].push(s);
        else groups['Older'].push(s);
    });

    list.innerHTML = '';
    Object.entries(groups).forEach(([label, items]) => {
        if (!items.length) return;
        const lbl = document.createElement('div');
        lbl.className = 'chat-history-label';
        lbl.textContent = label;
        list.appendChild(lbl);
        items.forEach(s => {
            const el = document.createElement('div');
            el.className = 'chat-h-item' + (currentSessionId !== null && s.id === currentSessionId ? ' active' : '');
            el.dataset.sessionId = s.id;
            el.innerHTML = `
                <div class="chat-h-item-body">
                    <div class="ht">${escapeHtml(s.title)}</div>
                    <div class="hm">${relativeTime(s.updated_at)}</div>
                </div>
                <button class="chat-h-delete" title="Delete conversation" data-sid="${s.id}">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>`;
            el.querySelector('.chat-h-item-body').addEventListener('click', () => loadChatSession(s.id));
            el.querySelector('.chat-h-delete').addEventListener('click', (e) => {
                e.stopPropagation();
                deleteChatSession(s.id);
            });
            list.appendChild(el);
        });
    });
}

// Fetch sessions from backend and re-render sidebar
async function loadChatSessions() {
    try {
        const res = await fetch(`${API_URL}chat/sessions/`, { credentials: 'include' });
        console.log('[Sessions] HTTP status:', res.status, res.ok);
        if (!res.ok) {
            console.error('[Sessions] Bad response:', res.status);
            return;
        }
        const sessions = await res.json();
        console.log('[Sessions] Received:', sessions.length, sessions.map(s => s.title));
        renderChatSessions(sessions);
    } catch (err) {
        console.error('[Sessions] Failed:', err);
    }
}

// Delete a conversation session
async function deleteChatSession(sessionId) {
    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}chat/sessions/${sessionId}/`, {
            method: 'DELETE',
            headers,
            credentials: 'include'
        });
        if (!res.ok) return;

        // If we deleted the active session, clear the chat
        if (sessionId === currentSessionId) {
            currentSessionId = null;
            conversationHistory = [];
            const msgs = document.getElementById('chatMessages');
            if (msgs) msgs.innerHTML = '';
            addBotMessage(`Conversation deleted. Start a new one anytime ✨`);
        }

        await loadChatSessions();
    } catch (err) {
        console.error('Failed to delete session:', err);
    }
}

// Load messages for a specific session into the chat window
async function loadChatSession(sessionId) {
    currentSessionId = sessionId;
    conversationHistory = [];
    const msgs = document.getElementById('chatMessages');
    if (msgs) msgs.innerHTML = '';

    document.querySelectorAll('.chat-h-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.sessionId) === sessionId);
    });

    try {
        const res = await fetch(`${API_URL}chat/?session_id=${sessionId}`, { credentials: 'include' });
        if (!res.ok) return;
        const history = await res.json();
        if (!Array.isArray(history) || history.length === 0) return;
        history.forEach(m => {
            if (m.role === 'user') {
                addUserMessage(m.content);
                conversationHistory.push({ role: 'user', content: m.content });
            } else {
                addBotMessage(mdToHtml(m.content));
                conversationHistory.push({ role: 'assistant', content: m.content });
            }
        });
    } catch (err) {
        console.error('Failed to load session:', err);
    }
}

// Called on page load and when switching to tutor view
async function loadChatHistory() {
    await loadChatSessions();
    // Load the most recent session if none is already active
    if (!currentSessionId) {
        const firstItem = document.querySelector('#chat-history-list .chat-h-item[data-session-id]');
        if (firstItem) {
            await loadChatSession(parseInt(firstItem.dataset.sessionId));
        }
    }
}

// Call Backend AI API (Groq)
async function callChatAPI(userText) {
    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    const url = `${API_URL}chat/`;
    console.log("Calling Chat API:", url);
    const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        credentials: 'include',
        body: JSON.stringify({
            message: userText,
            history: conversationHistory,
            session_id: currentSessionId
        })
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.msg || 'Server error');
    }

    const data = await response.json();
    const reply = data.text;

    console.log('[Chat] Response session_id:', data.session_id, 'title:', data.session_title);

    // Update session tracking and refresh sidebar
    if (data.session_id) {
        currentSessionId = data.session_id;
    }
    conversationHistory.push({ role: 'user', content: userText });
    conversationHistory.push({ role: 'assistant', content: reply });

    // Always refresh sidebar so title, ordering, and time stay current
    await loadChatSessions();

    return reply;
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function sendMessage(){
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if(!text) return;
  
  addUserMessage(text);
  input.value='';
  input.style.height='auto';
  showTyping();

  try {
    const reply = await callChatAPI(text);
    hideTyping();
    addBotMessage(mdToHtml(reply));
  } catch(err) {
    console.error("Chat Error:", err);
    hideTyping();
    addBotMessage(`❌ <strong>Oops!</strong> ${err.message}`);
  }
}

function useSuggestion(text){
  const input = document.getElementById('chatInput');
  input.value = text;
  sendMessage();
}

async function newChat(){
  currentSessionId = null;
  conversationHistory = [];
  const msgs = document.getElementById('chatMessages');
  if (msgs) msgs.innerHTML = '';
  addBotMessage(`Fresh conversation started ✨ What's on your mind?`);
  // Refresh sidebar — previous sessions stay visible, none is highlighted as active
  await loadChatSessions();
}

document.getElementById('chatInput').addEventListener('keydown',e=>{
  if(e.key==='Enter' && !e.shiftKey){e.preventDefault();sendMessage();}
});

// =================== JOURNAL LOGIC ===================
let journals = [];
let currentJournalId = null;

// Toggle password input visibility
const protectToggle = document.getElementById('j-is-protected');
const passwordInput = document.getElementById('j-entry-password');
if(protectToggle && passwordInput) {
    protectToggle.addEventListener('change', () => {
        passwordInput.style.display = protectToggle.checked ? 'block' : 'none';
    });
}

async function fetchJournals() {
    try {
        const res = await fetch(`${API_URL}journals/`, { credentials: 'include' });
        const data = await res.json();
        if (Array.isArray(data)) {
            journals = data;
            renderJournalList();
        }
    } catch (err) {
        console.error('Error fetching journals:', err);
        // Don't alert here to avoid spamming the user, just log
    }
}

function renderJournalList() {
    const listContainer = document.getElementById('journal-list');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    journals.forEach(j => {
        const date = new Date(j.date);
        const dateStr = date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' }).toUpperCase();
        
        const card = document.createElement('div');
        card.className = `j-entry-card ${currentJournalId === j.id ? 'active' : ''}`;
        card.onclick = () => selectJournal(j.id);
        
        const lockIcon = j.is_protected ? ' <span title="Protected" style="color:var(--accent);">🔒</span>' : '';
        const categoryLabel = j.mood ? `<span class="j-tag" style="margin-left:auto;">${j.mood}</span>` : '';
        
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <div class="j-date">${dateStr}</div>
                ${categoryLabel}
            </div>
            <div class="j-title">${escapeHtml(j.title)}${lockIcon}</div>
            <div class="j-preview">${escapeHtml(j.content.substring(0, 60))}${j.content.length > 60 ? '...' : ''}</div>
        `;
        listContainer.appendChild(card);
    });
}

async function selectJournal(id) {
    const journal = journals.find(j => j.id === id);
    if (!journal) return;

    if (journal.is_protected) {
        const pwd = prompt("This entry is password protected. Enter password to view:");
        if (pwd === null) return; // Cancelled
        
        try {
            // Fetch detail to check password
            const res = await fetch(`${API_URL}journals/${id}/`, { credentials: 'include' });
            const fullData = await res.json();
            if (fullData.entry_password && pwd !== fullData.entry_password) {
                alert("Incorrect password!");
                return;
            }
            // If correct, load content
            loadJournalToEditor(fullData);
        } catch (err) {
            console.error(err);
            alert("Error verifying password");
        }
    } else {
        loadJournalToEditor(journal);
    }
}

function loadJournalToEditor(j) {
    currentJournalId = j.id;
    document.querySelector('.j-editor-title').value = j.title;
    document.querySelector('.j-editor-body').value = j.content;
    
    const moodSelect = document.getElementById('j-mood-select');
    if (moodSelect) moodSelect.value = j.mood || '';
    
    const pToggle = document.getElementById('j-is-protected');
    const pInput = document.getElementById('j-entry-password');
    if(pToggle && pInput) {
        pToggle.checked = j.is_protected;
        pInput.value = j.entry_password || '';
        pInput.style.display = j.is_protected ? 'block' : 'none';
    }

    document.querySelectorAll('.j-entry-card').forEach(c => c.classList.remove('active'));
    renderJournalList();
}

function createNewJournal() {
    currentJournalId = null;
    document.querySelector('.j-editor-title').value = 'Untitled Entry';
    document.querySelector('.j-editor-body').value = '';
    
    const moodSelect = document.getElementById('j-mood-select');
    if (moodSelect) moodSelect.value = '';
    
    const pToggle = document.getElementById('j-is-protected');
    const pInput = document.getElementById('j-entry-password');
    if(pToggle && pInput) {
        pToggle.checked = false;
        pInput.value = '';
        pInput.style.display = 'none';
    }
    
    document.querySelectorAll('.j-entry-card').forEach(c => c.classList.remove('active'));
}

async function saveJournal() {
    const title = document.querySelector('.j-editor-title').value;
    const content = document.querySelector('.j-editor-body').value;
    const mood = document.getElementById('j-mood-select').value;
    const is_protected = document.getElementById('j-is-protected').checked;
    const entry_password = document.getElementById('j-entry-password').value;
    
    if (!title || !content) {
        alert('Please provide both title and content');
        return;
    }

    const method = currentJournalId ? 'PUT' : 'POST';
    const url = currentJournalId ? `${API_URL}journals/${currentJournalId}/` : `${API_URL}journals/`;
    
    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        console.log(`Saving journal (${method}):`, url);
        const res = await fetch(url, {
            method,
            headers,
            credentials: 'include',
            body: JSON.stringify({ title, content, mood, is_protected, entry_password })
        });
        
        const data = await res.json();
        
        if (res.ok) {
            if (!currentJournalId) currentJournalId = data.id;
            await fetchJournals();
            alert("Journal saved successfully!");
        } else {
            console.error('Save failed:', data);
            alert(data.msg || data.error || 'Save failed. Please check if you are logged in.');
        }
    } catch (err) {
        console.error('Error saving journal:', err);
        alert('Error saving journal entry: ' + err.message);
    }
}

async function deleteJournal() {
    if (!currentJournalId) return;
    if (!confirm('Are you sure you want to delete this entry?')) return;

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}journals/${currentJournalId}/`, {
            method: 'DELETE',
            headers,
            credentials: 'include'
        });
        if (res.ok) {
            createNewJournal();
            fetchJournals();
        } else {
            alert('Delete failed');
        }
    } catch (err) {
        console.error('Error deleting journal:', err);
    }
}

// Initial fetch
window.addEventListener('load', () => {
    fetchJournals();
    loadChatHistory();
});

// =================== THREE.JS BACKGROUND ===================
(function() {
  const container = document.getElementById('canvas-container');
  if (!container || !window.THREE) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  container.appendChild(renderer.domElement);

  const particlesGeometry = new THREE.BufferGeometry();
  const particlesCount = 150;
  const posArray = new Float32Array(particlesCount * 3);
  for (let i = 0; i < particlesCount * 3; i++) {
    posArray[i] = (Math.random() - 0.5) * 10;
  }
  particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  const particlesMaterial = new THREE.PointsMaterial({ size: 0.015, color: 0x4338ca, transparent: true, opacity: 0.4 });
  const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
  scene.add(particlesMesh);

  camera.position.z = 5;
  function animate() {
    requestAnimationFrame(animate);
    particlesMesh.rotation.y += 0.001;
    renderer.render(scene, camera);
  }
  animate();
})();

// =================== FLASHCARDS API LOGIC ===================
let fcAllCards = [];       // all cards from API
let fcDueCards = [];       // cards due for review
let fcStudyIndex = 0;      // current index in study session
let fcFlipped = false;     // is the current card flipped?

// ---------- Create a new flashcard ----------
async function fcCreateCard() {
  const subjectEl = document.getElementById('fc-subject');
  const frontEl = document.getElementById('fc-front');
  const backEl = document.getElementById('fc-back');

  const subject = subjectEl ? subjectEl.value.trim() : 'General';
  const front = frontEl ? frontEl.value.trim() : '';
  const back = backEl ? backEl.value.trim() : '';

  if (!front || !back) {
    alert('Please fill in both the front and back of the card.');
    return;
  }

  const headers = { 'Content-Type': 'application/json' };
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    const res = await fetch(`${API_URL}flashcards/`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ front, back, subject: subject || 'General' })
    });
    const data = await res.json();
    if (res.ok) {
      if (subjectEl) subjectEl.value = '';
      if (frontEl) frontEl.value = '';
      if (backEl) backEl.value = '';
      showToast('Flashcard added! ✨');
      const filterEl = document.getElementById('fc-filter-subject');
      if (filterEl) filterEl.value = ''; // Clear filter to show new card
      await fcLoadCards();
      await fcLoadDeckStats();
      await fcLoadSubjects();
    } else {
      alert(data.error || data.msg || 'Failed to create flashcard');
    }
  } catch (err) {
    console.error('Error creating flashcard:', err);
    alert('Error creating flashcard: ' + err.message);
  }
}

// ---------- Load all cards (optionally filtered by subject) ----------
async function fcLoadCards() {
  const filterEl = document.getElementById('fc-filter-subject');
  const subject = filterEl ? filterEl.value : '';
  const listEl = document.getElementById('fc-card-list');
  if (!listEl) return;

  try {
    let url = `${API_URL}flashcards/`;
    if (subject) url += `?subject=${encodeURIComponent(subject)}`;
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json();
    if (!Array.isArray(data)) { listEl.innerHTML = '<div style="color:var(--ink-soft);font-size:13px;text-align:center;padding:16px;">No cards found.</div>'; return; }
    fcAllCards = data;

    if (data.length === 0) {
      listEl.innerHTML = '<div style="color:var(--ink-soft);font-size:13px;text-align:center;padding:16px;">No flashcards yet. Create one above!</div>';
      return;
    }

    listEl.innerHTML = data.map(c => {
      const dueNow = c.is_due;
      const statusPill = dueNow
        ? '<span style="font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;background:rgba(251,113,133,0.15);color:var(--coral);letter-spacing:.04em;">DUE</span>'
        : '<span style="font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;background:rgba(52,211,153,0.15);color:var(--mint);letter-spacing:.04em;">OK</span>';
      const nextDate = new Date(c.next_review).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
      return `<div style="display:flex;align-items:center;gap:16px;padding:14px 18px;border:1.5px solid var(--line);border-radius:13px;background:var(--surface);transition:border-color .15s;" onmouseover="this.style.borderColor='rgba(99,102,241,0.4)'" onmouseout="this.style.borderColor='var(--line)'">
        <div style="width:6px;height:40px;border-radius:4px;background:${dueNow ? 'var(--coral)' : 'var(--mint)'};flex-shrink:0;"></div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;color:var(--ink);font-size:14px;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(c.front)}</div>
          <div style="font-size:12px;color:var(--ink-soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(c.back)}</div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;font-family:'Space Mono',monospace;color:var(--ink-soft);">${escapeHtml(c.subject)}</span>
            ${statusPill}
          </div>
          <div style="font-size:11px;color:var(--ink-soft);">Next ${nextDate} · EF ${c.ease_factor}</div>
        </div>
        <button onclick="fcDeleteCard(${c.id})" title="Delete card"
          style="background:none;border:none;cursor:pointer;color:var(--ink-soft);padding:6px;border-radius:8px;opacity:0.45;transition:opacity .15s,background .15s;"
          onmouseover="this.style.opacity='1';this.style.background='rgba(251,113,133,0.1)'" onmouseout="this.style.opacity='0.45';this.style.background='none'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </button>
      </div>`;
    }).join('');
  } catch (err) {
    console.error('Error loading flashcards:', err);
    listEl.innerHTML = '<div style="color:var(--coral);font-size:13px;text-align:center;padding:16px;">Failed to load cards.</div>';
  }
}

// ---------- Load deck stats from ML endpoint ----------
async function fcLoadDeckStats() {
  try {
    const res = await fetch(`${API_URL}predict-recall/`, { credentials: 'include' });
    if (!res.ok) return;
    const data = await res.json();
    const summary = data.summary || {};
    const dueCards = data.due_cards || [];

    const totalEl = document.getElementById('fc-total');
    const dueEl = document.getElementById('fc-due');
    const upcomingEl = document.getElementById('fc-upcoming');
    const recallEl = document.getElementById('fc-recall');
    const dueChip = document.getElementById('fc-due-chip');

    if (totalEl) totalEl.textContent = summary.total || 0;
    if (dueEl) dueEl.textContent = summary.due_now || 0;
    if (upcomingEl) upcomingEl.textContent = summary.due_next_3_days || 0;
    if (recallEl) recallEl.textContent = summary.avg_recall_probability ? Math.round(summary.avg_recall_probability * 100) + '%' : '—';
    if (dueChip) dueChip.textContent = (summary.due_now || 0) + ' DUE';

    // Store due cards for study session
    fcDueCards = dueCards.map(d => d);
    fcStudyIndex = 0;
    fcFlipped = false;

    // Show study panel or "all caught up"
    const cardArea = document.getElementById('fc-card-area');
    const noCards = document.getElementById('fc-no-cards');
    if (fcDueCards.length > 0) {
      if (cardArea) cardArea.style.display = 'block';
      if (noCards) noCards.style.display = 'none';
      fcRenderStudyCard();
    } else {
      if (cardArea) cardArea.style.display = 'none';
      if (noCards) noCards.style.display = 'block';
    }
  } catch (err) {
    console.error('Error loading deck stats:', err);
  }
}

// ---------- Load subject filter dropdown ----------
async function fcLoadSubjects() {
  try {
    const res = await fetch(`${API_URL}flashcard-subjects/`, { credentials: 'include' });
    if (!res.ok) return;
    const data = await res.json();
    const subjects = data.subjects || [];
    const filterEl = document.getElementById('fc-filter-subject');
    if (!filterEl) return;
    const currentVal = filterEl.value;
    filterEl.innerHTML = '<option value="">All Subjects</option>';
    subjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.subject;
      opt.textContent = `${s.subject} (${s.count})`;
      filterEl.appendChild(opt);
    });
    filterEl.value = currentVal;
  } catch (err) {
    console.error('Error loading subjects:', err);
  }
}

// ---------- Render the current study card ----------
function fcRenderStudyCard() {
  if (fcStudyIndex >= fcDueCards.length) {
    // All done
    const cardArea = document.getElementById('fc-card-area');
    const noCards = document.getElementById('fc-no-cards');
    if (cardArea) cardArea.style.display = 'none';
    if (noCards) {
      noCards.style.display = 'block';
      noCards.innerHTML = `
        <div style="font-size:36px;margin-bottom:8px;">🎉</div>
        <div style="font-weight:600;color:var(--ink);">Session complete!</div>
        <div style="font-size:13px;margin-top:4px;color:var(--ink-soft);">You've reviewed all due cards. Great work.</div>`;
    }
    fcLoadDeckStats();
    return;
  }

  const card = fcDueCards[fcStudyIndex];
  fcFlipped = false;
  const textEl = document.getElementById('fc-card-text');
  const subjectEl = document.getElementById('fc-card-subject');
  const hintEl = document.getElementById('fc-flip-hint');
  const gradeEl = document.getElementById('fc-grade-btns');

  if (textEl) textEl.textContent = card.front;
  if (subjectEl) subjectEl.textContent = card.subject || 'General';
  if (hintEl) hintEl.textContent = 'Tap to reveal answer';
  if (gradeEl) gradeEl.style.display = 'none';
}

// ---------- Flip the current study card ----------
function fcFlipCard() {
  if (fcStudyIndex >= fcDueCards.length) return;
  if (fcFlipped) return; // already flipped

  fcFlipped = true;
  const card = fcDueCards[fcStudyIndex];
  const textEl = document.getElementById('fc-card-text');
  const hintEl = document.getElementById('fc-flip-hint');
  const gradeEl = document.getElementById('fc-grade-btns');

  if (textEl) textEl.textContent = card.back;
  if (hintEl) hintEl.textContent = '';
  if (gradeEl) gradeEl.style.display = 'block';
}

// ---------- Grade the current card (SM-2) ----------
async function fcGrade(grade) {
  if (fcStudyIndex >= fcDueCards.length) return;
  const card = fcDueCards[fcStudyIndex];
  const cardId = card.id;

  const headers = { 'Content-Type': 'application/json' };
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    await fetch(`${API_URL}flashcards/${cardId}/review/`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ grade })
    });
  } catch (err) {
    console.error('Error recording review:', err);
  }

  // Move to next card
  fcStudyIndex++;
  fcRenderStudyCard();
}

// ---------- Delete a card ----------
async function fcDeleteCard(cardId) {
  if (!confirm('Delete this flashcard?')) return;

  const headers = {};
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    const res = await fetch(`${API_URL}flashcards/${cardId}/`, {
      method: 'DELETE',
      headers,
      credentials: 'include'
    });
    if (res.ok) {
      showToast('Card deleted');
      await fcLoadCards();
      await fcLoadDeckStats();
      await fcLoadSubjects();
    }
  } catch (err) {
    console.error('Error deleting card:', err);
  }
}

// ---------- Initialize flashcards on page load ----------
function fcInit() {
  fcLoadCards();
  fcLoadDeckStats();
  fcLoadSubjects();
}

// Run on load
window.addEventListener('load', () => { fcInit(); });

// ---------- AI Generate flashcards on any topic ----------
async function fcGenerateCards() {
  const topicEl = document.getElementById('fc-gen-topic');
  const countEl = document.getElementById('fc-gen-count');
  const diffEl = document.getElementById('fc-gen-difficulty');
  const btn = document.getElementById('fc-gen-btn');
  const statusEl = document.getElementById('fc-gen-status');

  const topic = topicEl ? topicEl.value.trim() : '';
  const count = countEl ? parseInt(countEl.value) : 10;
  const difficulty = diffEl ? diffEl.value : 'mixed';

  if (!topic) {
    alert('Please enter a topic to generate flashcards.');
    if (topicEl) topicEl.focus();
    return;
  }

  // Show loading state
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="syl-loading-spinner" style="width:16px;height:16px;border-width:2px;margin-right:8px;"></span> Generating…'; }
  if (statusEl) {
    statusEl.style.display = 'block';
    statusEl.innerHTML = `<div style="display:flex;align-items:center;gap:10px;padding:14px 18px;background:rgba(99,102,241,0.08);border:1.5px solid rgba(99,102,241,0.2);border-radius:12px;">
      <span class="syl-loading-spinner" style="width:18px;height:18px;border-width:2px;flex-shrink:0;"></span>
      <div>
        <div style="font-weight:600;color:var(--ink);font-size:14px;">Generating ${count} flashcards about "${escapeHtml(topic)}"…</div>
        <div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">AI is creating your cards. This may take a few seconds.</div>
      </div>
    </div>`;
  }

  const headers = { 'Content-Type': 'application/json' };
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    const res = await fetch(`${API_URL}flashcards/generate/`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ topic, count, difficulty })
    });
    const data = await res.json();

    if (res.ok && data.cards) {
      if (topicEl) topicEl.value = '';
      if (statusEl) {
        statusEl.innerHTML = `<div style="display:flex;align-items:center;gap:10px;padding:14px 18px;background:rgba(52,211,153,0.1);border:1.5px solid rgba(52,211,153,0.3);border-radius:12px;">
          <div style="font-size:24px;">✨</div>
          <div>
            <div style="font-weight:600;color:var(--ink);font-size:14px;">${data.count} flashcards created!</div>
            <div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">Topic: ${escapeHtml(topic)} · Subject: ${escapeHtml(data.cards[0]?.subject || topic)}</div>
          </div>
        </div>`;
        setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
      }
      showToast(`${data.count} flashcards generated! ✨`);
      const filterEl = document.getElementById('fc-filter-subject');
      if (filterEl) filterEl.value = ''; // Clear filter to show new cards
      await fcLoadCards();
      await fcLoadDeckStats(); // This loads all due cards into fcDueCards

      // PRIORITIZE NEW CARDS: Put the cards we just generated at the start of the study queue
      const newIds = data.cards.map(c => c.id);
      fcDueCards.sort((a, b) => {
        const aIsNew = newIds.includes(a.id);
        const bIsNew = newIds.includes(b.id);
        if (aIsNew && !bIsNew) return -1;
        if (!aIsNew && bIsNew) return 1;
        return 0;
      });
      
      fcStudyIndex = 0;
      fcRenderStudyCard(); // Refresh the study box to show the first new card
      await fcLoadSubjects();
    } else {
      if (statusEl) {
        statusEl.innerHTML = `<div style="padding:14px 18px;background:rgba(239,68,68,0.08);border:1.5px solid rgba(239,68,68,0.2);border-radius:12px;color:var(--coral);font-size:13px;">
          ❌ ${escapeHtml(data.error || 'Failed to generate flashcards. Please try again.')}
        </div>`;
      }
    }
  } catch (err) {
    console.error('Error generating flashcards:', err);
    if (statusEl) {
      statusEl.innerHTML = `<div style="padding:14px 18px;background:rgba(239,68,68,0.08);border:1.5px solid rgba(239,68,68,0.2);border-radius:12px;color:var(--coral);font-size:13px;">
        ❌ Connection error. Please check your internet and try again.
      </div>`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Generate';
    }
  }
}

// =================== SYLLABUS LOGIC ===================

async function fetchSyllabi() {
    try {
        const res = await fetch(`${API_URL}syllabi/`, { credentials: 'include' });
        const data = await res.json();
        if (Array.isArray(data)) {
            syllabi = data;
            renderSyllabusList();
        }
    } catch (err) {
        console.error('Error fetching syllabi:', err);
    }
}

function renderSyllabusList() {
    const listContainer = document.getElementById('syllabus-list');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    if (syllabi.length === 0) {
        listContainer.innerHTML = `
            <div class="syl-empty-state">
                <div style="font-size:36px; margin-bottom:8px;">📚</div>
                <div style="font-size:13px; color:var(--ink-soft);">No syllabi yet. Create one to get started!</div>
            </div>`;
        return;
    }

    syllabi.forEach(s => {
        const date = new Date(s.updated_at);
        const dateStr = date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' }).toUpperCase();
        
        const card = document.createElement('div');
        card.className = `syl-card ${currentSyllabusId === s.id ? 'active' : ''}`;
        card.onclick = () => selectSyllabus(s.id);
        
        const subjectBadge = s.subject ? `<span class="syl-subject-badge">${s.subject}</span>` : '';
        
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div class="j-date">${dateStr}</div>
                ${subjectBadge}
            </div>
            <div class="j-title">${escapeHtml(s.title)}</div>
            <div class="syl-item-counts">
                <span>📝 ${s.text_count} notes</span>
                <span>🖼️ ${s.image_count} images</span>
                ${s.file_count ? `<span>📎 ${s.file_count} files</span>` : ''}
            </div>
        `;
        listContainer.appendChild(card);
    });
}

async function createNewSyllabus() {
    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({
                title: 'Untitled Syllabus',
                subject: '',
                description: ''
            })
        });
        const data = await res.json();
        if (res.ok) {
            currentSyllabusId = data.id;
            await fetchSyllabi();
            selectSyllabus(data.id);
        } else {
            alert(data.msg || 'Failed to create syllabus');
        }
    } catch (err) {
        console.error('Create syllabus error:', err);
        alert('Error creating syllabus: ' + err.message);
    }
}

async function selectSyllabus(id) {
    currentSyllabusId = id;
    
    try {
        const res = await fetch(`${API_URL}syllabi/${id}/`, { credentials: 'include' });
        const data = await res.json();
        
        // Show editor, hide empty state
        const emptyEditor = document.getElementById('syl-empty-editor');
        const editor = document.getElementById('syl-editor');
        if (emptyEditor) emptyEditor.style.display = 'none';
        if (editor) editor.style.display = 'block';
        
        // Fill editor fields
        const titleEl = document.getElementById('syl-title');
        const subjectEl = document.getElementById('syl-subject');
        const descEl = document.getElementById('syl-description');
        if (titleEl) titleEl.value = data.title || '';
        if (subjectEl) subjectEl.value = data.subject || '';
        if (descEl) descEl.value = data.description || '';
        
        // Render items
        renderSyllabusItems(data.items || []);
        
        // Reset to notes tab whenever a plan is opened
        sylSwitchTab('notes');

        // Hide forms and insights
        hideAddForms();
        const insightsPanel = document.getElementById('syl-insights-panel');
        if (insightsPanel) insightsPanel.style.display = 'none';
        
        // Update sidebar highlight
        renderSyllabusList();
    } catch (err) {
        console.error('Error loading syllabus:', err);
    }
}

function renderSyllabusItems(items) {
    const container = document.getElementById('syl-items-list');
    if (!container) return;
    container.innerHTML = '';

    if (items.length === 0) {
        container.innerHTML = `
            <div class="syl-no-items">
                <div style="font-size:28px; margin-bottom:8px;">📋</div>
                <div style="font-size:13px; color:var(--ink-soft);">No content yet. Add notes, images, files, PDFs, audio, video, or links above.</div>
            </div>`;
        return;
    }

    items.forEach((item, index) => {
        const el = document.createElement('div');
        el.className = `syl-item syl-item-${item.item_type}`;
        
        if (item.item_type === 'text') {
            el.innerHTML = `
                <div class="syl-item-header">
                    <div class="syl-item-badge text">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        NOTE #${index + 1}
                    </div>
                    <button class="syl-item-delete" onclick="deleteSyllabusItem(${item.id})" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="syl-item-content">${escapeHtml(item.content).replace(/\n/g, '<br>')}</div>
            `;
        } else if (item.item_type === 'image') {
            const imgUrl = item.image_url || '';
            el.innerHTML = `
                <div class="syl-item-header">
                    <div class="syl-item-badge image">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                        IMAGE #${index + 1}
                    </div>
                    <button class="syl-item-delete" onclick="deleteSyllabusItem(${item.id})" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                ${imgUrl ? `<img src="${imgUrl}" class="syl-item-image" alt="${escapeHtml(item.content || 'Study material')}">` : ''}
                ${item.content ? `<div class="syl-item-caption">${escapeHtml(item.content)}</div>` : ''}
            `;
        } else if (['file', 'pdf', 'audio', 'video'].includes(item.item_type)) {
            const fileUrl = item.file_url || '';
            const fileName = item.file_name || 'Unknown file';
            const fileSize = formatFileSize(item.file_size || 0);
            const fileIcon = getFileIcon(fileName, item.file_type || '');
            const typeLabel = item.item_type.toUpperCase();
            el.innerHTML = `
                <div class="syl-item-header">
                    <div class="syl-item-badge file">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        ${typeLabel} #${index + 1}
                    </div>
                    <button class="syl-item-delete" onclick="deleteSyllabusItem(${item.id})" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="syl-file-card">
                    <div class="syl-file-icon">${fileIcon}</div>
                    <div class="syl-file-info">
                        <div class="syl-file-name">${escapeHtml(fileName)}</div>
                        <div class="syl-file-meta">${fileSize}${item.file_type ? ' · ' + escapeHtml(item.file_type) : ''}</div>
                    </div>
                    <a href="${fileUrl}" target="_blank" download class="syl-file-download" title="Download">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    </a>
                </div>
                ${item.content ? `<div class="syl-item-caption">${escapeHtml(item.content)}</div>` : ''}
            `;
        } else if (item.item_type === 'link') {
            const url = item.content || '';
            const title = item.file_name || url;
            const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
            const linkIcon = isYouTube ? '▶️' : '🔗';
            el.innerHTML = `
                <div class="syl-item-header">
                    <div class="syl-item-badge link">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
                        LINK #${index + 1}
                    </div>
                    <button class="syl-item-delete" onclick="deleteSyllabusItem(${item.id})" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="syl-file-card">
                    <div class="syl-file-icon">${linkIcon}</div>
                    <div class="syl-file-info">
                        <div class="syl-file-name">${escapeHtml(title)}</div>
                        <div class="syl-file-meta" style="word-break:break-all;">${escapeHtml(url)}</div>
                    </div>
                    <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="syl-file-download" title="Open link">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>
                </div>
            `;
        }
        container.appendChild(el);
    });
}

function getFileIcon(filename, mimeType) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'pdf': '📕', 'doc': '📘', 'docx': '📘', 'txt': '📄', 'rtf': '📄',
        'xls': '📊', 'xlsx': '📊', 'csv': '📊',
        'ppt': '📙', 'pptx': '📙',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'py': '🐍', 'js': '⚡', 'ts': '🔷', 'html': '🌐', 'css': '🎨',
        'java': '☕', 'cpp': '⚙️', 'c': '⚙️', 'cs': '🟣', 'rb': '💎',
        'php': '🐘', 'go': '🐹', 'rs': '🦀', 'swift': '🍎',
        'json': '📋', 'xml': '📋', 'yaml': '📋', 'yml': '📋',
        'mp3': '🎵', 'wav': '🎵', 'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬',
        'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
        'md': '📝', 'sql': '🗃️',
    };
    return icons[ext] || '📄';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function saveSyllabusInfo() {
    if (!currentSyllabusId) return;
    
    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/`, {
            method: 'PUT',
            headers,
            credentials: 'include',
            body: JSON.stringify({
                title: document.getElementById('syl-title').value || 'Untitled Syllabus',
                subject: document.getElementById('syl-subject').value || '',
                description: document.getElementById('syl-description').value || ''
            })
        });
        if (res.ok) {
            await fetchSyllabi();
            showToast('Syllabus saved!');
        } else {
            alert('Save failed');
        }
    } catch (err) {
        console.error(err);
    }
}

async function deleteSyllabus() {
    if (!currentSyllabusId) return;
    if (!confirm('Are you sure you want to delete this syllabus and all its content?')) return;

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/`, {
            method: 'DELETE',
            headers,
            credentials: 'include'
        });
        if (res.ok) {
            currentSyllabusId = null;
            const editor = document.getElementById('syl-editor');
            const emptyEditor = document.getElementById('syl-empty-editor');
            if (editor) editor.style.display = 'none';
            if (emptyEditor) emptyEditor.style.display = 'flex';
            await fetchSyllabi();
        }
    } catch (err) {
        console.error(err);
    }
}

function showAddNoteForm() {
    hideAddForms();
    const form = document.getElementById('syl-note-form');
    const text = document.getElementById('syl-note-text');
    if (form) form.style.display = 'block';
    if (text) text.focus();
}

function showAddImageForm() {
    hideAddForms();
    const form = document.getElementById('syl-image-form');
    if (form) form.style.display = 'block';
}

function hideAddForms() {
    const noteForm = document.getElementById('syl-note-form');
    const imageForm = document.getElementById('syl-image-form');
    const fileForm = document.getElementById('syl-file-form');
    const linkForm = document.getElementById('syl-link-form');
    const monthlyForm = document.getElementById('syl-monthly-form');
    const imagePreview = document.getElementById('syl-image-preview');
    const filePreview = document.getElementById('syl-file-preview');
    const imgInput = document.getElementById('syl-image-input');
    const fileInput = document.getElementById('syl-file-input');
    if (noteForm) noteForm.style.display = 'none';
    if (imageForm) imageForm.style.display = 'none';
    if (fileForm) fileForm.style.display = 'none';
    if (linkForm) linkForm.style.display = 'none';
    if (monthlyForm) monthlyForm.style.display = 'none';
    if (imagePreview) imagePreview.style.display = 'none';
    if (filePreview) filePreview.style.display = 'none';
    if (imgInput) imgInput.value = '';
    if (fileInput) fileInput.value = '';
}

function resetMonthlyChat() {
    const msgs = document.getElementById('monthly-chat-messages');
    if (!msgs) return;
    msgs.innerHTML = `
        <div class="plan-chat-bubble ai">
            <div class="pcb-avatar">📅</div>
            <div class="pcb-text">Your monthly plan is ready! Want to adjust anything? Try:
                <br><span class="pcb-suggestion" onclick="useMonthlyPlanSuggestion(this)">Make Month 1 more beginner-friendly</span>
                <span class="pcb-suggestion" onclick="useMonthlyPlanSuggestion(this)">Add more practice days in Week 2</span>
                <span class="pcb-suggestion" onclick="useMonthlyPlanSuggestion(this)">I have exams, condense Month 2</span>
                <span class="pcb-suggestion" onclick="useMonthlyPlanSuggestion(this)">Add revision every Sunday</span>
            </div>
        </div>`;
}

function useMonthlyPlanSuggestion(el) {
    const input = document.getElementById('monthly-chat-input');
    if (input) { input.value = el.textContent; input.focus(); }
}

function addMonthlyMessage(role, html) {
    const msgs = document.getElementById('monthly-chat-messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = `plan-chat-bubble ${role}`;
    if (role === 'ai') {
        div.innerHTML = `<div class="pcb-avatar">📅</div><div class="pcb-text">${html}</div>`;
    } else {
        div.innerHTML = `<div class="pcb-text">${escapeHtml(html)}</div>`;
    }
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}

function addMonthlyTyping() {
    const msgs = document.getElementById('monthly-chat-messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'plan-chat-bubble ai';
    div.id = 'monthly-chat-typing';
    div.innerHTML = `<div class="pcb-avatar">📅</div><div class="pcb-text"><span class="plan-typing"><span></span><span></span><span></span></span></div>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}

async function sendMonthlyChat() {
    const input = document.getElementById('monthly-chat-input');
    const sendBtn = document.getElementById('monthly-chat-send-btn');
    const message = input ? input.value.trim() : '';
    if (!message || !currentSyllabusId) return;

    addMonthlyMessage('user', message);
    monthlyChatHistory.push({ role: 'user', content: message });
    if (input) input.value = '';
    if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '0.5'; }
    addMonthlyTyping();

    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/monthly-plan-chat/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({ message, plan: currentMonthlyPlanText, history: monthlyChatHistory.slice(-10) })
        });
        const data = await res.json();
        const typing = document.getElementById('monthly-chat-typing');
        if (typing) typing.remove();

        if (res.ok && data.reply) {
            addMonthlyMessage('ai', mdToHtml(data.reply));
            monthlyChatHistory.push({ role: 'assistant', content: data.reply });
        } else {
            addMonthlyMessage('ai', `❌ ${data.error || 'Something went wrong. Please try again.'}`);
        }
    } catch (err) {
        console.error(err);
        const typing = document.getElementById('monthly-chat-typing');
        if (typing) typing.remove();
        addMonthlyMessage('ai', '❌ Connection error. Please try again.');
    } finally {
        if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = '1'; }
    }
}

function showMonthlyPlanForm() {
    hideAddForms();
    const form = document.getElementById('syl-monthly-form');
    if (form) form.style.display = 'block';
}

function hideMonthlyForm() {
    const form = document.getElementById('syl-monthly-form');
    if (form) form.style.display = 'none';
}

async function generateMonthlyPlan() {
    if (!currentSyllabusId) return;
    const monthsInput = document.getElementById('syl-months-input');
    const months = Math.max(1, Math.min(parseInt(monthsInput ? monthsInput.value : 2) || 2, 6));

    const panel = document.getElementById('syl-monthly-panel');
    const body = document.getElementById('syl-monthly-body');
    const btn = document.getElementById('syl-btn-monthly');

    hideMonthlyForm();
    if (panel) panel.style.display = 'block';
    if (body) body.innerHTML = `
        <div class="syl-loading">
            <div class="syl-loading-spinner"></div>
            <div style="margin-top:16px; font-size:14px; color:var(--ink-soft);">Sage is building your ${months}-month plan...</div>
            <div style="font-size:12px; color:var(--ink-soft); opacity:0.6; margin-top:4px;">This may take a few seconds</div>
        </div>`;
    if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }

    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/monthly-plan/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({ months })
        });
        const data = await res.json();

        if (res.ok && data.plan) {
            if (body) body.innerHTML = `<div class="syl-insights-content">${mdToHtml(data.plan)}</div>`;
            currentMonthlyPlanText = data.plan;
            monthlyChatHistory = [];
            resetMonthlyChat();
            const chatSection = document.getElementById('monthly-chat-section');
            if (chatSection) chatSection.style.display = 'flex';
        } else {
            if (body) body.innerHTML = `<div class="syl-insights-error">❌ ${data.error || 'Failed to generate plan. Make sure you have added some notes first.'}</div>`;
        }
    } catch (err) {
        console.error(err);
        if (body) body.innerHTML = `<div class="syl-insights-error">❌ Connection error. Please try again.</div>`;
    } finally {
        if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    }
}

function showAddFileForm(type) {
    hideAddForms();
    const form = document.getElementById('syl-file-form');
    if (!form) return;
    form.style.display = 'block';

    const fileInput = document.getElementById('syl-file-input');
    const dropLabel = form.querySelector('[data-file-label]');
    const dropHint = form.querySelector('[data-file-hint]');
    const uploadBtn = form.querySelector('[data-upload-btn]');

    const configs = {
        pdf:   { accept: '.pdf',               label: 'Click to upload or drag & drop a PDF', hint: 'PDF files only', btn: 'Upload PDF',   typeVal: 'pdf' },
        audio: { accept: 'audio/*,.mp3,.wav,.m4a,.ogg,.flac', label: 'Click to upload or drag & drop audio', hint: 'MP3, WAV, M4A, OGG, FLAC', btn: 'Upload Audio', typeVal: 'audio' },
        video: { accept: 'video/*,.mp4,.mov,.webm,.avi',       label: 'Click to upload or drag & drop video', hint: 'MP4, MOV, WEBM, AVI',      btn: 'Upload Video', typeVal: 'video' },
    };

    const cfg = configs[type] || { accept: '', label: 'Click to upload or drag & drop any file', hint: 'PDF, DOCX, PPTX, XLSX, ZIP, TXT, code files — any format', btn: 'Upload File', typeVal: 'file' };

    if (fileInput) fileInput.accept = cfg.accept;
    if (dropLabel) dropLabel.textContent = cfg.label;
    if (dropHint) dropHint.textContent = cfg.hint;
    if (uploadBtn) uploadBtn.textContent = cfg.btn;
    form.dataset.fileType = cfg.typeVal;
}

function showAddLinkForm() {
    hideAddForms();
    const form = document.getElementById('syl-link-form');
    if (form) form.style.display = 'block';
    const urlInput = document.getElementById('syl-link-url');
    if (urlInput) urlInput.focus();
}

async function addLinkNote() {
    if (!currentSyllabusId) return;
    const urlEl = document.getElementById('syl-link-url');
    const titleEl = document.getElementById('syl-link-title');
    const url = urlEl ? urlEl.value.trim() : '';
    const title = titleEl ? titleEl.value.trim() : '';
    if (!url) { alert('Please enter a URL'); return; }

    const formData = new FormData();
    formData.append('item_type', 'link');
    formData.append('content', url);
    formData.append('file_name', title);

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/items/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: formData
        });
        if (res.ok) {
            if (urlEl) urlEl.value = '';
            if (titleEl) titleEl.value = '';
            hideAddForms();
            await selectSyllabus(currentSyllabusId);
            showToast('Link added!');
        } else {
            const data = await res.json();
            alert(data.msg || 'Failed to add link');
        }
    } catch (err) {
        console.error(err);
        alert('Error adding link');
    }
}

function previewImage(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.getElementById('syl-preview-img');
            const preview = document.getElementById('syl-image-preview');
            if (img) img.src = e.target.result;
            if (preview) preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

function previewFile(event) {
    const file = event.target.files[0];
    if (file) {
        const preview = document.getElementById('syl-file-preview');
        const nameEl = document.getElementById('syl-fp-name');
        const sizeEl = document.getElementById('syl-fp-size');
        const iconEl = document.getElementById('syl-fp-icon');
        if (nameEl) nameEl.textContent = file.name;
        if (sizeEl) sizeEl.textContent = formatFileSize(file.size);
        if (iconEl) iconEl.textContent = getFileIcon(file.name, file.type);
        if (preview) preview.style.display = 'flex';
    }
}

async function addTextNote() {
    if (!currentSyllabusId) return;
    const textEl = document.getElementById('syl-note-text');
    const text = textEl ? textEl.value.trim() : '';
    if (!text) { alert('Please enter some text'); return; }

    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/items/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({ item_type: 'text', content: text })
        });
        if (res.ok) {
            if (textEl) textEl.value = '';
            hideAddForms();
            await selectSyllabus(currentSyllabusId);
            showToast('Note added!');
        }
    } catch (err) {
        console.error(err);
        alert('Error adding note');
    }
}

async function addImageNote() {
    if (!currentSyllabusId) return;
    const fileInput = document.getElementById('syl-image-input');
    const captionEl = document.getElementById('syl-image-caption');
    const caption = captionEl ? captionEl.value.trim() : '';
    
    if (!fileInput || !fileInput.files[0]) { alert('Please select an image'); return; }

    const formData = new FormData();
    formData.append('item_type', 'image');
    formData.append('image', fileInput.files[0]);
    formData.append('content', caption);

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/items/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: formData
        });
        if (res.ok) {
            hideAddForms();
            if (captionEl) captionEl.value = '';
            await selectSyllabus(currentSyllabusId);
            showToast('Image uploaded!');
        }
    } catch (err) {
        console.error(err);
        alert('Error uploading image');
    }
}

async function addFileNote() {
    if (!currentSyllabusId) return;
    const fileInput = document.getElementById('syl-file-input');
    const captionEl = document.getElementById('syl-file-caption');
    const caption = captionEl ? captionEl.value.trim() : '';
    const fileForm = document.getElementById('syl-file-form');
    const itemType = (fileForm && fileForm.dataset.fileType) || 'file';

    if (!fileInput || !fileInput.files[0]) { alert('Please select a file'); return; }

    const formData = new FormData();
    formData.append('item_type', itemType);
    formData.append('file', fileInput.files[0]);
    formData.append('content', caption);

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/items/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: formData
        });
        if (res.ok) {
            hideAddForms();
            if (captionEl) captionEl.value = '';
            await selectSyllabus(currentSyllabusId);
            showToast(`${itemType.charAt(0).toUpperCase() + itemType.slice(1)} uploaded!`);
        } else {
            const data = await res.json();
            alert(data.msg || 'Upload failed');
        }
    } catch (err) {
        console.error(err);
        alert('Error uploading file');
    }
}

async function deleteSyllabusItem(itemId) {
    if (!currentSyllabusId) return;
    if (!confirm('Delete this item?')) return;

    const headers = {};
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/items/${itemId}/`, {
            method: 'DELETE',
            headers,
            credentials: 'include'
        });
        if (res.ok) {
            await selectSyllabus(currentSyllabusId);
        }
    } catch (err) {
        console.error(err);
    }
}

let currentPlanText = '';
let planChatHistory = [];
let currentMonthlyPlanText = '';
let monthlyChatHistory = [];

async function generateInsights() {
    if (!currentSyllabusId) return;

    const insightsPanel = document.getElementById('syl-insights-panel');
    const insightsBody = document.getElementById('syl-insights-body');
    const planChatSection = document.getElementById('plan-chat-section');
    const btn = document.getElementById('syl-btn-insights');

    insightsPanel.style.display = 'block';
    if (planChatSection) planChatSection.style.display = 'none';
    insightsBody.innerHTML = `
        <div class="syl-loading">
            <div class="syl-loading-spinner"></div>
            <div style="margin-top:16px; font-size:14px; color:var(--ink-soft);">Sage is analyzing your study material...</div>
            <div style="font-size:12px; color:var(--ink-soft); opacity:0.6; margin-top:4px;">This may take a few seconds</div>
        </div>`;
    btn.disabled = true;
    btn.style.opacity = '0.5';

    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/insights/`, {
            method: 'POST', headers, credentials: 'include', body: JSON.stringify({})
        });
        const data = await res.json();

        if (res.ok && data.insights) {
            insightsBody.innerHTML = `<div class="syl-insights-content">${mdToHtml(data.insights)}</div>`;
            currentPlanText = data.insights;
            planChatHistory = [];
            resetPlanChat();
            if (planChatSection) planChatSection.style.display = 'flex';
        } else {
            insightsBody.innerHTML = `<div class="syl-insights-error">❌ ${data.error || 'Failed to generate insights. Make sure you have added some notes first.'}</div>`;
        }
    } catch (err) {
        console.error(err);
        insightsBody.innerHTML = `<div class="syl-insights-error">❌ Connection error. Please try again.</div>`;
    } finally {
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

function resetPlanChat() {
    const msgs = document.getElementById('plan-chat-messages');
    if (!msgs) return;
    msgs.innerHTML = `
        <div class="plan-chat-bubble ai">
            <div class="pcb-avatar">✨</div>
            <div class="pcb-text">Your plan is ready! Want to adjust anything? Try:
                <br><span class="pcb-suggestion" onclick="usePlanSuggestion(this)">Make it more beginner-friendly</span>
                <span class="pcb-suggestion" onclick="usePlanSuggestion(this)">I only have 3 days, shorten the plan</span>
                <span class="pcb-suggestion" onclick="usePlanSuggestion(this)">Add practical exercises</span>
                <span class="pcb-suggestion" onclick="usePlanSuggestion(this)">Focus on the most important 20%</span>
            </div>
        </div>`;
}

function usePlanSuggestion(el) {
    const input = document.getElementById('plan-chat-input');
    if (input) { input.value = el.textContent; input.focus(); }
}

function addPlanMessage(role, html) {
    const msgs = document.getElementById('plan-chat-messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = `plan-chat-bubble ${role}`;
    if (role === 'ai') {
        div.innerHTML = `<div class="pcb-avatar">✨</div><div class="pcb-text">${html}</div>`;
    } else {
        div.innerHTML = `<div class="pcb-text">${escapeHtml(html)}</div>`;
    }
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}

function addPlanTyping() {
    const msgs = document.getElementById('plan-chat-messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'plan-chat-bubble ai';
    div.id = 'plan-chat-typing';
    div.innerHTML = `<div class="pcb-avatar">✨</div><div class="pcb-text"><span class="plan-typing"><span></span><span></span><span></span></span></div>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}

async function sendPlanChat() {
    const input = document.getElementById('plan-chat-input');
    const sendBtn = document.getElementById('plan-chat-send-btn');
    const message = input ? input.value.trim() : '';
    if (!message || !currentSyllabusId) return;

    addPlanMessage('user', message);
    planChatHistory.push({ role: 'user', content: message });
    if (input) input.value = '';
    if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = '0.5'; }
    addPlanTyping();

    const headers = { 'Content-Type': 'application/json' };
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    try {
        const res = await fetch(`${API_URL}syllabi/${currentSyllabusId}/plan-chat/`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({ message, plan: currentPlanText, history: planChatHistory.slice(-10) })
        });
        const data = await res.json();
        const typing = document.getElementById('plan-chat-typing');
        if (typing) typing.remove();

        if (res.ok && data.reply) {
            addPlanMessage('ai', mdToHtml(data.reply));
            planChatHistory.push({ role: 'assistant', content: data.reply });
        } else {
            addPlanMessage('ai', `❌ ${data.error || 'Something went wrong. Please try again.'}`);
        }
    } catch (err) {
        console.error(err);
        const typing = document.getElementById('plan-chat-typing');
        if (typing) typing.remove();
        addPlanMessage('ai', '❌ Connection error. Please try again.');
    } finally {
        if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = '1'; }
    }
}

// Simple toast notification
function showToast(msg) {
    let toast = document.getElementById('syl-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'syl-toast';
        toast.className = 'syl-toast';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
}

// Drag and drop for syllabus images
const dropzone = document.getElementById('syl-dropzone');
if (dropzone) {
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('syl-image-input').files = files;
            previewImage({ target: { files: [files[0]] } });
        }
    });
}

// Drag and drop for syllabus files
const fileDropzone = document.getElementById('syl-file-dropzone');
if (fileDropzone) {
    fileDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropzone.classList.add('dragover');
    });
    fileDropzone.addEventListener('dragleave', () => {
        fileDropzone.classList.remove('dragover');
    });
    fileDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        fileDropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const input = document.getElementById('syl-file-input');
            if (input) input.files = files;
            previewFile({ target: { files: [files[0]] } });
        }
    });
}

// =================== QUIZ SETUP FUNCTIONS ===================
function _hideAllArenaScreens(){
  ['arena-landing-screen','quiz-setup-screen','mock-setup-screen','test-hub-screen','quiz-screen','result-screen']
    .forEach(id=>{ const el=document.getElementById(id); if(el) el.style.display='none'; });
}

function showArenaLanding(){
  _hideAllArenaScreens();
  document.getElementById('arena-landing-screen').style.display='block';
}

function showQuizSetup(){
  _hideAllArenaScreens();
  document.getElementById('quiz-setup-screen').style.display='block';
  loadTopicPicker();
}

function showMockSetup(){
  _hideAllArenaScreens();
  document.getElementById('mock-setup-screen').style.display='block';
}

function showTestHub(){
  _hideAllArenaScreens();
  document.getElementById('test-hub-screen').style.display='block';
}

function selectTopic(topic, cardEl){
  if(!topic) { _selectedTopic = null; return; }
  _selectedTopic = topic;
  // Deselect all cards
  document.querySelectorAll('.topic-pick-card').forEach(c=>{
    c.style.borderColor = 'var(--line)';
    c.style.background = 'var(--bg-soft)';
  });
  // Highlight selected card
  if(cardEl && cardEl.classList && cardEl.classList.contains('topic-pick-card')){
    cardEl.style.borderColor = '#6366f1';
    cardEl.style.background = 'rgba(99,102,241,0.08)';
    // Clear custom input if a card is picked
    const ci = document.getElementById('custom-topic-input');
    if(ci) ci.value = '';
  }
  const label = topic.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  const btn = document.getElementById('generate-quiz-btn');
  if(btn){
    btn.textContent = `Generate "${label}" Quiz →`;
    btn.style.opacity='1';
    btn.style.cursor='pointer';
    btn.disabled=false;
  }
  const preview = document.getElementById('quiz-preview-box');
  if(preview){
    preview.innerHTML = `<div style="padding:14px 18px;background:rgba(99,102,241,0.08);border:1.5px solid #6366f1;border-radius:10px;">
      <div style="font-size:11px;font-family:'Space Mono';color:#6366f1;margin-bottom:6px;">SELECTED TOPIC</div>
      <div style="font-family:'Playfair Display';font-weight:700;font-size:18px;color:var(--ink);">${label}</div>
      <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">${_selectedQCount} questions · +4/−1 marking</div>
    </div>`;
  }
}

function setQCount(n, btnEl){
  _selectedQCount = n;
  document.querySelectorAll('.qcount-opt').forEach(b=>b.classList.remove('active'));
  if(btnEl) btnEl.classList.add('active');
  const preview = document.getElementById('quiz-preview-box');
  if(preview && _selectedTopic){
    const label = _selectedTopic.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
    preview.innerHTML = `<div style="padding:14px 18px;background:rgba(99,102,241,0.08);border:1.5px solid #6366f1;border-radius:10px;">
      <div style="font-size:11px;font-family:'Space Mono';color:#6366f1;margin-bottom:6px;">SELECTED TOPIC</div>
      <div style="font-family:'Playfair Display';font-weight:700;font-size:18px;color:var(--ink);">${label}</div>
      <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">${n} questions · +4/−1 marking</div>
    </div>`;
  }
}

function generateAndStart(){
  if(!_selectedTopic) return;
  const btn = document.getElementById('generate-quiz-btn');
  if(btn){ btn.textContent='Generating…'; btn.disabled=true; btn.style.opacity='0.6'; }

  fetch(`/api/analytics/generate-quiz/?topic=${encodeURIComponent(_selectedTopic)}&count=${_selectedQCount}`)
    .then(r=>r.json())
    .then(data=>{
      if(data.error || !data.questions || data.questions.length === 0){
        alert(data.error || 'Could not generate questions. Please try again.');
        if(btn){ btn.textContent='Generate "'+_selectedTopic+'" Quiz →'; btn.disabled=false; btn.style.opacity='1'; }
        return;
      }
      _smartQuizQuestions = data.questions.map(q=>({
        q: q.q,
        opts: q.opts,
        correct: q.correct,
        diff: q.diff || 'MEDIUM · +4/−1',
        hint: q.hint || 'Think carefully about ' + _selectedTopic.replace(/_/g,' ') + '.',
        explain: q.explain || 'The correct answer is: ' + q.opts[q.correct],
        card_id: q.card_id || null,
      }));
      _smartQuizMeta = { topic: _selectedTopic, prediction: data.prediction };
      _quizDuration = 600;
      const qlbl = document.getElementById('quiz-screen-label');
      if(qlbl) qlbl.textContent = 'Quick Quiz · ' + _selectedTopic.replace(/_/g,' ') + ' · 10 min';
      const _pc = document.getElementById('ml-prediction-card');
      if(_pc && data.prediction){
        _pc.style.display='block';
        document.getElementById('ml-pred-score').textContent = data.prediction.predicted_score + ' / ' + data.prediction.max_score;
        document.getElementById('ml-pred-accuracy').textContent = 'Predicted accuracy: ' + data.prediction.predicted_accuracy + '%';
        document.getElementById('ml-pred-confidence').textContent = 'Model confidence: ' + data.prediction.confidence;
      }
      startTest();
    })
    .catch(()=>{
      alert('Could not generate quiz. Make sure you are logged in and have flashcards.');
      if(btn){ btn.textContent='Generate Quiz →'; btn.disabled=false; btn.style.opacity='1'; }
    });
}

function startSmartQuiz(topic, count){
  _selectedTopic = topic;
  _selectedQCount = count || 5;
  generateAndStart();
}

function retryQuiz(){
  if(_smartQuizMeta){
    const t = _smartQuizMeta.topic;
    _selectedTopic = t;
    generateAndStart();
  } else {
    exitTest();
    startTest();
  }
}

function loadTopicPicker(){
  const grid = document.getElementById('topic-picker-grid');
  if(!grid) return;

  fetch('/api/flashcard-subjects/')
    .then(r=>r.json())
    .then(data=>{
      const subjects = data.subjects || [];
      if(subjects.length === 0){
        // Show popular topic suggestions even without flashcards
        const suggestions = ['Data Science','Machine Learning','Python Programming','Mathematics','Statistics','Computer Science','Physics','History','Economics','Biology'];
        grid.innerHTML = suggestions.map(s=>{
          const topic = s.toLowerCase().replace(/ /g,'_');
          return `<div class="topic-pick-card" data-topic="${s}"
            onclick="selectTopic('${s}',this)"
            style="border:2px solid var(--line);border-radius:12px;padding:18px 20px;cursor:pointer;background:var(--bg-soft);">
            <div style="font-family:'Playfair Display';font-size:17px;font-weight:700;margin-bottom:8px;color:var(--ink);">${s}</div>
            <div class="tpc-pct" style="font-size:13px;color:var(--ink-soft);">AI generates questions</div>
            <div class="tpc-badge" style="font-size:11px;color:#6366f1;margin-top:10px;font-weight:600;">Click to test</div>
          </div>`;
        }).join('');
        return;
      }
      // Render one card per subject
      grid.innerHTML = subjects.map(s=>{
        const topic = s.subject;
        const label = topic.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
        return `<div class="topic-pick-card" data-topic="${topic}"
          onclick="selectTopic('${topic.replace(/'/g,"\\'")}',this)"
          style="border:2px solid var(--line);border-radius:12px;padding:18px 20px;cursor:pointer;background:var(--bg-soft);">
          <div style="font-family:'Playfair Display';font-size:17px;font-weight:700;margin-bottom:8px;color:var(--ink);">${label}</div>
          <div class="tpc-pct" style="font-size:13px;color:var(--ink-soft);">AI generates questions</div>
          <div class="tpc-badge" style="font-size:11px;color:#6366f1;margin-top:10px;font-weight:600;">Click to test</div>
        </div>`;
      }).join('');
      // Enrich with ML predicted scores
      fetch('/api/analytics/smart-topics/')
        .then(r=>r.json())
        .then(mlData=>{
          if(!mlData.topics) return;
          mlData.topics.forEach(t=>{
            const card = document.querySelector(`.topic-pick-card[data-topic="${t.topic}"]`);
            if(!card) return;
            const pct = card.querySelector('.tpc-pct');
            if(pct) pct.textContent = `${t.predicted_score_pct}% predicted · ${t.reason}`;
            const badge = card.querySelector('.tpc-badge');
            if(badge && t.priority > 0.5) badge.textContent = '⚡ High priority';
          });
        })
        .catch(()=>{});
    })
    .catch(()=>{
      // Keep whatever is in the grid already
    });
}

// =================== MOCK TEST FUNCTIONS ===================
function setMockTopic(topic){
  const inp = document.getElementById('mock-topic-input');
  if(inp) inp.value = topic;
  _mockTopic = topic;
  updateMockPreview();
}

function setMockDuration(mins, btnEl){
  _mockDuration = mins;
  document.querySelectorAll('.mock-dur-opt').forEach(b=>{
    b.style.borderColor='var(--line)';
    b.style.background='';
  });
  if(btnEl){ btnEl.style.borderColor='var(--gold)'; btnEl.style.background='rgba(251,191,36,0.1)'; }
  updateMockPreview();
}

function setMockCount(n, btnEl){
  _mockCount = n;
  document.querySelectorAll('.mock-count-opt').forEach(b=>{
    b.style.borderColor='var(--line)';
    b.style.background='';
  });
  if(btnEl){ btnEl.style.borderColor='var(--gold)'; btnEl.style.background='rgba(251,191,36,0.1)'; }
  updateMockPreview();
}

function adjustMockType(type, delta){
  const map = { mcq:'_mockMcq', tf:'_mockTf', fitb:'_mockFitb', ar:'_mockAr' };
  const maxMap = { mcq:30, tf:20, fitb:20, ar:15 };
  if(!map[type]) return;
  let val = { mcq:_mockMcq, tf:_mockTf, fitb:_mockFitb, ar:_mockAr }[type];
  val = Math.max(0, Math.min(maxMap[type], val + delta));
  if(type==='mcq')  _mockMcq  = val;
  if(type==='tf')   _mockTf   = val;
  if(type==='fitb') _mockFitb = val;
  if(type==='ar')   _mockAr   = val;
  const numEl = document.getElementById(`mock-${type}-val`);
  const rangeEl = document.getElementById(`mock-${type}-range`);
  if(numEl)   numEl.textContent = val;
  if(rangeEl) rangeEl.value    = val;
  _mockCount = _mockMcq + _mockTf + _mockFitb + _mockAr;
  const badge = document.getElementById('mock-total-badge');
  if(badge) badge.textContent = _mockCount;
  updateMockPreview();
}

function syncMockType(type, value){
  const val = parseInt(value, 10);
  if(type==='mcq')  _mockMcq  = val;
  if(type==='tf')   _mockTf   = val;
  if(type==='fitb') _mockFitb = val;
  if(type==='ar')   _mockAr   = val;
  const numEl = document.getElementById(`mock-${type}-val`);
  if(numEl) numEl.textContent = val;
  _mockCount = _mockMcq + _mockTf + _mockFitb + _mockAr;
  const badge = document.getElementById('mock-total-badge');
  if(badge) badge.textContent = _mockCount;
  updateMockPreview();
}

function updateMockPreview(){
  const inp = document.getElementById('mock-topic-input');
  if(inp) _mockTopic = inp.value.trim();
  const preview = document.getElementById('mock-preview');
  const btn = document.getElementById('generate-mock-btn');
  if(!_mockTopic){
    if(preview) preview.innerHTML='<div style="color:var(--ink-soft);font-size:13px;">Fill in the topic above to see your test breakdown.</div>';
    if(btn){ btn.disabled=true; btn.style.opacity='0.4'; btn.style.cursor='not-allowed'; btn.textContent='↑ Enter a topic to generate your mock test'; }
    return;
  }
  const mcq   = _mockMcq;
  const tf    = _mockTf;
  const fitb  = _mockFitb;
  const ar    = _mockAr;
  _mockCount  = mcq + tf + fitb + ar;
  const label = _mockTopic.replace(/\b\w/g,c=>c.toUpperCase());
  if(preview) preview.innerHTML = `
    <div style="font-family:'Playfair Display';font-size:18px;font-weight:700;margin-bottom:14px;color:var(--ink);">${label} · ${_mockCount} Questions · ${_mockDuration} min</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;">
      <div style="padding:12px 16px;border-radius:10px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);">
        <div style="font-size:11px;color:#6366f1;font-weight:600;margin-bottom:2px;">MCQ</div>
        <div style="font-size:22px;font-weight:700;font-family:'Playfair Display';">${mcq}</div>
        <div style="font-size:11px;color:var(--ink-soft);">4-option questions</div>
      </div>
      <div style="padding:12px 16px;border-radius:10px;background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.3);">
        <div style="font-size:11px;color:var(--mint);font-weight:600;margin-bottom:2px;">TRUE / FALSE</div>
        <div style="font-size:22px;font-weight:700;font-family:'Playfair Display';">${tf}</div>
        <div style="font-size:11px;color:var(--ink-soft);">2-option statements</div>
      </div>
      <div style="padding:12px 16px;border-radius:10px;background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);">
        <div style="font-size:11px;color:var(--gold);font-weight:600;margin-bottom:2px;">FILL IN BLANK</div>
        <div style="font-size:22px;font-weight:700;font-family:'Playfair Display';">${fitb}</div>
        <div style="font-size:11px;color:var(--ink-soft);">complete the statement</div>
      </div>
      <div style="padding:12px 16px;border-radius:10px;background:rgba(251,113,133,0.1);border:1px solid rgba(251,113,133,0.3);">
        <div style="font-size:11px;color:var(--coral);font-weight:600;margin-bottom:2px;">ASSERTION-REASON</div>
        <div style="font-size:22px;font-weight:700;font-family:'Playfair Display';">${ar}</div>
        <div style="font-size:11px;color:var(--ink-soft);">evaluate both statements</div>
      </div>
    </div>`;
  if(btn){
    btn.disabled=false;
    btn.style.opacity='1';
    btn.style.cursor='pointer';
    btn.textContent=`Generate ${label} Mock Test →`;
  }
}

function generateMock(){
  const inp = document.getElementById('mock-topic-input');
  if(inp) _mockTopic = inp.value.trim();
  if(!_mockTopic) return;
  const btn = document.getElementById('generate-mock-btn');
  if(btn){ btn.textContent='Generating your mock test… (this may take 15–30s)'; btn.disabled=true; btn.style.opacity='0.7'; }

  fetch(`/api/analytics/generate-mock/?topic=${encodeURIComponent(_mockTopic)}&mcq=${_mockMcq}&tf=${_mockTf}&fitb=${_mockFitb}&ar=${_mockAr}&duration=${_mockDuration}`)
    .then(r=>r.json())
    .then(data=>{
      if(data.error || !data.questions || data.questions.length===0){
        alert(data.error || 'Could not generate mock test. Please try again.');
        if(btn){ btn.textContent=`Generate ${_mockTopic} Mock Test →`; btn.disabled=false; btn.style.opacity='1'; }
        return;
      }
      _smartQuizQuestions = data.questions.map(q=>({
        q: q.q,
        opts: q.opts,
        correct: q.correct,
        diff: q.diff || 'MCQ · MEDIUM · +4/−1',
        hint: q.hint || `Think carefully about ${_mockTopic}.`,
        explain: q.explain || `The correct answer is: ${q.opts[q.correct]}`,
        card_id: null,
        qtype: q.qtype || 'MCQ',
      }));
      _smartQuizMeta = { topic: _mockTopic, prediction: data.prediction };
      _quizDuration = _mockDuration * 60;

      // Update quiz screen label
      const lbl = document.getElementById('quiz-screen-label');
      if(lbl) lbl.textContent = `Mock Test · ${_mockTopic} · ${_mockDuration} min`;

      // Show ML prediction card
      const _pc = document.getElementById('ml-prediction-card');
      if(_pc && data.prediction){
        _pc.style.display='block';
        document.getElementById('ml-pred-score').textContent = data.prediction.predicted_score+' / '+data.prediction.max_score;
        document.getElementById('ml-pred-accuracy').textContent='Predicted accuracy: '+data.prediction.predicted_accuracy+'%';
        document.getElementById('ml-pred-confidence').textContent='Model confidence: '+data.prediction.confidence;
      }
      startTest();
    })
    .catch(()=>{
      alert('Could not connect to the server. Please try again.');
      if(btn){ btn.textContent=`Generate ${_mockTopic} Mock Test →`; btn.disabled=false; btn.style.opacity='1'; }
    });
}

// =================== CALENDAR ===================
const _calMonthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const _calDayNames   = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

let _calYear, _calMonth, _calData = {}, _calReminders = [], _calPlanTasks = {}, _calSelectedDate = null;

function _fmtCalDate(ds) {
  const d = new Date(ds + 'T00:00:00');
  return d.getDate() + ' ' + _calMonthNames[d.getMonth()].slice(0, 3);
}

function calLoad(y, m) {
  const now = new Date();
  // Preserve already-browsed month unless caller explicitly passes a target
  _calYear  = y || _calYear  || now.getFullYear();
  _calMonth = m || _calMonth || (now.getMonth() + 1);
  fetch(`/api/calendar/?year=${_calYear}&month=${_calMonth}`)
    .then(r => r.json())
    .then(data => {
      _calData      = data.activity || {};
      _calReminders = data.reminders || [];
      _calPlanTasks = data.scheduled_tasks || {};
      document.getElementById('cal-streak-count').textContent = data.streak || 0;
      document.getElementById('cal-month-label').textContent  = _calMonthNames[_calMonth - 1] + ' ' + _calYear;
      _calRenderGrid(data.today);
      _calRenderUpcoming();
      if (_calSelectedDate) _calSelectDay(_calSelectedDate);
    })
    .catch(() => {});
}

function calPrevMonth() {
  let m = _calMonth - 1, y = _calYear;
  if (m < 1) { m = 12; y--; }
  calLoad(y, m);
}
function calNextMonth() {
  let m = _calMonth + 1, y = _calYear;
  if (m > 12) { m = 1; y++; }
  calLoad(y, m);
}

function _calRenderGrid(today) {
  const grid = document.getElementById('cal-grid');
  if (!grid) return;
  grid.innerHTML = '';

  // First day of month (JS: 0=Sun … 6=Sat → convert to Mon-first)
  const first = new Date(_calYear, _calMonth - 1, 1);
  const last  = new Date(_calYear, _calMonth, 0);
  let startDow = first.getDay(); // 0=Sun
  startDow = startDow === 0 ? 6 : startDow - 1; // Mon=0 … Sun=6

  // Pad with prev-month days
  for (let i = 0; i < startDow; i++) {
    const d = new Date(_calYear, _calMonth - 1, -startDow + i + 1);
    grid.appendChild(_calCell(d, true, today));
  }
  // Current month
  for (let d = 1; d <= last.getDate(); d++) {
    const date = new Date(_calYear, _calMonth - 1, d);
    grid.appendChild(_calCell(date, false, today));
  }
  // Pad to fill last row
  const filled = startDow + last.getDate();
  const remainder = filled % 7 === 0 ? 0 : 7 - (filled % 7);
  for (let i = 1; i <= remainder; i++) {
    const d = new Date(_calYear, _calMonth, i);
    grid.appendChild(_calCell(d, true, today));
  }
}

function _calDateStr(date) {
  return date.getFullYear() + '-' +
    String(date.getMonth() + 1).padStart(2, '0') + '-' +
    String(date.getDate()).padStart(2, '0');
}

function _calCell(date, otherMonth, today) {
  const ds    = _calDateStr(date);
  const act   = _calData[ds] || {};
  const total = act.total || 0;
  const rems  = _calReminders.filter(r => r.date === ds);
  const hasTasks = (_calPlanTasks[ds] || []).length > 0 || (act.tasks || 0) > 0;

  const cell = document.createElement('div');
  cell.className = 'cal-cell' +
    (otherMonth ? ' other-month' : '') +
    (ds === today ? ' today' : '') +
    (ds === _calSelectedDate ? ' selected' : '');
  cell.dataset.date = ds;
  if (!otherMonth) cell.onclick = () => _calSelectDay(ds);

  // Activity intensity background
  if (total > 0 && !otherMonth) {
    const opacity = Math.min(0.08 + (total / 20) * 0.22, 0.3);
    const bg = document.createElement('div');
    bg.className = 'cal-activity-bg';
    bg.style.background = `rgba(99,102,241,${opacity})`;
    cell.appendChild(bg);
  }

  const num = document.createElement('div');
  num.className = 'cal-day-num';
  num.textContent = date.getDate();
  cell.appendChild(num);

  // Dots row
  const dots = document.createElement('div');
  dots.className = 'cal-cell-dots';
  if (total > 0)     dots.innerHTML += `<span class="cal-dot" style="background:var(--primary);opacity:${Math.min(0.4 + total * 0.06, 1)};"></span>`;
  if (rems.length)   dots.innerHTML += `<span class="cal-dot" style="background:#f59e0b;"></span>`;
  if (hasTasks)      dots.innerHTML += `<span class="cal-dot" style="background:#34d399;"></span>`;
  cell.appendChild(dots);

  return cell;
}

function _calSelectDay(ds) {
  // Deselect previous
  if (_calSelectedDate) {
    const prev = document.querySelector(`.cal-cell[data-date="${_calSelectedDate}"]`);
    if (prev) prev.classList.remove('selected');
  }
  _calSelectedDate = ds;
  const cell = document.querySelector(`.cal-cell[data-date="${ds}"]`);
  if (cell) cell.classList.add('selected');

  // Format date label
  const d = new Date(ds + 'T00:00:00');
  const label = _calDayNames[d.getDay() === 0 ? 6 : d.getDay() - 1] + ', ' +
    d.getDate() + ' ' + _calMonthNames[d.getMonth()] + ' ' + d.getFullYear();
  document.getElementById('cal-day-date').textContent = label;
  document.getElementById('cal-add-btn').style.display = '';
  document.getElementById('cal-day-empty').style.display = 'none';
  document.getElementById('cal-reminder-form').style.display = 'none';

  const act = _calData[ds] || {};
  const hasAny = Object.values(act).some(v => v > 0);
  document.getElementById('cal-day-activity').style.display = hasAny ? '' : 'none';
  if (hasAny) {
    document.getElementById('cal-act-chat-n').textContent  = act.chat || 0;
    document.getElementById('cal-act-fc-n').textContent    = act.flashcards || 0;
    document.getElementById('cal-act-quiz-n').textContent  = act.quizzes || 0;
    document.getElementById('cal-act-tasks-n').textContent = act.tasks || 0;
  }

  const hasPlanTasks = (_calPlanTasks[ds] || []).length > 0;
  document.getElementById('cal-day-empty').style.display = (hasAny || hasPlanTasks) ? 'none' : '';
  _calRenderDayPlanTasks(ds);
  _calRenderDayReminders(ds);
}

function _calRenderDayReminders(ds) {
  const wrap = document.getElementById('cal-day-reminders');
  const rems = _calReminders.filter(r => r.date === ds);
  if (!rems.length) { wrap.innerHTML = ''; return; }

  wrap.innerHTML = `<div style="font-size:12px;font-weight:700;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Reminders</div>` +
    rems.map(r => `
      <div class="cal-reminder-item" id="cal-rem-${r.id}">
        <div class="cal-rem-check${r.is_done ? ' done' : ''}" onclick="calToggleReminder(${r.id})">
          ${r.is_done ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
        </div>
        <div class="cal-rem-body">
          <div class="cal-rem-title${r.is_done ? ' done' : ''}">${r.title}</div>
          ${r.time ? `<div class="cal-rem-time">${r.time}</div>` : ''}
        </div>
        <button class="cal-rem-del" onclick="calDeleteReminder(${r.id})">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
        </button>
      </div>`).join('');
}

function _calRenderDayPlanTasks(ds) {
  const wrap = document.getElementById('cal-day-plan-tasks');
  if (!wrap) return;
  const tasks = _calPlanTasks[ds] || [];
  if (!tasks.length) { wrap.innerHTML = ''; return; }
  wrap.innerHTML = `<div style="font-size:12px;font-weight:700;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Study Tasks</div>` +
    tasks.map(t => `
      <div class="cal-plan-task" id="cal-pt-${t.id}">
        <div class="cal-plan-check${t.is_completed ? ' done' : ''}" onclick="calTogglePlanTask(${t.id}, this)">
          ${t.is_completed ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
        </div>
        <div class="cal-plan-body">
          <div class="cal-plan-title${t.is_completed ? ' done' : ''}">${t.title}</div>
          <div class="cal-plan-week">Week ${t.week_number}</div>
        </div>
      </div>`).join('');
}

async function calTogglePlanTask(taskId, checkEl) {
  try {
    const res = await fetch(`/api/study-plan/tasks/${taskId}/toggle/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const data = await res.json();
    if (!res.ok) return;
    // Update local _calPlanTasks state
    for (const ds in _calPlanTasks) {
      const t = _calPlanTasks[ds].find(t => t.id === taskId);
      if (t) { t.is_completed = data.is_completed; break; }
    }
    // Update calendar day detail UI
    checkEl.classList.toggle('done', data.is_completed);
    checkEl.innerHTML = data.is_completed
      ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>'
      : '';
    const row = document.getElementById('cal-pt-' + taskId);
    if (row) {
      const title = row.querySelector('.cal-plan-title');
      if (title) title.classList.toggle('done', data.is_completed);
    }
    // Sync with study tracker if it's loaded
    if (_sytData) {
      _sytData.completed_tasks = data.completed_tasks;
      _sytData.total_tasks = data.total_tasks;
      _sytData.progress_pct = data.progress_pct;
      _sytUpdateProgress(_sytData);
      _sytData.weeks.forEach(wk => {
        const t = wk.tasks.find(t => t.id === taskId);
        if (t) {
          t.is_completed = data.is_completed;
          const done = wk.tasks.filter(t => t.is_completed).length;
          const total = wk.tasks.length;
          const wkEl = document.getElementById('syt-wk-' + wk.week);
          if (wkEl) {
            wkEl.classList.toggle('complete', done === total);
            const pctEl = wkEl.querySelector('.splan-week-pct');
            if (pctEl) pctEl.textContent = done === total ? '✓ Done' : Math.round(done / total * 100) + '%';
          }
          const sytRow = document.getElementById('syt-task-row-' + taskId);
          if (sytRow) {
            sytRow.classList.toggle('done', data.is_completed);
            const chk = sytRow.querySelector('.splan-task-check');
            if (chk) chk.classList.toggle('done', data.is_completed);
          }
        }
      });
    }
  } catch (_) {}
}

function _calRenderUpcoming() {
  const list = document.getElementById('cal-upcoming-list');
  if (!list) return;
  const today = new Date().toISOString().slice(0, 10);
  // Gather from current month + already fetched
  const upcoming = _calReminders
    .filter(r => r.date >= today && !r.is_done)
    .sort((a, b) => a.date.localeCompare(b.date) || (a.time || '').localeCompare(b.time || ''))
    .slice(0, 8);

  if (!upcoming.length) {
    list.innerHTML = '<div style="font-size:13px;color:var(--ink-soft);">No upcoming reminders</div>';
    return;
  }
  const d2 = new Date();
  list.innerHTML = upcoming.map(r => {
    const rd = new Date(r.date + 'T00:00:00');
    const lbl = rd.getDate() + ' ' + _calMonthNames[rd.getMonth()].slice(0, 3);
    return `<div class="cal-upcoming-item">
      <span class="cal-upcoming-date">${lbl}</span>
      <div>
        <div class="cal-upcoming-title">${r.title}</div>
        ${r.time ? `<div class="cal-upcoming-time">${r.time}</div>` : ''}
      </div>
      <button class="cal-rem-del" onclick="calDeleteReminder(${r.id})" style="margin-left:auto;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
      </button>
    </div>`;
  }).join('');
}

function calShowReminderForm() {
  document.getElementById('cal-reminder-form').style.display = '';
  document.getElementById('cal-rem-title').focus();
}
function calHideReminderForm() {
  document.getElementById('cal-reminder-form').style.display = 'none';
  document.getElementById('cal-rem-title').value = '';
  document.getElementById('cal-rem-time').value  = '';
}

async function calAddReminder() {
  const title = document.getElementById('cal-rem-title').value.trim();
  if (!title || !_calSelectedDate) return;
  const time = document.getElementById('cal-rem-time').value || null;
  try {
    const res = await fetch('/api/reminders/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ title, date: _calSelectedDate, time }),
    });
    const r = await res.json();
    if (r.id) {
      _calReminders.push(r);
      _calRenderGrid(new Date().toISOString().slice(0, 10));
      _calRenderDayReminders(_calSelectedDate);
      _calRenderUpcoming();
      calHideReminderForm();
    }
  } catch (_) {}
}

async function calToggleReminder(id) {
  try {
    const res = await fetch(`/api/reminders/${id}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const data = await res.json();
    const rem = _calReminders.find(r => r.id === id);
    if (rem) rem.is_done = data.is_done;
    if (_calSelectedDate) _calRenderDayReminders(_calSelectedDate);
    _calRenderUpcoming();
  } catch (_) {}
}

async function calDeleteReminder(id) {
  try {
    await fetch(`/api/reminders/${id}/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    _calReminders = _calReminders.filter(r => r.id !== id);
    _calRenderGrid(new Date().toISOString().slice(0, 10));
    if (_calSelectedDate) _calRenderDayReminders(_calSelectedDate);
    _calRenderUpcoming();
  } catch (_) {}
}

// =================== SYLLABUS TAB SWITCHING ===================
let _sylActiveTab = 'notes';

function sylSwitchTab(tab) {
  _sylActiveTab = tab;
  document.getElementById('syl-notes-panel').style.display   = tab === 'notes'   ? '' : 'none';
  document.getElementById('syl-tracker-panel').style.display = tab === 'tracker' ? '' : 'none';
  document.getElementById('syl-tab-notes').classList.toggle('active', tab === 'notes');
  document.getElementById('syl-tab-tracker').classList.toggle('active', tab === 'tracker');
  if (tab === 'tracker') sytLoad();
}

// =================== STUDY TRACKER (inside My Plan) ===================
let _sytData = null;

function _sytSubject() {
  const s = (document.getElementById('syl-subject') || {}).value || '';
  const t = (document.getElementById('syl-title') || {}).value || '';
  return (s || t || 'General Study').trim();
}

function _sytUpdateProgress(plan) {
  const pct = plan.progress_pct;
  document.getElementById('syt-ring-pct').textContent = pct + '%';
  document.getElementById('syt-ring-fg').style.strokeDasharray = pct + ',100';
  document.getElementById('syt-bar-fill').style.width = pct + '%';
  document.getElementById('syt-done-count').textContent = plan.completed_tasks;
  document.getElementById('syt-total-count').textContent = plan.total_tasks;
  document.getElementById('syt-weeks-label').textContent = plan.duration_weeks + ' wks';
  document.getElementById('syt-hours-label').textContent = plan.hours_per_day + ' hrs';
}

function _sytRenderWeeks(plan) {
  const container = document.getElementById('syt-weeks-container');
  if (!container) return;
  container.innerHTML = '';
  plan.weeks.forEach((wk, wi) => {
    const total = wk.tasks.length;
    const done = wk.tasks.filter(t => t.is_completed).length;
    const isComplete = done === total && total > 0;
    const isActive = !isComplete && wi === plan.weeks.findIndex(w => w.tasks.some(t => !t.is_completed));
    const open = isActive || wi === 0;
    const wkPct = total ? Math.round(done / total * 100) : 0;

    const el = document.createElement('div');
    el.className = 'splan-week' + (isComplete ? ' complete' : '') + (isActive ? ' active' : '') + (open ? ' open' : '');
    el.id = 'syt-wk-' + wk.week;
    el.innerHTML = `
      <div class="splan-week-header" onclick="sytToggleWeek(${wk.week})">
        <span class="splan-week-badge">Week ${wk.week}</span>
        <span class="splan-week-theme">${wk.theme}</span>
        <span class="splan-week-pct">${isComplete ? '✓ Done' : wkPct + '%'}</span>
        <svg class="splan-week-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="splan-task-list" style="display:${open ? 'block' : 'none'}">
        ${wk.tasks.map(task => `
          <div class="splan-task${task.is_completed ? ' done' : ''}" id="syt-task-row-${task.id}">
            <div class="splan-task-check${task.is_completed ? ' done' : ''}" onclick="sytToggleTask(${task.id}, this)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div class="splan-task-body">
              <div class="splan-task-title">${task.title}${task.scheduled_date ? `<span class="syt-task-date">${_fmtCalDate(task.scheduled_date)}</span>` : ''}</div>
              ${task.description ? `<div class="splan-task-desc">${task.description}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>`;
    container.appendChild(el);
  });
}

function _sytRender(plan) {
  _sytData = plan;
  document.getElementById('syt-setup').style.display = 'none';
  document.getElementById('syt-view').style.display = '';
  _sytUpdateProgress(plan);
  _sytRenderWeeks(plan);
  _sytUpdateCalStatus(plan);
}

function _sytUpdateCalStatus(plan) {
  const statusEl = document.getElementById('syt-cal-status');
  const dateInput = document.getElementById('syt-cal-date');
  if (!statusEl) return;
  if (plan.schedule_start) {
    const d = new Date(plan.schedule_start + 'T00:00:00');
    const label = d.getDate() + ' ' + _calMonthNames[d.getMonth()] + ' ' + d.getFullYear();
    statusEl.textContent = 'Activated — starts ' + label;
    statusEl.style.color = 'var(--primary)';
    if (dateInput) dateInput.value = plan.schedule_start;
  } else {
    statusEl.textContent = 'Pick a start date to activate this plan';
    statusEl.style.color = '';
    if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);
  }
}

async function sytActivateCalendar() {
  const dateInput = document.getElementById('syt-cal-date');
  const startDate = dateInput ? dateInput.value : '';
  if (!startDate) { alert('Please pick a start date.'); return; }

  const btn = document.querySelector('.syt-cal-activate-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Scheduling…'; }

  try {
    const res = await fetch('/api/study-plan/schedule/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ start_date: startDate }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.error || 'Failed to schedule.'); return; }
    _sytData = data.plan;
    _sytRenderWeeks(data.plan);
    _sytUpdateCalStatus(data.plan);
    // Reload calendar so the new task dots appear immediately
    if (typeof calLoad === 'function') calLoad(_calYear, _calMonth);
  } catch (_) {
    alert('Server error. Please try again.');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Activate'; }
  }
}

function sytToggleWeek(wkNum) {
  const el = document.getElementById('syt-wk-' + wkNum);
  if (!el) return;
  const list = el.querySelector('.splan-task-list');
  const isOpen = el.classList.contains('open');
  el.classList.toggle('open', !isOpen);
  list.style.display = isOpen ? 'none' : 'block';
}

async function sytLoad() {
  try {
    const res = await fetch('/api/study-plan/');
    const data = await res.json();
    if (data.plan) {
      _sytRender(data.plan);
      sytRefreshSuggestion();
    } else {
      document.getElementById('syt-setup').style.display = '';
      document.getElementById('syt-view').style.display = 'none';
    }
  } catch (_) {}
}

async function sytGenerate() {
  const subject = _sytSubject();
  const goal = (document.getElementById('syt-goal') || {}).value || '';
  const weeks = parseInt((document.getElementById('syt-weeks') || {}).value || 4);
  const hours = parseFloat((document.getElementById('syt-hours') || {}).value || 2);

  const btn = document.getElementById('syt-gen-btn');
  btn.disabled = true;
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Building your tracker…`;

  try {
    const res = await fetch('/api/study-plan/generate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ subject, goal, duration_weeks: weeks, hours_per_day: hours }),
    });
    const data = await res.json();
    if (data.plan) {
      _sytRender(data.plan);
      sytRefreshSuggestion();
    } else {
      alert(data.error || 'Failed to generate tracker. Please try again.');
    }
  } catch (_) {
    alert('Server error. Please try again.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Generate Study Tracker`;
  }
}

async function sytToggleTask(taskId, checkEl) {
  try {
    const res = await fetch(`/api/study-plan/tasks/${taskId}/toggle/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const data = await res.json();
    if (!res.ok) return;
    const row = document.getElementById('syt-task-row-' + taskId);
    checkEl.classList.toggle('done', data.is_completed);
    if (row) row.classList.toggle('done', data.is_completed);
    if (_sytData) {
      _sytData.completed_tasks = data.completed_tasks;
      _sytData.total_tasks = data.total_tasks;
      _sytData.progress_pct = data.progress_pct;
      _sytUpdateProgress(_sytData);
    }
    // Update week badge
    if (_sytData) {
      _sytData.weeks.forEach(wk => {
        const task = wk.tasks.find(t => t.id === taskId);
        if (task) {
          task.is_completed = data.is_completed;
          const done = wk.tasks.filter(t => t.is_completed).length;
          const total = wk.tasks.length;
          const wkEl = document.getElementById('syt-wk-' + wk.week);
          if (wkEl) {
            wkEl.classList.toggle('complete', done === total);
            const pctEl = wkEl.querySelector('.splan-week-pct');
            if (pctEl) pctEl.textContent = done === total ? '✓ Done' : Math.round(done / total * 100) + '%';
          }
        }
      });
    }
    if (data.progress_pct === 100 || data.completed_tasks % 5 === 0) sytRefreshSuggestion();
  } catch (_) {}
}

async function sytRefreshSuggestion() {
  const el = document.getElementById('syt-suggestion-text');
  if (!el) return;
  el.textContent = 'Thinking…';
  try {
    const res = await fetch('/api/study-plan/suggestion/');
    const data = await res.json();
    el.textContent = data.suggestion || 'Keep going — every task done matters!';
  } catch (_) {
    el.textContent = 'Keep going — every task completed brings you closer to your goal!';
  }
}

function sytReset() {
  if (!confirm('Start a new tracker? This will replace your current one.')) return;
  _sytData = null;
  document.getElementById('syt-setup').style.display = '';
  document.getElementById('syt-view').style.display = 'none';
  document.getElementById('syt-goal').value = '';
}

// =================== STUDY PLAN ===================
let _splanData = null;

function showPlanSetup() {
  document.getElementById('splan-setup').style.display = '';
  document.getElementById('splan-view').style.display = 'none';
}

function _splanUpdateProgress(plan) {
  const pct = plan.progress_pct;
  document.getElementById('splan-ring-pct').textContent = pct + '%';
  document.getElementById('splan-ring-fg').style.strokeDasharray = pct + ',100';
  document.getElementById('splan-bar-fill').style.width = pct + '%';
  document.getElementById('splan-done-count').textContent = plan.completed_tasks;
  document.getElementById('splan-total-count').textContent = plan.total_tasks;
}

function _splanRenderWeeks(plan) {
  const container = document.getElementById('splan-weeks-container');
  if (!container) return;
  container.innerHTML = '';
  plan.weeks.forEach((wk, wi) => {
    const total = wk.tasks.length;
    const done = wk.tasks.filter(t => t.is_completed).length;
    const isComplete = done === total && total > 0;
    const isActive = !isComplete && wi === plan.weeks.findIndex(w => w.tasks.some(t => !t.is_completed));
    const open = isActive || wi === 0;
    const wkPct = total ? Math.round(done / total * 100) : 0;

    const wkEl = document.createElement('div');
    wkEl.className = 'splan-week' + (isComplete ? ' complete' : '') + (isActive ? ' active' : '') + (open ? ' open' : '');
    wkEl.id = 'splan-wk-' + wk.week;

    wkEl.innerHTML = `
      <div class="splan-week-header" onclick="splanToggleWeek(${wk.week})">
        <span class="splan-week-badge">Week ${wk.week}</span>
        <span class="splan-week-theme">${wk.theme}</span>
        <span class="splan-week-pct">${isComplete ? '✓ Done' : wkPct + '%'}</span>
        <svg class="splan-week-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="splan-task-list" style="display:${open ? 'block' : 'none'}">
        ${wk.tasks.map(task => `
          <div class="splan-task${task.is_completed ? ' done' : ''}" id="splan-task-row-${task.id}">
            <div class="splan-task-check${task.is_completed ? ' done' : ''}" onclick="togglePlanTask(${task.id}, this)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div class="splan-task-body">
              <div class="splan-task-title">${task.title}</div>
              ${task.description ? `<div class="splan-task-desc">${task.description}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>`;
    container.appendChild(wkEl);
  });
}

function _splanRender(plan) {
  _splanData = plan;
  document.getElementById('splan-setup').style.display = 'none';
  document.getElementById('splan-view').style.display = '';

  document.getElementById('splan-subject-label').textContent = plan.subject + ' · Study Plan';
  document.getElementById('splan-goal-label').textContent = plan.goal || 'Your personalised roadmap';
  document.getElementById('splan-weeks-label').textContent = plan.duration_weeks + ' weeks';
  document.getElementById('splan-hours-label').textContent = plan.hours_per_day + ' hrs/day';
  document.getElementById('splan-started-label').textContent = plan.created_at;

  _splanUpdateProgress(plan);
  _splanRenderWeeks(plan);
}

function splanToggleWeek(wkNum) {
  const wkEl = document.getElementById('splan-wk-' + wkNum);
  if (!wkEl) return;
  const list = wkEl.querySelector('.splan-task-list');
  const isOpen = wkEl.classList.contains('open');
  wkEl.classList.toggle('open', !isOpen);
  list.style.display = isOpen ? 'none' : 'block';
}

async function loadStudyPlan() {
  try {
    const res = await fetch('/api/study-plan/');
    const data = await res.json();
    if (data.plan) {
      _splanRender(data.plan);
      refreshPlanSuggestion();
    }
  } catch (_) {}
}

async function generateStudyPlan() {
  const subject = document.getElementById('splan-subject').value.trim();
  if (!subject) {
    document.getElementById('splan-subject').focus();
    return;
  }
  const btn = document.getElementById('splan-gen-btn');
  btn.disabled = true;
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Building your plan…`;

  try {
    const res = await fetch('/api/study-plan/generate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({
        subject,
        goal: document.getElementById('splan-goal').value.trim(),
        duration_weeks: parseInt(document.getElementById('splan-weeks').value),
        hours_per_day: parseFloat(document.getElementById('splan-hours').value),
      }),
    });
    const data = await res.json();
    if (data.plan) {
      _splanRender(data.plan);
      refreshPlanSuggestion();
    } else {
      alert(data.error || 'Failed to generate plan. Please try again.');
    }
  } catch (e) {
    alert('Server error. Please try again.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Generate My Plan`;
  }
}

async function togglePlanTask(taskId, checkEl) {
  try {
    const res = await fetch(`/api/study-plan/tasks/${taskId}/toggle/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const data = await res.json();
    if (!res.ok) return;

    // Update check visual
    const row = document.getElementById('splan-task-row-' + taskId);
    const isNowDone = data.is_completed;
    checkEl.classList.toggle('done', isNowDone);
    if (row) row.classList.toggle('done', isNowDone);

    // Update progress counters
    if (_splanData) {
      _splanData.completed_tasks = data.completed_tasks;
      _splanData.total_tasks = data.total_tasks;
      _splanData.progress_pct = data.progress_pct;
      _splanUpdateProgress(_splanData);
    }

    // Re-fetch suggestion every 5th toggle (to avoid hammering API)
    if (data.completed_tasks % 5 === 0 || data.progress_pct === 100) {
      refreshPlanSuggestion();
    }

    // Update week header %
    if (_splanData) {
      _splanData.weeks.forEach(wk => {
        const task = wk.tasks.find(t => t.id === taskId);
        if (task) {
          task.is_completed = isNowDone;
          const done = wk.tasks.filter(t => t.is_completed).length;
          const total = wk.tasks.length;
          const wkEl = document.getElementById('splan-wk-' + wk.week);
          if (wkEl) {
            const pctEl = wkEl.querySelector('.splan-week-pct');
            const isComplete = done === total;
            wkEl.classList.toggle('complete', isComplete);
            if (pctEl) pctEl.textContent = isComplete ? '✓ Done' : Math.round(done / total * 100) + '%';
          }
        }
      });
    }
  } catch (_) {}
}

async function refreshPlanSuggestion() {
  const textEl = document.getElementById('splan-suggestion-text');
  if (!textEl) return;
  textEl.textContent = 'Thinking…';
  try {
    const res = await fetch('/api/study-plan/suggestion/');
    const data = await res.json();
    textEl.textContent = data.suggestion || 'Keep going — every task completed matters!';
  } catch (_) {
    textEl.textContent = 'Keep going — every task completed brings you closer to your goal!';
  }
}

window.switchView = switchView;
window.startTest = startTest;
window.selectOption = selectOption;
window.nextQuestion = nextQuestion;
window.prevQuestion = prevQuestion;
window.goToQ = goToQ;
window.showHint = showHint;
window.submitTest = submitTest;
window.exitTest = exitTest;
window.loadChatHistory = loadChatHistory;
window.loadChatSession = loadChatSession;
window.loadChatSessions = loadChatSessions;
window.deleteChatSession = deleteChatSession;
window.sendMessage = sendMessage;
window.useSuggestion = useSuggestion;
window.newChat = newChat;
window.saveApiKey = saveApiKey;
// Flashcard exports
window.fcCreateCard = fcCreateCard;
window.fcLoadCards = fcLoadCards;
window.fcLoadDeckStats = fcLoadDeckStats;
window.fcLoadSubjects = fcLoadSubjects;
window.fcFlipCard = fcFlipCard;
window.fcGrade = fcGrade;
window.fcDeleteCard = fcDeleteCard;
window.fcInit = fcInit;
window.fcGenerateCards = fcGenerateCards;
window.handleLogin = handleLogin;
window.handleSignup = handleSignup;
window.toggleAuthMode = toggleAuthMode;
window.logout = logout;
window.closeModal = closeModal;
window.createNewJournal = createNewJournal;
window.saveJournal = saveJournal;
window.deleteJournal = deleteJournal;
window.fetchJournals = fetchJournals;
// Syllabus exports
window.createNewSyllabus = createNewSyllabus;
window.saveSyllabusInfo = saveSyllabusInfo;
window.deleteSyllabus = deleteSyllabus;
window.showAddNoteForm = showAddNoteForm;
window.showAddImageForm = showAddImageForm;
window.showAddFileForm = showAddFileForm;
window.showAddLinkForm = showAddLinkForm;
window.hideAddForms = hideAddForms;
window.addTextNote = addTextNote;
window.addImageNote = addImageNote;
window.addFileNote = addFileNote;
window.addLinkNote = addLinkNote;
window.deleteSyllabusItem = deleteSyllabusItem;
window.generateInsights = generateInsights;
window.sendPlanChat = sendPlanChat;
window.usePlanSuggestion = usePlanSuggestion;
window.showMonthlyPlanForm = showMonthlyPlanForm;
window.hideMonthlyForm = hideMonthlyForm;
window.generateMonthlyPlan = generateMonthlyPlan;
window.sendMonthlyChat = sendMonthlyChat;
window.useMonthlyPlanSuggestion = useMonthlyPlanSuggestion;
window.resetMonthlyChat = resetMonthlyChat;
// Quiz setup exports
window.showArenaLanding = showArenaLanding;
window.showQuizSetup = showQuizSetup;
window.showMockSetup = showMockSetup;
window.showTestHub = showTestHub;
window.setMockTopic = setMockTopic;
window.setMockDuration = setMockDuration;
window.setMockCount = setMockCount;
window.adjustMockType = adjustMockType;
window.syncMockType = syncMockType;
window.updateMockPreview = updateMockPreview;
window.generateMock = generateMock;
window.selectTopic = selectTopic;
window.setQCount = setQCount;
window.generateAndStart = generateAndStart;
window.startSmartQuiz = startSmartQuiz;
window.retryQuiz = retryQuiz;
window.loadTopicPicker = loadTopicPicker;
window.previewImage = previewImage;
window.previewFile = previewFile;
window.fetchSyllabi = fetchSyllabi;
// Calendar exports
window.calLoad = calLoad;
window.calPrevMonth = calPrevMonth;
window.calNextMonth = calNextMonth;
window.calShowReminderForm = calShowReminderForm;
window.calHideReminderForm = calHideReminderForm;
window.calAddReminder = calAddReminder;
window.calToggleReminder = calToggleReminder;
window.calDeleteReminder = calDeleteReminder;
window.calTogglePlanTask = calTogglePlanTask;
// Syllabus tab + Study Tracker exports
window.sylSwitchTab = sylSwitchTab;
window.sytGenerate = sytGenerate;
window.sytActivateCalendar = sytActivateCalendar;
window.sytToggleTask = sytToggleTask;
window.sytRefreshSuggestion = sytRefreshSuggestion;
window.sytToggleWeek = sytToggleWeek;
window.sytReset = sytReset;
// Study Plan exports
window.generateStudyPlan = generateStudyPlan;
window.togglePlanTask = togglePlanTask;
window.refreshPlanSuggestion = refreshPlanSuggestion;
window.showPlanSetup = showPlanSetup;
window.splanToggleWeek = splanToggleWeek;

// =================== VIDEO SEARCH ===================
const _vidLevelColors = {
  Beginner:     { bg: 'rgba(52,211,153,0.12)',  color: 'var(--mint)',  border: 'rgba(52,211,153,0.3)'  },
  Intermediate: { bg: 'rgba(251,191,36,0.12)',  color: 'var(--gold)',  border: 'rgba(251,191,36,0.3)'  },
  Advanced:     { bg: 'rgba(251,113,133,0.12)', color: 'var(--coral)', border: 'rgba(251,113,133,0.3)' },
};

function _vidSetState(state) {
  document.getElementById('vid-empty-state').style.display   = state === 'empty'   ? 'block' : 'none';
  document.getElementById('vid-loading').style.display       = state === 'loading'  ? 'block' : 'none';
  document.getElementById('vid-grid').style.display          = state === 'results'  ? 'block' : 'none';
  document.getElementById('vid-error').style.display         = state === 'error'    ? 'block' : 'none';
}

function searchVideos() {
  const inp = document.getElementById('vid-topic-input');
  const topic = inp ? inp.value.trim() : '';
  if (!topic) { inp && inp.focus(); return; }

  const btn = document.getElementById('vid-search-btn');
  if (btn) { btn.textContent = 'Searching…'; btn.disabled = true; }
  _vidSetState('loading');

  fetch(`/api/analytics/video-search/?topic=${encodeURIComponent(topic)}`)
    .then(r => r.json())
    .then(data => {
      if (btn) { btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Find Videos'; btn.disabled = false; }
      if (data.error || !data.videos || data.videos.length === 0) {
        document.getElementById('vid-error-msg').textContent = data.error || 'No results found. Try a different topic.';
        _vidSetState('error');
        return;
      }
      _vidRenderResults(data.videos, data.topic);
    })
    .catch(() => {
      if (btn) { btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Find Videos'; btn.disabled = false; }
      document.getElementById('vid-error-msg').textContent = 'Could not connect. Please check your connection and try again.';
      _vidSetState('error');
    });
}

function quickVideoSearch(topic) {
  const inp = document.getElementById('vid-topic-input');
  if (inp) inp.value = topic;
  searchVideos();
}

const _vidGradients = [
  'linear-gradient(135deg,#6366f1,#8b5cf6)',
  'linear-gradient(135deg,#f59e0b,#ef4444)',
  'linear-gradient(135deg,#10b981,#3b82f6)',
  'linear-gradient(135deg,#ec4899,#8b5cf6)',
  'linear-gradient(135deg,#14b8a6,#6366f1)',
  'linear-gradient(135deg,#f97316,#eab308)',
];

const _levelMeta = {
  Beginner:     { label: 'Beginner',     icon: '🌱', color: '#10b981', bg: 'rgba(16,185,129,.09)',  border: 'rgba(16,185,129,.22)'  },
  Intermediate: { label: 'Intermediate', icon: '⚡', color: '#f59e0b', bg: 'rgba(245,158,11,.09)',  border: 'rgba(245,158,11,.22)'  },
  Advanced:     { label: 'Advanced',     icon: '🔥', color: '#ef4444', bg: 'rgba(239,68,68,.09)',   border: 'rgba(239,68,68,.22)'   },
};

function _vidCard(v, idx) {
  const isSearch = !v.thumbnail;
  const isHindi  = v.lang === 'Hindi';
  const langDot  = isHindi ? '#f97316' : '#3b82f6';
  const langLabel = isHindi ? '· Hindi' : '· English';

  const thumbInner = v.thumbnail
    ? `<img src="${v.thumbnail}" alt="${escapeHtml(v.title)}">`
    : `<div class="vid-thumb-gradient" style="background:${_vidGradients[idx % 6]};">
         <svg width="28" height="28" viewBox="0 0 24 24" fill="rgba(255,255,255,.9)"><polygon points="5 3 19 12 5 21 5 3"/></svg>
         <span>${escapeHtml(v.channel)}</span>
       </div>`;

  const ytIcon = `<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
    <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
  </svg>`;

  return `<a class="vid-card" href="${v.watch_url}" target="_blank" rel="noopener">
    <div class="vid-thumb">
      ${thumbInner}
      <span class="vid-duration">${escapeHtml(v.duration)}</span>
    </div>
    <div class="vid-body">
      <div class="vid-meta">
        <span class="vid-lang-dot" style="background:${langDot};"></span>
        <span class="vid-channel">${escapeHtml(v.channel)}</span>
        <span class="vid-lang-label">${langLabel}</span>
        ${isSearch ? '<span class="vid-search-tag">SEARCH</span>' : ''}
      </div>
      <div class="vid-title">${escapeHtml(v.title)}</div>
      <div class="vid-btn">
        ${ytIcon}
        ${isSearch ? 'Search on YouTube' : 'Watch on YouTube'}
      </div>
    </div>
  </a>`;
}

function _vidRenderResults(videos, topic) {
  const label = document.getElementById('vid-results-label');
  if (label) label.textContent = `${videos.length} videos for "${topic}"`;

  const cards = document.getElementById('vid-cards');
  if (!cards) return;

  const groups = { Beginner: [], Intermediate: [], Advanced: [] };
  let idx = 0;
  videos.forEach(v => {
    const lvl = groups[v.level] !== undefined ? v.level : 'Intermediate';
    groups[lvl].push({ v, idx: idx++ });
  });

  let html = '';
  ['Beginner', 'Intermediate', 'Advanced'].forEach(level => {
    const group = groups[level];
    if (!group.length) return;
    const m = _levelMeta[level];
    html += `<div class="vid-section">
      <div class="vid-section-hd">
        <div class="vid-section-pill" style="background:${m.bg};border:1.5px solid ${m.border};color:${m.color};">
          <span>${m.icon}</span><span>${m.label}</span>
        </div>
        <div class="vid-section-line"></div>
        <span class="vid-section-count">${group.length} video${group.length > 1 ? 's' : ''}</span>
      </div>
      <div class="vid-grid">
        ${group.map(({ v, idx: i }) => _vidCard(v, i)).join('')}
      </div>
    </div>`;
  });

  cards.innerHTML = html;
  _vidSetState('results');
}

window.searchVideos = searchVideos;
window.quickVideoSearch = quickVideoSearch;

// =================== STUDY TIME HEATMAP ===================
const _ST_DAYS  = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const _ST_COLORS = [
  'rgba(99,102,241,', // indigo
];

function _stIntensityColor(v) {
  if (v <= 0)    return 'var(--line)';
  if (v < 0.15)  return 'rgba(99,102,241,0.15)';
  if (v < 0.35)  return 'rgba(99,102,241,0.35)';
  if (v < 0.55)  return 'rgba(99,102,241,0.55)';
  if (v < 0.75)  return 'rgba(99,102,241,0.75)';
  return 'rgba(99,102,241,1)';
}

function loadStudyTime() {
  const skeleton = document.getElementById('st-skeleton');
  const content  = document.getElementById('st-content');
  const warming  = document.getElementById('st-warming');
  if (!skeleton) return;

  fetch('/api/analytics/study-time/')
    .then(r => r.json())
    .then(data => {
      if (skeleton) skeleton.style.display = 'none';

      if (data.status === 'warming_up') {
        if (warming) {
          warming.style.display = 'block';
          const msg = document.getElementById('st-warming-msg');
          if (msg) msg.textContent = data.message || 'Keep studying — we need more data to find your peak focus time.';
        }
        return;
      }

      // Populate message
      const msgEl = document.getElementById('st-message');
      if (msgEl) msgEl.textContent = data.message || '';

      // Peak days pills
      const daysEl = document.getElementById('st-days');
      if (daysEl && data.peak_days) {
        daysEl.innerHTML = data.peak_days.map(d =>
          `<span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;
            background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);
            color:var(--primary);">${d}</span>`
        ).join('');
      }

      // Confidence bar
      const conf = Math.round((data.confidence || 0) * 100);
      const bar  = document.getElementById('st-conf-bar');
      const lbl  = document.getElementById('st-conf-label');
      if (bar) setTimeout(() => { bar.style.width = conf + '%'; }, 100);
      if (lbl) lbl.textContent = conf + '% confidence';

      // Heatmap — data.heatmap is a flat 168-float array (day*24 + hour)
      const hmEl = document.getElementById('st-heatmap');
      if (hmEl && data.heatmap && data.heatmap.length === 168) {
        hmEl.innerHTML = _ST_DAYS.map((day, d) => {
          const cells = Array.from({length: 24}, (_, h) => {
            const v = data.heatmap[d * 24 + h];
            const color = _stIntensityColor(v);
            const pct = Math.round(v * 100);
            return `<div class="st-hm-cell" style="background:${color};"
              title="${day} ${h}:00 — ${pct}% intensity"></div>`;
          }).join('');
          return `<div class="st-hm-row">
            <span class="st-hm-label">${day}</span>${cells}
          </div>`;
        }).join('');
      }

      if (content) content.style.display = 'block';
    })
    .catch(() => {
      if (skeleton) skeleton.style.display = 'none';
      if (warming)  warming.style.display  = 'block';
    });
}

// Load on page ready
document.addEventListener('DOMContentLoaded', loadStudyTime);

