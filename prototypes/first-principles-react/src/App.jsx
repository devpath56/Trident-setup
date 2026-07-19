import { useState, useEffect } from 'react'
import { Agentation } from 'agentation'
import { DERIV, PRONGS, STEPS, slug } from './data.js'

function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'light' || saved === 'dark') return saved
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button className="themebtn" id="themebtn" data-anchor="themebtn"
      onClick={() => setTheme(next)} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      {theme === 'dark' ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.6v2.4M12 19v2.4M4.2 4.2l1.7 1.7M18.1 18.1l1.7 1.7M2.6 12h2.4M19 12h2.4M4.2 19.8l1.7-1.7M18.1 5.9l1.7-1.7" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20.5 14.2A8.4 8.4 0 1 1 9.8 3.5a6.6 6.6 0 0 0 10.7 10.7z" />
        </svg>
      )}
    </button>
  )
}

function toggleAll(e) {
  const all = [...document.querySelectorAll('details')]
  const anyClosed = all.some((d) => !d.open)
  all.forEach((d) => { d.open = anyClosed })
  e.currentTarget.textContent = anyClosed ? 'collapse all' : 'open all'
}

function Loop() {
  return (
    <div className="loop" id="prong-loop" data-anchor="prong-loop">
      <div className="lab" style={{ marginTop: 0 }}>How they interact<span className="ev">one bounded loop</span></div>
      <svg className="loopsvg" viewBox="0 0 760 210" role="img"
        aria-label="Simba passes an IntentCard to the Do-er. The Do-er passes an Output to the Auditor. The Auditor returns a Verdict to the Do-er.">
        <defs>
          <marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0 1 L7 4 L0 7 z" className="arh" />
          </marker>
        </defs>

        <line className="trk" x1="148" y1="87" x2="308" y2="87" markerEnd="url(#ar)" />
        <line className="trk" x1="444" y1="87" x2="604" y2="87" markerEnd="url(#ar)" />
        <polyline className="trk" points="676,110 676,176 380,176 380,114" markerEnd="url(#ar)" />

        <g className="pk n-simba">
          <rect x="20" y="64" width="128" height="46" rx="10" />
          <text className="pk-n" x="84" y="83" textAnchor="middle">Simba</text>
          <text className="pk-l" x="84" y="98" textAnchor="middle">loyal to: you</text>
        </g>
        <g className="pk n-doer">
          <rect x="316" y="64" width="128" height="46" rx="10" />
          <text className="pk-n" x="380" y="83" textAnchor="middle">Do-er · Opus</text>
          <text className="pk-l" x="380" y="98" textAnchor="middle">loyal to: shipping</text>
        </g>
        <g className="pk n-auditor">
          <rect x="612" y="64" width="128" height="46" rx="10" />
          <text className="pk-n" x="676" y="83" textAnchor="middle">Auditor · Fable</text>
          <text className="pk-l" x="676" y="98" textAnchor="middle">loyal to: the artifact</text>
        </g>

        <g className="pkt pkt-1">
          <rect x="152" y="76" width="96" height="22" rx="6" />
          <text x="200" y="91" textAnchor="middle">IntentCard</text>
        </g>
        <g className="pkt pkt-2">
          <rect x="448" y="76" width="96" height="22" rx="6" />
          <text x="496" y="91" textAnchor="middle">Output</text>
        </g>
        <g className="pkt pkt-3">
          <rect x="628" y="165" width="96" height="22" rx="6" />
          <text x="676" y="180" textAnchor="middle">Verdict</text>
        </g>
      </svg>
      <div className="loopcap">
        Typed artifacts only, never each other's reasoning. On a fail the Verdict carries the <b>specific failing detector</b> back to the Do-er, not a vague try again. Simba reads the Output and flags drift to the Auditor: it proposes, the Auditor disposes.
      </div>
    </div>
  )
}

