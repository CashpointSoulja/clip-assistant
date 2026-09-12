/* The dial, the ambient backdrop, and the clock.
 *
 * This file never talks to the server and never edits app.js. app.js already
 * renders the candidate cards into #clips and marks the open one .selected, so
 * the dial reads that list, draws it as a ring, and selects by clicking the
 * matching card. One direction of truth: app.js owns the state, the dial is a
 * second view onto it.
 */
(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  const STAGES = ["SOURCE", "TRANSCRIBE", "ANALYSE", "EXPORT"];
  const SVG_NS = "http://www.w3.org/2000/svg";

  /* ---------------- preloader ---------------- */

  function preloader() {
    const el = $("preloader");
    if (!el) return;
    const dismiss = () => el.classList.add("is-dismissed");
    if (reduced) return dismiss();
    window.setTimeout(dismiss, 1500);
  }

  /* ---------------- clock ---------------- */

  function clock() {
    const time = $("clock-time");
    const footer = $("footer-clock");
    const format = (zone) => {
      try {
        return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: zone }).format(new Date());
      } catch { return "--:--"; }
    };
    const tick = () => {
      const value = format("Europe/London");
      if (time) time.textContent = value;
      if (footer) footer.textContent = `London ${value}`;
    };
    tick();
    window.setInterval(tick, 15000);
  }

  /* ---------------- ambient backdrop ---------------- */

  const VERT = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
  const FRAG = `
precision mediump float;
uniform vec2 u_res; uniform float u_time;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
void main(){
  vec2 p=(gl_FragCoord.xy-.5*u_res.xy)/min(u_res.x,u_res.y);
  float t=u_time*.05;
  float n=noise(p*3.1+t)*.5+noise(p*7.3-t*1.3)*.26;
  float glow=smoothstep(1.3,.0,length(p-vec2(.22,.06)));
  float vig=smoothstep(1.45,.2,length(p));
  vec3 col=vec3(.075,.081,.089)+vec3(.17,.10,.085)*glow*.5+vec3(n)*.032;
  col*=.5+.72*vig;
  col+=(hash(gl_FragCoord.xy+u_time*.5)-.5)*.012;
  gl_FragColor=vec4(col,1.);
}`;

  function backdrop() {
    const canvas = $("gl-backdrop");
    if (!canvas) return;
    const gl = canvas.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power" });
    if (!gl) return;                                  // no WebGL: the CSS background already stands in

    const compile = (type, src) => {
      const sh = gl.createShader(type);
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      return gl.getShaderParameter(sh, gl.COMPILE_STATUS) ? sh : null;
    };
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, "a");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(program, "u_res");
    const uTime = gl.getUniformLocation(program, "u_time");

    let visible = true;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
      const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w; canvas.height = h;
        gl.viewport(0, 0, w, h);
      }
    };

    const draw = (seconds) => {
      resize();
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, seconds);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    if (reduced) { draw(0); return; }                 // one static frame, no loop

    // Stop rendering when scrolled away: this is a laptop tool, not a demo reel.
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(entries => { visible = entries[0].isIntersecting; }, { threshold: 0 })
        .observe(canvas);
    }
    const start = performance.now();
    const frame = (now) => {
      if (visible) draw((now - start) / 1000);
      window.requestAnimationFrame(frame);
    };
    window.requestAnimationFrame(frame);
  }

  /* ---------------- the dial ---------------- */

  const CX = 410, CY = 410, R_OUTER = 372, R_TICK = 348, R_LABEL = 322, R_STAGE = 268, R_INNER = 186;

  const polar = (r, deg) => {
    const rad = (deg - 90) * Math.PI / 180;
    return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
  };
  const arcPath = (r, from, to, sweep = 1) => {
    const [x1, y1] = polar(r, from);
    const [x2, y2] = polar(r, to);
    const large = Math.abs(to - from) > 180 ? 1 : 0;
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} ${sweep} ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  };
  const el = (name, attrs) => {
    const node = document.createElementNS(SVG_NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  };

  function dial() {
    const svg = $("dial");
    const clipsRoot = $("clips");
    if (!svg || !clipsRoot) return;

    const defs = el("defs", {});
    svg.append(defs);

    const ringGroup = el("g", { class: "dial-static" });
    ringGroup.append(el("circle", { class: "dial-ring", cx: CX, cy: CY, r: R_OUTER }));
    ringGroup.append(el("circle", { class: "dial-ring", cx: CX, cy: CY, r: R_LABEL + 26 }));
    ringGroup.append(el("circle", { class: "dial-ring", cx: CX, cy: CY, r: R_INNER }));

    for (let deg = 0; deg < 360; deg += 5) {
      const long = deg % 45 === 0;
      const [x1, y1] = polar(R_OUTER - (long ? 20 : 10), deg);
      const [x2, y2] = polar(R_OUTER, deg);
      ringGroup.append(el("line", { class: "dial-tick", x1, y1, x2, y2, "stroke-width": long ? 1.4 : 0.7 }));
    }
    svg.append(ringGroup);

    // Four stage labels, each riding its own quarter arc.
    const stageGroup = el("g", { class: "dial-stages" });
    const stageTexts = {};
    STAGES.forEach((stage, i) => {
      const id = `stage-path-${i}`;
      // Angles run clockwise from the top, so the right and bottom quadrants
      // (i = 1, 2) rise left-to-right on screen while the others fall. Draw
      // those two in reverse, otherwise their labels ride upside down.
      const reversed = i === 1 || i === 2;
      const d = reversed
        ? arcPath(R_STAGE, (i + 1) * 90 - 5, i * 90 + 5, 0)
        : arcPath(R_STAGE, i * 90 + 5, (i + 1) * 90 - 5, 1);
      defs.append(el("path", { id, d }));
      const text = el("text", { class: "dial-label" });
      const tp = el("textPath", { href: `#${id}`, startOffset: "50%", "text-anchor": "middle" });
      tp.textContent = stage;
      text.append(tp);
      stageGroup.append(text);
      stageTexts[stage] = text;
    });
    svg.append(stageGroup);

    const arcs = el("g", { class: "dial-arcs" });
    const rotate = el("g", { class: "dial-rotate" });
    rotate.append(arcs);
    svg.append(rotate);

    const core = el("g", { class: "dial-core" });
    const scoreText = el("text", { class: "dial-core-score", x: CX, y: CY + 4 });
    const labelText = el("text", { class: "dial-core-label", x: CX, y: CY - 40 });
    const titleText = el("text", { class: "dial-core-title", x: CX, y: CY + 40 });
    core.append(labelText, scoreText, titleText);
    svg.append(core);

    const COLORS = ["#ff5541", "#5595ff", "#51b75a", "#e4bd10"];
    let cards = [];
    let targetAngle = 0;
    let currentAngle = 0;
    let dragStart = null;

    const readCards = () => Array.from(clipsRoot.querySelectorAll(".clip-card"));

    function render() {
      arcs.replaceChildren();
      cards = readCards();
      const count = cards.length;
      if (!count) {
        labelText.textContent = "NO CANDIDATES";
        scoreText.textContent = "—";
        titleText.textContent = "";
        return;
      }
      const span = 360 / count;
      cards.forEach((card, i) => {
        const from = i * span + 1.6;
        const to = (i + 1) * span - 1.6;
        const path = el("path", {
          class: "dial-arc",
          d: arcPath(R_TICK - 26, from, to),
          stroke: COLORS[i % COLORS.length],
          "stroke-width": 14,
          "stroke-linecap": "butt",
          "data-index": i
        });
        path.addEventListener("click", () => { dragStart = null; card.click(); });
        arcs.append(path);
      });
      syncSelection();
    }

    function syncSelection() {
      const cards = readCards();
      const index = Math.max(0, cards.findIndex(card => card.classList.contains("selected")));
      const span = 360 / Math.max(1, cards.length);
      targetAngle = -index * span;                     // bring the chosen arc to the top
      currentAngle = reduced ? targetAngle : currentAngle;

      const selected = cards[index];
      if (selected) {
        const title = selected.querySelector("h4")?.textContent?.trim() || "";
        const score = selected.querySelector(".score")?.textContent || "";
        const digits = (score.match(/\d+/) || [])[0];
        // Local mode produces no score at all. Say so rather than showing a
        // bare dash that reads like a zero.
        labelText.textContent = digits ? "EDITORIAL SCORE" : "LOCAL MODE";
        scoreText.textContent = digits || "NO SCORE";
        scoreText.setAttribute("font-size", digits ? "68" : "26");
        titleText.textContent = title.length > 34 ? title.slice(0, 33) + "…" : title;
      }
      arcs.querySelectorAll(".dial-arc").forEach((arc, i) => {
        arc.setAttribute("opacity", i === index ? "1" : "0.42");
        arc.setAttribute("stroke-width", i === index ? "22" : "12");
      });
    }

    function setStage(stage) {
      const text = String(stage || "").toUpperCase();
      Object.entries(stageTexts).forEach(([name, node]) => {
        const hit = text.includes(name.slice(0, 6)) || (name === "SOURCE" && text.includes("PROBE"));
        node.classList.toggle("active", hit);
      });
    }

    // Rotate the ring: pointer drag, arrow keys, and a gentle scroll offset.
    svg.addEventListener("pointerdown", event => { dragStart = { x: event.clientX, angle: targetAngle }; });
    window.addEventListener("pointerup", () => { dragStart = null; });
    window.addEventListener("pointermove", event => {
      if (!dragStart) return;
      const delta = (event.clientX - dragStart.x) * 0.6;
      targetAngle = dragStart.angle + delta;
    });
    window.addEventListener("keydown", event => {
      if (event.target instanceof Element && event.target.closest("input, select, textarea")) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const list = readCards();
      if (list.length < 2) return;
      const at = Math.max(0, list.findIndex(card => card.classList.contains("selected")));
      const next = (at + (event.key === "ArrowRight" ? 1 : -1) + list.length) % list.length;
      event.preventDefault();
      list[next].click();
    });

    let scrollRotation = 0;
    const onScroll = () => {
      if (reduced) return;
      const rect = svg.getBoundingClientRect();
      const progress = 1 - Math.min(1, Math.max(0, (rect.top + rect.height / 2) / window.innerHeight));
      scrollRotation = (progress - 0.5) * 14;         // ±7°, a nudge, not a hijack
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    const spin = () => {
      currentAngle += (targetAngle - currentAngle) * 0.12;
      const angle = reduced ? targetAngle : currentAngle + scrollRotation;
      rotate.setAttribute("transform", `rotate(${angle.toFixed(3)} ${CX} ${CY})`);
      if (!reduced) window.requestAnimationFrame(spin);
    };
    spin();

    new MutationObserver(() => { render(); setStage(($("job-stage")?.textContent) || ""); })
      .observe(clipsRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });

    // The stage pill is written by app.js; watch it rather than reaching into app.js.
    const stagePill = $("job-stage");
    if (stagePill) {
      new MutationObserver(() => setStage(stagePill.textContent || ""))
        .observe(stagePill, { childList: true, characterData: true, subtree: true });
      setStage(stagePill.textContent || "");
    }
    render();
  }

  preloader();
  clock();
  backdrop();
  dial();
})();
