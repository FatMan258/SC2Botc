// Execute selected production Galaxy bodies after removing only type annotations.
// Native UI calls are stubs: this checks logic/bounds, NOT SC2 timing or its VM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../../scripts/BOTC.galaxy'), 'utf8');
// Mask strings and comments without changing offsets, then balance braces.
const clean = source.replace(/"(?:\\.|[^"\\])*"|\/\/[^\r\n]*|\/\*[\s\S]*?\*\//g,
    s => s.replace(/[^\r\n]/g, ' '));
function extract(name) {
    const re = new RegExp('^(?:void|bool|int)\\s+' + name + '\\s*\\([^;{}]*\\)\\s*\\{', 'm');
    const m = re.exec(clean);
    assert(m, name);
    let end = m.index + m[0].length, depth = 1;
    while (depth) {
        if (clean[end] === '{') depth++;
        if (clean[end] === '}') depth--;
        assert(end < clean.length);
        end++;
    }
    return source.slice(m.index, end);
}
function translate(name) {
    return extract(name)
        .replace(/^(?:void|bool|int)\s+(\w+)\s*\(([^)]*)\)/,
            (_, fn, params) => `function ${fn}(${params.replace(/\b(?:int|bool|string)\s+/g, '')})`)
        .replace(/\b(?:int|bool|string)\s+(\w+)\s*;/g, 'let $1;');
}
function array(n, value, name) {
    return new Proxy(Array(n).fill(value), {
        get(a, key) {
            if (/^-?\d+$/.test(String(key))) assert(+key >= 0 && +key < n, `${name}[${key}]`);
            return a[key];
        },
        set(a, key, v) {
            if (/^-?\d+$/.test(String(key))) assert(+key >= 0 && +key < n, `${name}[${key}]`);
            a[key] = v;
            return true;
        }
    });
}
const functions = ['BOTC_LogRender', 'BOTC_LogRenderNow', 'BOTC_LogTaskStart',
    'BOTC_LogStreamStep', 'BOTC_LogTaskStep', 'BOTC_LogTick_Func', 'BOTC_LogOpen',
    'BOTC_LogClose', 'BOTC_LogSetMode', 'BOTC_AllPmStoreTo', 'BOTC_PubLogStore',
    'BOTC_VoteLogAdd', 'BOTC_PmStoreRaw', 'BOTC_SayToggle', 'BOTC_HotSwitch',
    'BOTC_RpStageRun', 'BOTC_RpStageNext', 'BOTC_PmDropPrefix', 'BOTC_ClearAllLogs'];
function runtime() {
    const c = {rows: Array.from({length: 14}, () => []), events: [], pmDraws: 0};
    for (const m of source.matchAll(/^(int|bool|string|fixed)\s*(?:\[(\d+)\])?\s+(g_\w+)\s*;/gm)) {
        const value = m[1] === 'bool' ? false : m[1] === 'string' ? '' : 0;
        c[m[3]] = m[2] ? array(+m[2], value, m[3]) : value;
    }
    Object.assign(c, {
        StringLength: s => s.length,
        StringSub: (s,a,b) => s.slice(a-1,b),
        BOTC_IsPeriodMark: s => s.includes('----'),
        BOTC_PosOf: p => c.g_who.indexOf(p),
        BOTC_PmWithMe: p => 0,
        BOTC_PubHideByBlock: () => false,
        BOTC_PmBoxRender: () => c.pmDraws++,
        BOTC_ChatRender: () => {},
        BOTC_LogAddLine: (p,s,who) => c.rows[p].push(s),
        BOTC_LogViewBtnRender: () => {},
        PlayerGroupSingle: p => p,
        PlayerGroupAll: () => 0,
        DialogSetVisible: (dialog,p,on) => c.events.push(['visible',p,on]),
        DialogControlSetVisible: () => {},
        DialogControlRemoveAllItems: (control,p) => {c.rows[p] = []; c.events.push(['clear',p]);},
        BOTC_RpRender: () => {throw Error('Unexpected replay initialization');},
        BOTC_RpCollectPm: p => {c.g_logTaskN[p] = 0;},
        BOTC_RpTail: p => c.events.push(['tail', p]),
        BOTC_RpL: (last,i) => `replay-${i}`,
        BOTC_PmOff: () => false,
        BOTC_SayRender: p => c.events.push(['say',p]),
        BOTC_SubMsg: (p,s) => c.events.push(['notice',p,s]),
    });
    for (let p=0;p<=13;p++) c.g_who[p] = p;
    c.g_teller = 1;
    c.g_logLiveUpdate = true;
    vm.createContext(c);
    vm.runInContext(functions.map(translate).join('\n'), c);
    return c;
}
function start(c,p,mode) {
    c.g_logOpen[p] = true;
    c.g_logMode[p] = mode;
    c.BOTC_LogTaskStart(p);
}
function step(c,p,n=8) { c.g_logBatch=n; c.BOTC_LogTaskStep(p); }
function drain(c,p) {
    let limit=20000;
    while(c.g_logTaskN[p] > 0 && limit-- > 0) step(c,p);
    assert(limit > 0, 'loader must finish');
}
function pub(c,s,who=0) { c.g_chatWhoNow=who; c.BOTC_PubLogStore(s); }
function pm(c,p,s,who=0) { c.g_chatWhoNow=who; c.BOTC_PmStoreRaw(p,s); }