export default function App() {
  return (
    <div className="wrap">
      <ThemeToggle />
      <header className="hero" id="hero" data-anchor="hero">
        <div className="eyebrow">🔱 Trident · first principles</div>
        <h1>Why long building sessions fail, and the design forced by each failure.</h1>
        <p className="lede">Trident isn't a bundle of features. Start from how a long autonomous build actually breaks, and each prong is the only answer left standing.</p>
      </header>

      <div className="bar">
        <span className="hint">Click any card to reveal the derivation.</span>
        <button className="toggle" onClick={toggleAll}>open all</button>
      </div>

      <h2 id="h-argument" data-anchor="section:argument">The argument · each failure forces one response</h2>
      {DERIV.map((d, i) => (
        <details key={i} id={`d-${slug(d.fail)}`} data-anchor={`DERIV[${i}] ${d.tag}`}>
          <summary>
            <span className="idx">{String(i + 1).padStart(2, '0')}</span>
            <div className="sum"><div className="t">{d.fail}</div><div className="c">{d.conseq}</div></div>
            <span className="chev">▸</span>
          </summary>
          <div className="reveal">
            <div className="lab">What happens<span className="ev">{d.ev}</span></div>
            <p>{d.what}</p>
            <div className="resp">
              <div className="lab" style={{ marginTop: 0 }}>The forced response</div>
              <div className="rt">{d.resp}</div>
              <span className="tag">{d.tag}</span>
            </div>
          </div>
        </details>
      ))}

      <h2 id="h-prongs" data-anchor="section:prongs">Three prongs, loyal to different masters</h2>
      <p className="body">The checks stay honest only if no prong can be captured. Each answers to a different thing, and none both builds the work and blesses it.</p>
      <Loop />
      {PRONGS.map((p, i) => (
        <details key={i} id={`p-${slug(p.n)}`} data-anchor={`PRONGS[${i}] ${p.n}`}>
          <summary>
            <div className="sum"><div className="t">{p.n}</div></div>
            <span className="loyal">{p.loyal}</span>
            <span className="chev">▸</span>
          </summary>
          <div className="reveal"><p>{p.detail}</p><div className="never"><b>Never:</b> {p.never}</div></div>
        </details>
      ))}
      <div className="shaft" id="shaft" data-anchor="shaft">The shaft binding the three: <b>one failures log</b>. Every prong reads and writes it, so quality compounds instead of repeating.</div>

      <h2 id="h-walkthrough" data-anchor="section:walkthrough">Walkthrough · a real long build (parse_config, with a security must)</h2>
      <p className="body">Task: build a config parser over many rounds, with a hard rule set on round 1 (reject any key starting with <code>__</code>). Below is what actually ran (RESULT-05). Click a step.</p>
      {STEPS.map((s, i) => (
        <details key={i} id={`s-${slug(s.phase)}`} data-anchor={`STEPS[${i}] ${s.phase}`}>
          <summary>
            <span className="idx">{s.phase}</span>
            <div className="sum"><div className="t">{s.h}</div></div>
            <span className="chev">▸</span>
          </summary>
          <div className="reveal"><p>{s.p}</p><div className="real">{s.real}</div></div>
        </details>
      ))}

      <div className="oneline" id="oneline" data-anchor="oneline">Nothing in Trident is a feature you could drop. Each prong is the forced answer to a way long sessions break: <b>intent decays, context rots, optimism lies, the goal drifts</b>. Hold intent out-of-band, judge with a different model, keep loops small and gated, and prove every claim.</div>

      {/*
        Agentation widget: the in-page toolbar. With agentation-mcp configured in ~/.claude/settings.json,
        your LOCAL Claude Code auto-fetches these annotations (watch_annotations) instead of you pasting.
        See README.md. Check agentation docs for props (session id, position) if you need them.
      */}
      <Agentation endpoint="http://localhost:4747" onSessionCreated={(id) => console.log('[agentation] session created:', id)} />
    </div>
  )
}
