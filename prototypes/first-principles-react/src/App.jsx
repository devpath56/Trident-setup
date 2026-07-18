import { Agentation } from 'agentation'
import { DERIV, PRONGS, STEPS, slug } from './data.js'

function toggleAll(e) {
  const all = [...document.querySelectorAll('details')]
  const anyClosed = all.some((d) => !d.open)
  all.forEach((d) => { d.open = anyClosed })
  e.currentTarget.textContent = anyClosed ? 'collapse all' : 'open all'
}

export default function App() {
  return (
    <div className="wrap">
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
      <Agentation />
    </div>
  )
}