test('opening a full history shows the window without scanning or drawing it', () => {
    const c=runtime();
    for(let i=0;i<3600;i++) pub(c, `pub-${i}`);
    c.BOTC_LogOpen(13);
    assert.equal(c.g_logOpen[13],true);
    assert.equal(c.g_logRefresh[13],true);
    assert.deepEqual(c.events,[['visible',13,true]]);
    assert.equal(c.rows[13].length,0);
    c.BOTC_LogTick_Func(false,true);
    c.BOTC_LogTick_Func(false,true);
    assert.equal(c.rows[13].length,8);
});
test('system page catches new public and private entries exactly once', () => {
    const c=runtime();
    pub(c,'public-old'); pm(c,7,'private-old');
    start(c,7,3); step(c,7,1);
    pub(c,'public-new'); pm(c,7,'private-new');
    drain(c,7);
    assert.deepEqual(c.rows[7],['public-old','public-new','private-old','private-new']);
    pub(c,'public-live'); pm(c,7,'private-live'); drain(c,7);
    assert.deepEqual(c.rows[7].slice(-2),['public-live','private-live']);
});
test('public rollover does not replay already read records or misread moved slots', () => {
    const c=runtime();
    for(let i=0;i<3600;i++) pub(c,`p${i}`);
    start(c,2,0); step(c,2,1400); pub(c,'p3600'); drain(c,2);
    assert.equal(c.g_pubLogBase,1200);
    assert.deepEqual(c.rows[2],Array.from({length:3601},(_,i)=>`p${i}`));
});
test('slow readers skip only history already evicted by the existing storage policy', () => {
    const c=runtime();
    for(let i=0;i<3600;i++) pub(c,`p${i}`);
    start(c,2,0); step(c,2,8); pub(c,'p3600'); drain(c,2);
    assert.deepEqual(c.rows[2], [
        ...Array.from({length:8},(_,i)=>`p${i}`),
        ...Array.from({length:2401},(_,i)=>`p${i+1200}`)
    ]);
});
test('private and voting rollovers retain cursor identity', () => {
    for(const mode of [1,2]) {
        const c=runtime();
        const put=mode===1 ? s=>pm(c,13,s) : s=>c.BOTC_VoteLogAdd(s);
        for(let i=0;i<900;i++) put(`r${i}`);
        start(c,13,mode); step(c,13,400); put('r900'); drain(c,13);
        assert.deepEqual(c.rows[13],Array.from({length:901},(_,i)=>`r${i}`));
    }
});
test('all-private ring wraps repeatedly and preserves participant filtering', () => {
    const c=runtime();
    for(let i=0;i<4000;i++) {
        c.g_chatWhoNow=i%13+1;
        c.BOTC_AllPmStoreTo(`a${i}`,0,i%2===0?3:4);
    }
    assert.equal(c.g_allPmCount,1500);
    assert.equal(c.g_allPmBase,2500);
    c.g_logViewWho[1]=3; start(c,1,4); drain(c,1);
    assert.deepEqual(c.rows[1],Array.from({length:750},(_,i)=>`a${2500+2*i}`));
});
test('all-private writes at capacity touch a constant number of participant fields', () => {
    const c=runtime();
    for(let i=0;i<1500;i++) c.BOTC_AllPmStoreTo(`a${i}`,0,3);
    let writes=0;
    c.g_allPmIn=new Proxy(c.g_allPmIn,{set(a,k,v){writes++; a[k]=v; return true;}});
    c.BOTC_AllPmStoreTo('new',0,4);
    assert.equal(writes,14);
});
test('ring overflow during loading and real-time append neither duplicate nor lose retained entries', () => {
    const c=runtime();
    for(let i=0;i<1500;i++) c.BOTC_AllPmStoreTo(`a${i}`,0,3);
    start(c,1,4); step(c,1,16);
    for(let i=1500;i<1510;i++) c.BOTC_AllPmStoreTo(`a${i}`,0,3);
    drain(c,1);
    assert.deepEqual(c.rows[1],Array.from({length:1510},(_,i)=>`a${i}`));
});
test('13 simultaneous readers all get service; timer draws at most 32 records', () => {
    const c=runtime();
    for(let i=0;i<3600;i++) pub(c,`p${i}`);
    for(let p=1;p<=13;p++) start(c,p,0);
    for(let tick=0;tick<4;tick++) {
        const before=c.rows.reduce((n,r)=>n+r.length,0);
        c.BOTC_LogTick_Func(false,true);
        const after=c.rows.reduce((n,r)=>n+r.length,0);
        assert(after-before<=32);
    }
    for(let p=1;p<=13;p++) assert(c.rows[p].length>=8,`player ${p} must progress`);
    let ticks=0;
    while(c.g_logTaskN.some(n=>n>0) && ticks++<2000) c.BOTC_LogTick_Func(false,true);
    assert(ticks<2000);
    for(let p=1;p<=13;p++) assert.equal(c.rows[p].length,3600);
});
test('filtered-out records consume scan budget', () => {
    const c=runtime();
    for(let i=0;i<3600;i++) pub(c,`p${i}`,3);
    c.g_logViewWho[13]=4; start(c,13,0); step(c,13,8);
    assert.equal(c.g_logReadMain[13],8);
    assert.equal(c.g_logBatch,0);
    assert.equal(c.rows[13].length,0);
});
test('private filters use physical-to-logical seat mapping and exclude box-only hints', () => {
    const c=runtime(); c.g_who[1]=5; c.g_who[5]=1;
    pm(c,1,'from-target',3); pm(c,1,'from-other',4);
    c.BOTC_PmWithMe=()=>3; pm(c,1,'to-target',5);
    c.g_pmBoxOnlyNow=true; pm(c,1,'hidden-hint',3); c.g_pmBoxOnlyNow=false;
    pm(c,1,'---- Day ----',0);
    c.g_logViewWho[1]=3; start(c,1,1); drain(c,1);
    assert.deepEqual(c.rows[1],['from-target','to-target','---- Day ----']);
});
test('blocked public lines stay hidden; period markers remain', () => {
    const c=runtime(); pub(c,'hidden',3); pub(c,'---- Day ----',0); pub(c,'visible',4);
    c.BOTC_PubHideByBlock=(p,who)=>who===3;
    start(c,2,0); drain(c,2); assert.deepEqual(c.rows[2],['---- Day ----','visible']);
});
test('closing cancels queued work and reopening rebuilds cleanly', () => {
    const c=runtime(); pub(c,'one'); c.BOTC_LogOpen(2); c.BOTC_LogClose(2);
    for(let i=0;i<4;i++) c.BOTC_LogTick_Func(false,true);
    assert.equal(c.rows[2].length,0);
    c.BOTC_LogOpen(2);
    for(let i=0;i<3;i++) c.BOTC_LogTick_Func(false,true);
    assert.deepEqual(c.rows[2],['one']);
});
test('changing tabs cancels the old task', () => {
    const c=runtime(); pub(c,'public'); pm(c,2,'private'); start(c,2,0);
    c.BOTC_LogSetMode(2,1);
    for(let i=0;i<3;i++) c.BOTC_LogTick_Func(false,true);
    assert.deepEqual(c.rows[2],['private']);
});
test('storyteller handover revokes further all-private rendering', () => {
    const c=runtime(); c.BOTC_AllPmStoreTo('secret',0,3); start(c,1,4);
    c.g_teller=2; step(c,1);
    assert.equal(c.rows[1].length,0); assert.equal(c.g_logMode[1],0);
    assert.equal(c.g_logRefresh[1],true);
});
test('mouse and Tab share cooldown and write no log entries', () => {
    const c=runtime();
    c.BOTC_SayToggle(2); const first=c.g_chatSay[2];
    for(let i=0;i<1000;i++) c.BOTC_HotSwitch(2);
    assert.equal(c.g_chatSay[2],first);
    assert.equal(c.events.filter(e=>e[0]==='say').length,1);
    for(let i=0;i<4;i++) c.BOTC_LogTick_Func(false,true);
    c.BOTC_HotSwitch(2); assert.notEqual(c.g_chatSay[2],first);
    assert.equal(c.g_pmLogCount[2],0); assert.equal(c.g_pubLogCount,0);
});
test('condition-only timer evaluation cannot mutate state', () => {
    const c=runtime(); pub(c,'line'); start(c,2,0);
    assert.equal(c.BOTC_LogTick_Func(true,false),true);
    assert.equal(c.g_logClock,0); assert.equal(c.g_logReadMain[2],0);
});
test('replay completion does not recurse into a fresh batch', () => {
    const c=runtime(); c.g_logOpen[2]=true; c.g_logMode[2]=5;
    c.g_logRpStage[2]=1; c.g_logTaskN[2]=2;
    c.g_logTaskIdx[2*8448]=1; c.g_logTaskIdx[2*8448+1]=2;
    step(c,2,8);
    assert.deepEqual(c.rows[2],['replay-0','replay-1']);
    assert.equal(c.g_logBatch,6); assert.equal(c.g_logRpStage[2],1);
    c.BOTC_LogTick_Func(false,true); assert.equal(c.g_logRpStage[2],2);
    c.BOTC_LogTick_Func(false,true); assert.equal(c.g_logRpStage[2],0);
    assert.deepEqual(c.events,[['tail',2]]);
});
test('one failed draw does not pin scheduling to that player or record', () => {
    const c=runtime(); pub(c,'line0'); pub(c,'line1');
    start(c,1,0); start(c,13,0);
    const draw=c.BOTC_LogAddLine;
    c.BOTC_LogAddLine=(p,s,who)=>{if(p===1 && s==='line0') throw Error('native failure'); draw(p,s,who);};
    assert.throws(()=>c.BOTC_LogTick_Func(false,true),/native failure/);
    assert.equal(c.g_logTickNext,2); assert.equal(c.g_logReadMain[1],1);
    c.BOTC_LogTick_Func(false,true);
    assert.deepEqual(c.rows[13],['line0','line1']);
    assert.deepEqual(c.rows[1],['line1']);
});
test('new game clears ring origins, pending cursors and visible historical rows', () => {
    const c=runtime();
    for(let i=0;i<1501;i++) c.BOTC_AllPmStoreTo(`old${i}`,0,3);
    start(c,1,4); step(c,1);
    c.BOTC_ClearAllLogs();
    assert.equal(c.g_allPmHead,0); assert.equal(c.g_allPmBase,0);
    assert.equal(c.g_allPmCount,0); assert.equal(c.g_logReadMain[1],0);
    c.BOTC_AllPmStoreTo('new-game',0,4);
    for(let i=0;i<3;i++) c.BOTC_LogTick_Func(false,true);
    assert.deepEqual(c.rows[1],['new-game']);
});
test('removing old deal hints restarts only that private view without stale offsets', () => {
    const c=runtime();
    pm(c,2,'deal: old'); pm(c,2,'conversation'); pm(c,2,'deal: second');
    start(c,2,1); step(c,2,1);
    c.BOTC_PmDropPrefix(2,'deal:');
    for(let i=0;i<3;i++) c.BOTC_LogTick_Func(false,true);
    assert.deepEqual(c.rows[2],['conversation']);
});
