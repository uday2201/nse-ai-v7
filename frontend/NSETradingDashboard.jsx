import { useState, useEffect, useRef } from "react";
import { LineChart, Line, AreaChart, Area, BarChart, Bar, RadialBarChart, RadialBar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from "recharts";

/* ═══════════════════════════════════════════
   MOCK DATA
═══════════════════════════════════════════ */
const MARKET = {
  bias: "BULLISH", pcr: 1.31, support: 23000, resistance: 23500, max_pain: 23200,
  nifty: 23287.45, nifty_chg: 0.82, india_vix: 14.32,
  summary: "Institutions are aggressively writing puts at 23000 while call OI at 23500 remains capped. PCR above 1.3 signals strong bullish undertone. Expect continuation towards 23500 resistance.",
  ce_oi: 18420000, pe_oi: 24130000,
  buildups: [
    { strike: 23000, type: "PE", oi: 8500000, oi_change: 420000, buildup: "LONG_BUILDUP" },
    { strike: 23500, type: "CE", oi: 9200000, oi_change: -180000, buildup: "SHORT_COVER" },
    { strike: 22800, type: "PE", oi: 6200000, oi_change: 310000, buildup: "LONG_BUILDUP" },
    { strike: 23600, type: "CE", oi: 7100000, oi_change: 250000, buildup: "SHORT_BUILDUP" },
    { strike: 22900, type: "PE", oi: 5800000, oi_change: -90000, buildup: "LONG_UNWIND" },
  ],
};

const RECOMMENDATIONS = [
  { id:1, stock:"RELIANCE", strategy:"EMA_TREND_FOLLOW", entry:2942.50, target:3085.00, stop:2885.00, rr:2.5, duration_days:10, expiry_date:"2025-05-06", conviction:8.1, status:"TARGET_HIT", outcome:"WIN", exit_price:3091.20, exit_date:"2025-05-02", max_price:3097.40, min_price:2919.80, created_at:"2025-04-26", reasons:["Triple EMA stack bullish: 2942 > EMA9 2930 > EMA20 2905 > EMA50 2860","MACD histogram rising (+12.4)","Supertrend bullish, trailing stop at 2885","ADX 31.2 — strong trending market"] },
  { id:2, stock:"TCS", strategy:"BB_SQUEEZE_BREAK", entry:3756.00, target:3920.00, stop:3690.00, rr:2.48, duration_days:7, expiry_date:"2025-05-03", conviction:7.4, status:"OPEN", outcome:"OPEN", exit_price:null, exit_date:null, max_price:3810.50, min_price:3740.00, created_at:"2025-04-26", reasons:["Bollinger squeeze: width at 15th percentile","Breakout above upper band (3756)","Volume surge 2.3× 20-day average","MACD crossover confirmed"] },
  { id:3, stock:"HDFCBANK", strategy:"ADX_BREAKOUT", entry:1672.30, target:1780.00, stop:1636.00, rr:2.97, duration_days:12, expiry_date:"2025-05-08", conviction:8.6, status:"OPEN", outcome:"OPEN", exit_price:null, exit_date:null, max_price:1698.40, min_price:1660.10, created_at:"2025-04-26", reasons:["ADX 38.4 — strong bullish trend","EMA20 pullback bounce (1658 → 1672)","Supertrend bullish all week","3:1 RR with institutional support at 1636"] },
  { id:4, stock:"INFY", strategy:"RSI_DIVERGENCE", entry:1421.00, target:1510.00, stop:1388.50, rr:2.74, duration_days:8, expiry_date:"2025-05-04", conviction:6.8, status:"STOP_HIT", outcome:"LOSS", exit_price:1388.50, exit_date:"2025-04-30", max_price:1441.20, min_price:1381.00, created_at:"2025-04-26", reasons:["Bullish RSI divergence at RSI 38.4","Price lower low, RSI higher low — accumulation","1.5×ATR stop at 1388.50","Supertrend bullish at entry"] },
  { id:5, stock:"BAJFINANCE", strategy:"VWAP_MOMENTUM", entry:7120.00, target:7390.00, stop:7010.00, rr:2.45, duration_days:5, expiry_date:"2025-05-01", conviction:7.9, status:"TARGET_HIT", outcome:"WIN", exit_price:7401.00, exit_date:"2025-04-30", max_price:7418.00, min_price:7085.00, created_at:"2025-04-26", reasons:["VWAP reclaim at 7095 with 1.9× volume","Institutional buying above VWAP","MACD positive crossover","Stochastic turning from oversold"] },
  { id:6, stock:"SBIN", strategy:"EMA_TREND_FOLLOW", entry:812.40, target:868.00, stop:790.00, rr:2.47, duration_days:10, expiry_date:"2025-05-06", conviction:7.2, status:"OPEN", outcome:"OPEN", exit_price:null, exit_date:null, max_price:829.60, min_price:805.30, created_at:"2025-04-26", reasons:["EMA stack: close > EMA9 > EMA20 > EMA50","MACD histogram rising","Supertrend bullish (stop 790)","Volume breakout 1.6× average"] },
  { id:7, stock:"WIPRO", strategy:"STOCH_REVERSAL", entry:462.50, target:492.00, stop:449.80, rr:2.32, duration_days:4, expiry_date:"2025-04-30", conviction:5.9, status:"EXPIRED", outcome:"LOSS", exit_price:458.20, exit_date:"2025-04-30", max_price:471.00, min_price:450.10, created_at:"2025-04-26", reasons:["Stochastic oversold K=19 D=22","K crossed above D","OBV above OBV-EMA","Near 20-day support"] },
  { id:8, stock:"KOTAKBANK", strategy:"ADX_BREAKOUT", entry:1842.00, target:1965.00, stop:1800.00, rr:2.93, duration_days:12, expiry_date:"2025-05-08", conviction:8.3, status:"OPEN", outcome:"OPEN", exit_price:null, exit_date:null, max_price:1878.00, min_price:1828.00, created_at:"2025-04-26", reasons:["ADX 34 — strong trend","EMA20 bounce pattern","PCR bullish at key strikes","3:1 RR setup"] },
];

const ACCURACY = {
  total: 47, overall: { wins:29, losses:12, expired:6, win_rate:61.7 },
  best_strategy:"ADX_BREAKOUT", worst_strategy:"STOCH_REVERSAL",
  by_strategy: [
    { strategy:"ADX_BREAKOUT",     total:11, wins:8, losses:2, expired:1, win_rate:72.7, avg_rr_offered:3.0, avg_rr_achieved:2.8, avg_days:7.2,  edge:1.18 },
    { strategy:"EMA_TREND_FOLLOW", total:14, wins:9, losses:4, expired:1, win_rate:64.3, avg_rr_offered:2.5, avg_rr_achieved:2.1, avg_days:8.4,  edge:0.71 },
    { strategy:"BB_SQUEEZE_BREAK", total:8,  wins:5, losses:2, expired:1, win_rate:62.5, avg_rr_offered:2.4, avg_rr_achieved:1.9, avg_days:5.1,  edge:0.63 },
    { strategy:"VWAP_MOMENTUM",    total:5,  wins:3, losses:2, expired:0, win_rate:60.0, avg_rr_offered:2.2, avg_rr_achieved:1.6, avg_days:3.8,  edge:0.52 },
    { strategy:"RSI_DIVERGENCE",   total:6,  wins:3, losses:2, expired:1, win_rate:50.0, avg_rr_offered:2.6, avg_rr_achieved:1.8, avg_days:6.3,  edge:0.30 },
    { strategy:"STOCH_REVERSAL",   total:3,  wins:1, losses:2, expired:0, win_rate:33.3, avg_rr_offered:2.2, avg_rr_achieved:0.9, avg_days:3.2,  edge:-0.27 },
  ],
};

const JOURNAL = [
  { id:1, stock:"RELIANCE", entry:2942.50, exit:3091.20, qty:50, pnl:7435, status:"CLOSED", conviction:8.1, grade:"HIGH",  reason:"EMA breakout + PE OI buildup", entry_time:"2025-04-26", exit_time:"2025-05-02" },
  { id:2, stock:"BAJFINANCE", entry:7120, exit:7401, qty:10, pnl:2810, status:"CLOSED", conviction:7.9, grade:"HIGH",  reason:"VWAP reclaim + volume surge", entry_time:"2025-04-26", exit_time:"2025-04-30" },
  { id:3, stock:"INFY", entry:1421, exit:1388.50, qty:40, pnl:-1300, status:"CLOSED", conviction:6.8, grade:"MODERATE", reason:"RSI divergence reversal", entry_time:"2025-04-26", exit_time:"2025-04-30" },
  { id:4, stock:"TCS", entry:3756, exit:null, qty:15, pnl:null, status:"OPEN", conviction:7.4, grade:"HIGH", reason:"BB squeeze breakout", entry_time:"2025-04-26", exit_time:null },
  { id:5, stock:"HDFCBANK", entry:1672.30, exit:null, qty:30, pnl:null, status:"OPEN", conviction:8.6, grade:"HIGH", reason:"ADX trend + EMA bounce", entry_time:"2025-04-26", exit_time:null },
];

const PNL_CHART = [
  {d:"Apr 14",pnl:0},{d:"Apr 17",pnl:3200},{d:"Apr 20",pnl:1800},{d:"Apr 22",pnl:5100},
  {d:"Apr 24",pnl:4200},{d:"Apr 26",pnl:9245},{d:"Apr 28",pnl:7800},{d:"Apr 30",pnl:8945},
];

/* ═══════════════════════════════════════════
   DESIGN TOKENS
═══════════════════════════════════════════ */
const C = {
  bg:       "#03060f",
  panel:    "#080e1c",
  border:   "#101828",
  border2:  "#1a2540",
  amber:    "#f59e0b",
  amberDim: "#78450a",
  green:    "#00d4a0",
  greenDim: "#003d2e",
  red:      "#ff4757",
  redDim:   "#3d0a10",
  blue:     "#3b82f6",
  blueDim:  "#0a1f4a",
  text:     "#e2e8f0",
  muted:    "#475569",
  sub:      "#64748b",
};

const strategyColors = {
  EMA_TREND_FOLLOW:"#f59e0b", BB_SQUEEZE_BREAK:"#3b82f6", RSI_DIVERGENCE:"#00d4a0",
  VWAP_MOMENTUM:"#8b5cf6",   ADX_BREAKOUT:"#f97316",     STOCH_REVERSAL:"#ff4757",
};

/* ═══════════════════════════════════════════
   SHARED COMPONENTS
═══════════════════════════════════════════ */
const Panel = ({ children, style = {}, className = "" }) => (
  <div style={{ background: C.panel, border: `1px solid ${C.border2}`, borderRadius: 10, ...style }}>
    {children}
  </div>
);

const Tag = ({ children, color = C.muted, bg }) => (
  <span style={{
    background: bg || `${color}22`, color, borderRadius: 4,
    padding: "2px 7px", fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
    fontFamily: "'IBM Plex Mono', monospace", whiteSpace: "nowrap",
  }}>{children}</span>
);

const Dot = ({ color }) => (
  <span style={{ display:"inline-block", width:6, height:6, borderRadius:"50%", background:color, marginRight:6 }} />
);

const Bar = ({ value, max = 100, color, height = 4 }) => (
  <div style={{ background: C.border, borderRadius: 99, overflow:"hidden", height }}>
    <div style={{ width:`${Math.min(100,(value/max)*100)}%`, height:"100%", background:color, borderRadius:99, transition:"width 1s ease" }} />
  </div>
);

const statusMeta = s => ({
  TARGET_HIT:{ label:"TARGET HIT", color:C.green,  bg:C.greenDim, icon:"✓" },
  STOP_HIT:  { label:"STOP HIT",   color:C.red,    bg:C.redDim,   icon:"✗" },
  EXPIRED:   { label:"EXPIRED",    color:C.amber,  bg:C.amberDim, icon:"◷" },
  OPEN:      { label:"OPEN",       color:C.blue,   bg:C.blueDim,  icon:"●" },
}[s] || { label:s, color:C.muted, bg:C.border, icon:"○" });

const pct = (v,max) => Math.round(Math.min(100,Math.max(0,(v/max)*100)));

/* ═══════════════════════════════════════════
   TICKER BAR
═══════════════════════════════════════════ */
const TICKERS = [
  {n:"NIFTY 50",v:"23,287.45",c:"+0.82%",up:true},{n:"SENSEX",v:"76,421.30",c:"+0.79%",up:true},
  {n:"BANK NIFTY",v:"49,840.10",c:"+1.12%",up:true},{n:"INDIA VIX",v:"14.32",c:"-3.1%",up:false},
  {n:"RELIANCE",v:"2,942.50",c:"+1.4%",up:true},{n:"TCS",v:"3,756.00",c:"+0.9%",up:true},
  {n:"HDFCBANK",v:"1,672.30",c:"+1.8%",up:true},{n:"SBIN",v:"812.40",c:"+2.1%",up:true},
];

function Ticker() {
  return (
    <div style={{ borderBottom:`1px solid ${C.border2}`, background:"#050b18", overflow:"hidden", height:32, display:"flex", alignItems:"center" }}>
      <div style={{ display:"flex", gap:32, animation:"ticker 30s linear infinite", whiteSpace:"nowrap", paddingLeft:"100%" }}>
        {[...TICKERS,...TICKERS].map((t,i) => (
          <span key={i} style={{ fontSize:11, fontFamily:"'IBM Plex Mono',monospace" }}>
            <span style={{ color:C.muted }}>{t.n} </span>
            <span style={{ color:C.text, fontWeight:700 }}>{t.v} </span>
            <span style={{ color:t.up?C.green:C.red }}>{t.c}</span>
          </span>
        ))}
      </div>
      <style>{`@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}`}</style>
    </div>
  );
}

/* ═══════════════════════════════════════════
   DASHBOARD TAB
═══════════════════════════════════════════ */
function Dashboard() {
  const open = RECOMMENDATIONS.filter(r=>r.status==="OPEN");
  const wins = RECOMMENDATIONS.filter(r=>r.outcome==="WIN");
  const losses = RECOMMENDATIONS.filter(r=>r.outcome==="LOSS");
  const wr = Math.round(wins.length/(wins.length+losses.length)*100);

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gridTemplateRows:"auto auto auto", gap:12 }}>

      {/* Market Bias — spans 2 cols */}
      <Panel style={{ gridColumn:"span 2", padding:20, position:"relative", overflow:"hidden" }}>
        <div style={{ position:"absolute", right:-20, top:-20, width:180, height:180, borderRadius:"50%", background:`${C.green}08`, border:`1px solid ${C.green}18` }} />
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:8, fontFamily:"'IBM Plex Mono',monospace" }}>MARKET INTELLIGENCE</div>
        <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom:14 }}>
          <div style={{ fontSize:36, fontWeight:900, color:C.green, letterSpacing:-2, fontFamily:"'IBM Plex Mono',monospace" }}>BULLISH</div>
          <div>
            <div style={{ display:"flex", gap:8, marginBottom:4 }}>
              <Tag color={C.green}>PCR 1.31</Tag>
              <Tag color={C.amber}>VIX 14.32</Tag>
              <Tag color={C.blue}>NIFTY 23,287</Tag>
            </div>
            <div style={{ fontSize:11, color:C.muted }}>Options flow confirming institutional accumulation</div>
          </div>
        </div>
        <div style={{ fontSize:12, color:C.sub, lineHeight:1.6, borderLeft:`2px solid ${C.green}40`, paddingLeft:12 }}>
          {MARKET.summary}
        </div>
      </Panel>

      {/* Stats card */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:16, fontFamily:"'IBM Plex Mono',monospace" }}>TODAY'S STATS</div>
        {[
          ["WIN RATE", `${wr}%`, C.green], ["OPEN TRADES", open.length, C.blue],
          ["WINS", wins.length, C.green], ["LOSSES", losses.length, C.red],
        ].map(([l,v,c]) => (
          <div key={l} style={{ display:"flex", justifyContent:"space-between", marginBottom:12, alignItems:"center" }}>
            <span style={{ fontSize:10, color:C.muted, fontFamily:"'IBM Plex Mono',monospace" }}>{l}</span>
            <span style={{ fontSize:20, fontWeight:900, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v}</span>
          </div>
        ))}
      </Panel>

      {/* Key Levels */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:16, fontFamily:"'IBM Plex Mono',monospace" }}>OI KEY LEVELS</div>
        {[
          ["RESISTANCE", MARKET.resistance, C.red],
          ["MAX PAIN",   MARKET.max_pain,   C.amber],
          ["SUPPORT",    MARKET.support,    C.green],
        ].map(([l,v,c]) => (
          <div key={l} style={{ marginBottom:14 }}>
            <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
              <span style={{ fontSize:10, color:C.muted, fontFamily:"'IBM Plex Mono',monospace" }}>{l}</span>
              <span style={{ fontSize:16, fontWeight:800, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v.toLocaleString()}</span>
            </div>
            <div style={{ background:C.border, borderRadius:99, height:3 }}>
              <div style={{ width: l==="RESISTANCE"?"90%":l==="SUPPORT"?"30%":"58%", height:"100%", background:c, borderRadius:99 }} />
            </div>
          </div>
        ))}
        <div style={{ marginTop:8, paddingTop:8, borderTop:`1px solid ${C.border2}` }}>
          <div style={{ display:"flex", justifyContent:"space-between", fontSize:11 }}>
            <span style={{ color:C.muted }}>CE OI</span>
            <span style={{ color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{(MARKET.ce_oi/1e6).toFixed(1)}M</span>
          </div>
          <div style={{ display:"flex", justifyContent:"space-between", fontSize:11, marginTop:4 }}>
            <span style={{ color:C.muted }}>PE OI</span>
            <span style={{ color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{(MARKET.pe_oi/1e6).toFixed(1)}M</span>
          </div>
        </div>
      </Panel>

      {/* P&L Chart */}
      <Panel style={{ gridColumn:"span 2", padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>CUMULATIVE P&L (₹)</div>
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={PNL_CHART}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.green} stopOpacity={0.3} />
                <stop offset="100%" stopColor={C.green} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="d" tick={{ fill:C.muted, fontSize:9, fontFamily:"'IBM Plex Mono',monospace" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill:C.muted, fontSize:9, fontFamily:"'IBM Plex Mono',monospace" }} axisLine={false} tickLine={false} tickFormatter={v=>`₹${(v/1000).toFixed(1)}k`} />
            <Tooltip contentStyle={{ background:C.panel, border:`1px solid ${C.border2}`, borderRadius:6, fontSize:11 }} formatter={v=>[`₹${v.toLocaleString()}`,"P&L"]} />
            <Area type="monotone" dataKey="pnl" stroke={C.green} strokeWidth={2} fill="url(#pnlGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      {/* OI Buildups */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>OI BUILDUPS</div>
        {MARKET.buildups.slice(0,4).map((b,i) => {
          const isB = b.buildup==="LONG_BUILDUP"||b.buildup==="SHORT_COVER";
          return (
            <div key={i} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8, padding:"6px 8px", borderRadius:6, background:isB?`${C.green}08`:`${C.red}08` }}>
              <div>
                <span style={{ fontSize:12, fontWeight:700, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{b.strike}</span>
                <span style={{ fontSize:9, color:C.muted, marginLeft:6 }}>{b.type}</span>
              </div>
              <div style={{ textAlign:"right" }}>
                <div style={{ fontSize:9, color:isB?C.green:C.red, fontWeight:700 }}>{b.buildup.replace(/_/g," ")}</div>
                <div style={{ fontSize:9, color:C.muted }}>{b.oi_change>0?"+":""}{(b.oi_change/1e5).toFixed(1)}L OI</div>
              </div>
            </div>
          );
        })}
      </Panel>

      {/* Top Picks preview */}
      <Panel style={{ gridColumn:"span 3", padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>HIGH CONVICTION PICKS TODAY</div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
          {RECOMMENDATIONS.filter(r=>r.status==="OPEN").slice(0,4).map(r => (
            <div key={r.id} style={{ background:C.bg, border:`1px solid ${C.border2}`, borderRadius:8, padding:12, borderTop:`3px solid ${strategyColors[r.strategy]}` }}>
              <div style={{ fontSize:14, fontWeight:800, color:C.text, marginBottom:4 }}>{r.stock}</div>
              <div style={{ fontSize:9, color:C.muted, marginBottom:8 }}>{r.strategy.replace(/_/g," ")}</div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:4 }}>
                {[["Entry",`₹${r.entry}`,C.blue],["Target",`₹${r.target}`,C.green],["Stop",`₹${r.stop}`,C.red],["RR",`${r.rr}:1`,C.amber]].map(([l,v,c])=>(
                  <div key={l} style={{ background:C.panel, borderRadius:4, padding:"4px 6px", textAlign:"center" }}>
                    <div style={{ fontSize:8, color:C.muted }}>{l}</div>
                    <div style={{ fontSize:11, fontWeight:800, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop:8 }}>
                <Bar value={r.conviction} max={10} color={strategyColors[r.strategy]} height={3} />
                <div style={{ fontSize:9, color:C.muted, textAlign:"right", marginTop:2 }}>CV {r.conviction}/10</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

/* ═══════════════════════════════════════════
   RECOMMENDATIONS TAB
═══════════════════════════════════════════ */
function Recommendations() {
  const [filter, setFilter] = useState("ALL");
  const [expanded, setExpanded] = useState({});
  const [validating, setValidating] = useState(false);
  const [toast, setToast] = useState(null);

  const filtered = filter === "ALL" ? RECOMMENDATIONS
    : filter === "OPEN" ? RECOMMENDATIONS.filter(r=>r.status==="OPEN")
    : filter === "WIN"  ? RECOMMENDATIONS.filter(r=>r.outcome==="WIN")
    : RECOMMENDATIONS.filter(r=>r.outcome==="LOSS"||r.outcome==="EXPIRED");

  const runValidator = () => {
    setValidating(true);
    setTimeout(() => {
      setValidating(false);
      setToast("✓ Validated 4 open recommendations — no status changes");
      setTimeout(()=>setToast(null), 3500);
    }, 1800);
  };

  return (
    <div>
      {/* Controls */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <div style={{ display:"flex", gap:6 }}>
          {["ALL","OPEN","WIN","LOSS"].map(f => (
            <button key={f} onClick={()=>setFilter(f)} style={{
              background: filter===f ? C.amber : C.border, color: filter===f ? "#000" : C.muted,
              border:"none", borderRadius:6, padding:"5px 14px", fontSize:11, fontWeight:700,
              cursor:"pointer", fontFamily:"'IBM Plex Mono',monospace", letterSpacing:0.5,
            }}>{f} ({f==="ALL"?RECOMMENDATIONS.length:f==="OPEN"?RECOMMENDATIONS.filter(r=>r.status==="OPEN").length:f==="WIN"?RECOMMENDATIONS.filter(r=>r.outcome==="WIN").length:RECOMMENDATIONS.filter(r=>["LOSS","EXPIRED"].includes(r.outcome)).length})</button>
          ))}
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <button onClick={runValidator} disabled={validating} style={{
            background:validating?C.border:C.green, color:validating?C.muted:"#000",
            border:"none", borderRadius:6, padding:"7px 16px", fontSize:12, fontWeight:700,
            cursor:validating?"not-allowed":"pointer", fontFamily:"'IBM Plex Mono',monospace",
          }}>{validating?"Validating...":"▶ Run Validator"}</button>
          <button style={{ background:C.amber, color:"#000", border:"none", borderRadius:6, padding:"7px 16px", fontSize:12, fontWeight:700, cursor:"pointer", fontFamily:"'IBM Plex Mono',monospace" }}>⊕ Generate</button>
        </div>
      </div>

      {toast && (
        <div style={{ background:C.greenDim, border:`1px solid ${C.green}40`, color:C.green, borderRadius:8, padding:"10px 16px", marginBottom:12, fontSize:12 }}>{toast}</div>
      )}

      <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
        {filtered.map(r => {
          const sm = statusMeta(r.status);
          const sc = strategyColors[r.strategy];
          const exp = !!expanded[r.id];
          const progress = r.max_price ? pct(r.max_price - r.entry, r.target - r.entry) : 0;
          return (
            <Panel key={r.id} style={{ borderLeft:`3px solid ${sc}`, overflow:"hidden" }}>
              <div style={{ padding:"14px 16px" }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:12 }}>
                  <div style={{ display:"flex", gap:12, alignItems:"center" }}>
                    <div>
                      <div style={{ fontSize:18, fontWeight:900, color:C.text, letterSpacing:-0.5 }}>{r.stock}</div>
                      <div style={{ display:"flex", gap:6, marginTop:4 }}>
                        <Tag color={sc}>{r.strategy.replace(/_/g," ")}</Tag>
                        <Tag color={C.muted}>{r.duration_days}d · exp {r.expiry_date}</Tag>
                      </div>
                    </div>
                  </div>
                  <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                    {r.conviction && <div style={{ textAlign:"center" }}>
                      <div style={{ fontSize:18, fontWeight:900, color:sc, fontFamily:"'IBM Plex Mono',monospace" }}>{r.conviction}</div>
                      <div style={{ fontSize:9, color:C.muted }}>CONVICTION</div>
                    </div>}
                    <div style={{ background:sm.bg, color:sm.color, borderRadius:6, padding:"6px 12px", fontSize:11, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace" }}>
                      {sm.icon} {sm.label}
                    </div>
                  </div>
                </div>

                {/* Price levels */}
                <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:8, marginBottom:12 }}>
                  {[["ENTRY",`₹${r.entry}`,C.blue],["TARGET",`₹${r.target}`,C.green],["STOP",`₹${r.stop}`,C.red],["R:R",`${r.rr}:1`,C.amber],["DAYS",r.duration_days,C.muted]].map(([l,v,c])=>(
                    <div key={l} style={{ background:C.bg, borderRadius:8, padding:"10px 0", textAlign:"center" }}>
                      <div style={{ fontSize:9, color:C.muted, marginBottom:3, fontFamily:"'IBM Plex Mono',monospace", letterSpacing:1 }}>{l}</div>
                      <div style={{ fontSize:14, fontWeight:800, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v}</div>
                    </div>
                  ))}
                </div>

                {/* Progress bar for OPEN */}
                {r.status==="OPEN" && r.max_price && (
                  <div style={{ marginBottom:10 }}>
                    <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:C.muted, marginBottom:4, fontFamily:"'IBM Plex Mono',monospace" }}>
                      <span>Progress to target</span>
                      <span style={{ color:C.green }}>High ₹{r.max_price} · {progress}% done</span>
                    </div>
                    <div style={{ background:C.border, borderRadius:99, height:5, position:"relative" }}>
                      <div style={{ width:`${progress}%`, height:"100%", background:`linear-gradient(90deg,${sc},${C.green})`, borderRadius:99, transition:"width 1s" }} />
                    </div>
                  </div>
                )}

                {/* Closed result */}
                {r.status!=="OPEN" && (
                  <div style={{ display:"flex", gap:8, marginBottom:10, flexWrap:"wrap" }}>
                    {r.exit_price&&<Tag color={r.outcome==="WIN"?C.green:C.red} bg={r.outcome==="WIN"?C.greenDim:C.redDim}>Exit ₹{r.exit_price} on {r.exit_date}</Tag>}
                    {r.max_price&&<Tag color={C.green} bg={C.greenDim}>High ₹{r.max_price}</Tag>}
                    {r.min_price&&<Tag color={C.red} bg={C.redDim}>Low ₹{r.min_price}</Tag>}
                  </div>
                )}

                <button onClick={()=>setExpanded(p=>({...p,[r.id]:!p[r.id]}))} style={{
                  background:"none", border:"none", color:C.sub, cursor:"pointer",
                  fontSize:11, padding:0, fontFamily:"'IBM Plex Mono',monospace",
                }}>
                  {exp?"▲ hide rationale":"▼ show rationale"}
                </button>

                {exp && (
                  <div style={{ marginTop:10, borderLeft:`2px solid ${sc}40`, paddingLeft:12 }}>
                    {r.reasons.map((s,i)=>(
                      <div key={i} style={{ fontSize:11, color:C.sub, marginBottom:5 }}>· {s}</div>
                    ))}
                  </div>
                )}
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   SMART MONEY TAB
═══════════════════════════════════════════ */
function SmartMoney() {
  const pcr = MARKET.pcr;
  const pcrAngle = pct(pcr, 2) * 1.8; // 0-180 degrees
  const pcrColor = pcr > 1.2 ? C.green : pcr < 0.8 ? C.red : C.amber;

  const oi_data = MARKET.buildups.map(b=>({ name:`${b.strike}\n${b.type}`, oi:b.oi/1e5, change:b.oi_change/1e5, color:b.oi_change>0?C.green:C.red }));

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>

      {/* PCR Gauge */}
      <Panel style={{ padding:20, display:"flex", flexDirection:"column", alignItems:"center" }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:16, fontFamily:"'IBM Plex Mono',monospace", alignSelf:"flex-start" }}>PUT-CALL RATIO</div>
        <div style={{ position:"relative", width:200, height:110 }}>
          <svg width="200" height="110" viewBox="0 0 200 110">
            <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke={C.border} strokeWidth="16" strokeLinecap="round" />
            <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke={pcrColor} strokeWidth="16" strokeLinecap="round"
              strokeDasharray={`${pct(pcr,2)*2.5} 250`} style={{ transition:"stroke-dasharray 1s" }} />
            <text x="100" y="90" textAnchor="middle" fill={pcrColor} fontSize="28" fontWeight="900" fontFamily="'IBM Plex Mono',monospace">{pcr}</text>
            <text x="100" y="108" textAnchor="middle" fill={C.muted} fontSize="10" fontFamily="'IBM Plex Mono',monospace">PUT-CALL RATIO</text>
            <text x="20" y="108" textAnchor="middle" fill={C.red} fontSize="9">0</text>
            <text x="180" y="108" textAnchor="middle" fill={C.green} fontSize="9">2</text>
          </svg>
        </div>
        <div style={{ marginTop:16, textAlign:"center" }}>
          <div style={{ fontSize:22, fontWeight:900, color:pcrColor, fontFamily:"'IBM Plex Mono',monospace" }}>BULLISH</div>
          <div style={{ fontSize:11, color:C.muted, marginTop:4 }}>PCR > 1.2 → Put writers defending support</div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, width:"100%", marginTop:16 }}>
          {[["CE OI",(MARKET.ce_oi/1e6).toFixed(1)+"M",C.red],["PE OI",(MARKET.pe_oi/1e6).toFixed(1)+"M",C.green]].map(([l,v,c])=>(
            <div key={l} style={{ background:C.bg, borderRadius:8, padding:10, textAlign:"center" }}>
              <div style={{ fontSize:9, color:C.muted, fontFamily:"'IBM Plex Mono',monospace" }}>{l}</div>
              <div style={{ fontSize:18, fontWeight:900, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      </Panel>

      {/* OI by Strike */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>OI BY STRIKE (Lakhs)</div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={oi_data} layout="vertical" barGap={2}>
            <XAxis type="number" tick={{ fill:C.muted, fontSize:9, fontFamily:"'IBM Plex Mono',monospace" }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ fill:C.text, fontSize:10, fontFamily:"'IBM Plex Mono',monospace" }} width={60} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background:C.panel, border:`1px solid ${C.border2}`, borderRadius:6, fontSize:11 }} />
            <Bar dataKey="oi" radius={[0,4,4,0]}>
              {oi_data.map((d,i)=><Cell key={i} fill={d.color} fillOpacity={0.8} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {/* Buildups table — full width */}
      <Panel style={{ gridColumn:"span 2", padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>STRIKE-LEVEL OI BUILDUP ANALYSIS</div>
        <table style={{ width:"100%", borderCollapse:"collapse" }}>
          <thead>
            <tr>
              {["STRIKE","TYPE","OI","OI CHANGE","BUILDUP","INTERPRETATION"].map(h=>(
                <th key={h} style={{ fontSize:9, color:C.muted, textAlign:"left", padding:"8px 12px", fontFamily:"'IBM Plex Mono',monospace", letterSpacing:1, borderBottom:`1px solid ${C.border2}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MARKET.buildups.map((b,i)=>{
              const isB = b.buildup==="LONG_BUILDUP"||b.buildup==="SHORT_COVER";
              const interp = {
                LONG_BUILDUP:"Put writers building longs — bulls defending",
                SHORT_COVER:"Call writers closing shorts — bearish pressure easing",
                SHORT_BUILDUP:"Call writers building shorts — resistance forming",
                LONG_UNWIND:"Put writers exiting — support weakening",
              }[b.buildup];
              return (
                <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ padding:"10px 12px", fontSize:13, fontWeight:800, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{b.strike.toLocaleString()}</td>
                  <td style={{ padding:"10px 12px" }}><Tag color={b.type==="PE"?C.green:C.red}>{b.type}</Tag></td>
                  <td style={{ padding:"10px 12px", fontSize:11, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{(b.oi/1e5).toFixed(1)}L</td>
                  <td style={{ padding:"10px 12px", fontSize:11, color:b.oi_change>0?C.green:C.red, fontFamily:"'IBM Plex Mono',monospace" }}>{b.oi_change>0?"+":""}{(b.oi_change/1e5).toFixed(1)}L</td>
                  <td style={{ padding:"10px 12px" }}><Tag color={isB?C.green:C.red} bg={isB?C.greenDim:C.redDim}>{b.buildup.replace(/_/g," ")}</Tag></td>
                  <td style={{ padding:"10px 12px", fontSize:11, color:C.sub }}>{interp}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

/* ═══════════════════════════════════════════
   ACCURACY TAB
═══════════════════════════════════════════ */
function Accuracy() {
  const ov = ACCURACY.overall;
  const pieData = [
    { name:"Wins", value:ov.wins, fill:C.green },
    { name:"Losses", value:ov.losses, fill:C.red },
    { name:"Expired", value:ov.expired, fill:C.amber },
  ];

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>

      {/* Overall */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:16, fontFamily:"'IBM Plex Mono',monospace" }}>OVERALL ACCURACY</div>
        <div style={{ display:"flex", alignItems:"center", gap:24 }}>
          <div>
            <div style={{ fontSize:48, fontWeight:900, color:C.green, fontFamily:"'IBM Plex Mono',monospace", lineHeight:1 }}>{ov.win_rate}%</div>
            <div style={{ fontSize:12, color:C.muted, marginTop:4 }}>WIN RATE</div>
            <div style={{ marginTop:12 }}>
              <Bar value={ov.win_rate} max={100} color={C.green} height={8} />
            </div>
          </div>
          <ResponsiveContainer width={120} height={120}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={30} outerRadius={55} dataKey="value" paddingAngle={3}>
                {pieData.map((d,i)=><Cell key={i} fill={d.fill} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:8, marginTop:16 }}>
          {[["WINS",ov.wins,C.green],["LOSSES",ov.losses,C.red],["EXPIRED",ov.expired,C.amber]].map(([l,v,c])=>(
            <div key={l} style={{ background:C.bg, borderRadius:8, padding:10, textAlign:"center" }}>
              <div style={{ fontSize:22, fontWeight:900, color:c, fontFamily:"'IBM Plex Mono',monospace" }}>{v}</div>
              <div style={{ fontSize:9, color:C.muted }}>{l}</div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Strategy leaderboard */}
      <Panel style={{ padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:16, fontFamily:"'IBM Plex Mono',monospace" }}>STRATEGY LEADERBOARD</div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={ACCURACY.by_strategy} layout="vertical">
            <XAxis type="number" domain={[0,100]} tick={{ fill:C.muted, fontSize:9, fontFamily:"'IBM Plex Mono',monospace" }} axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`} />
            <YAxis type="category" dataKey="strategy" tick={{ fill:C.text, fontSize:8, fontFamily:"'IBM Plex Mono',monospace" }} width={100} axisLine={false} tickLine={false} tickFormatter={v=>v.replace(/_/g," ")} />
            <Tooltip contentStyle={{ background:C.panel, border:`1px solid ${C.border2}`, borderRadius:6, fontSize:11 }} formatter={v=>[`${v}%`,"Win Rate"]} />
            <Bar dataKey="win_rate" radius={[0,6,6,0]}>
              {ACCURACY.by_strategy.map((d,i)=><Cell key={i} fill={strategyColors[d.strategy]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {/* Full strategy breakdown */}
      <Panel style={{ gridColumn:"span 2", padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>STRATEGY PERFORMANCE BREAKDOWN</div>
        <table style={{ width:"100%", borderCollapse:"collapse" }}>
          <thead>
            <tr>
              {["STRATEGY","WIN RATE","W/L/E","RR OFFERED","RR ACHIEVED","AVG DAYS","EDGE SCORE"].map(h=>(
                <th key={h} style={{ fontSize:9, color:C.muted, textAlign:"left", padding:"8px 12px", fontFamily:"'IBM Plex Mono',monospace", letterSpacing:1, borderBottom:`1px solid ${C.border2}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ACCURACY.by_strategy.map((s,i)=>{
              const wr = s.win_rate;
              const wc = wr>=65?C.green:wr>=50?C.amber:C.red;
              const ec = s.edge>0?C.green:C.red;
              return (
                <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ padding:"10px 12px" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                      <div style={{ width:8, height:8, borderRadius:"50%", background:strategyColors[s.strategy], flexShrink:0 }} />
                      <span style={{ fontSize:12, fontWeight:700, color:C.text }}>{s.strategy.replace(/_/g," ")}</span>
                    </div>
                  </td>
                  <td style={{ padding:"10px 12px" }}>
                    <div>
                      <div style={{ fontSize:16, fontWeight:900, color:wc, fontFamily:"'IBM Plex Mono',monospace" }}>{wr}%</div>
                      <Bar value={wr} max={100} color={wc} height={3} />
                    </div>
                  </td>
                  <td style={{ padding:"10px 12px", fontSize:12, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{s.wins}W / {s.losses}L / {s.expired}E</td>
                  <td style={{ padding:"10px 12px", fontSize:13, fontWeight:700, color:C.blue, fontFamily:"'IBM Plex Mono',monospace" }}>{s.avg_rr_offered}:1</td>
                  <td style={{ padding:"10px 12px", fontSize:13, fontWeight:700, color:C.amber, fontFamily:"'IBM Plex Mono',monospace" }}>{s.avg_rr_achieved}:1</td>
                  <td style={{ padding:"10px 12px", fontSize:12, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{s.avg_days}d</td>
                  <td style={{ padding:"10px 12px" }}>
                    <Tag color={ec} bg={`${ec}18`}>{s.edge>0?"+":""}{s.edge}</Tag>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

/* ═══════════════════════════════════════════
   JOURNAL TAB
═══════════════════════════════════════════ */
function Journal() {
  const closed = JOURNAL.filter(t=>t.status==="CLOSED");
  const totalPnl = closed.reduce((s,t)=>s+(t.pnl||0),0);
  const wins = closed.filter(t=>t.pnl>0);
  const losses = closed.filter(t=>t.pnl<=0);

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12 }}>

      {/* Summary cards */}
      {[
        ["TOTAL P&L", `₹${totalPnl.toLocaleString()}`, totalPnl>=0?C.green:C.red, "CLOSED TRADES"],
        ["WIN RATE",  `${Math.round(wins.length/closed.length*100)}%`, C.green, `${wins.length} wins of ${closed.length}`],
        ["PROFIT FACTOR", `${Math.abs((wins.reduce((s,t)=>s+t.pnl,0))/(losses.reduce((s,t)=>s+t.pnl,0)||1)).toFixed(2)}`, C.amber, "Gross profit / gross loss"],
      ].map(([l,v,c,sub])=>(
        <Panel key={l} style={{ padding:16 }}>
          <div style={{ fontSize:10, color:C.muted, letterSpacing:2, fontFamily:"'IBM Plex Mono',monospace" }}>{l}</div>
          <div style={{ fontSize:32, fontWeight:900, color:c, fontFamily:"'IBM Plex Mono',monospace", margin:"8px 0 4px" }}>{v}</div>
          <div style={{ fontSize:11, color:C.sub }}>{sub}</div>
        </Panel>
      ))}

      {/* Trades table */}
      <Panel style={{ gridColumn:"span 3", padding:20 }}>
        <div style={{ fontSize:10, color:C.muted, letterSpacing:2, marginBottom:12, fontFamily:"'IBM Plex Mono',monospace" }}>TRADE HISTORY</div>
        <table style={{ width:"100%", borderCollapse:"collapse" }}>
          <thead>
            <tr>
              {["STOCK","ENTRY","EXIT","QTY","P&L","CONVICTION","STRATEGY","STATUS","REASON"].map(h=>(
                <th key={h} style={{ fontSize:9, color:C.muted, textAlign:"left", padding:"8px 10px", fontFamily:"'IBM Plex Mono',monospace", letterSpacing:1, borderBottom:`1px solid ${C.border2}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {JOURNAL.map(t=>{
              const pnlColor = t.pnl===null?C.blue:t.pnl>=0?C.green:C.red;
              const strategy = RECOMMENDATIONS.find(r=>r.stock===t.stock)?.strategy || "—";
              return (
                <tr key={t.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ padding:"10px 10px", fontSize:13, fontWeight:800, color:C.text }}>{t.stock}</td>
                  <td style={{ padding:"10px 10px", fontSize:11, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>₹{t.entry}</td>
                  <td style={{ padding:"10px 10px", fontSize:11, color:C.text, fontFamily:"'IBM Plex Mono',monospace" }}>{t.exit?`₹${t.exit}`:"—"}</td>
                  <td style={{ padding:"10px 10px", fontSize:11, color:C.muted, fontFamily:"'IBM Plex Mono',monospace" }}>{t.qty}</td>
                  <td style={{ padding:"10px 10px", fontSize:13, fontWeight:800, color:pnlColor, fontFamily:"'IBM Plex Mono',monospace" }}>{t.pnl!==null?`${t.pnl>0?"+":""}₹${t.pnl.toLocaleString()}`:"OPEN"}</td>
                  <td style={{ padding:"10px 10px" }}><Tag color={t.grade==="HIGH"?C.green:C.amber}>{t.grade} {t.conviction}</Tag></td>
                  <td style={{ padding:"10px 10px" }}><Tag color={strategyColors[strategy]||C.muted}>{strategy.replace(/_/g," ")}</Tag></td>
                  <td style={{ padding:"10px 10px" }}>
                    <Tag color={t.status==="OPEN"?C.blue:t.pnl>0?C.green:C.red} bg={t.status==="OPEN"?C.blueDim:t.pnl>0?C.greenDim:C.redDim}>{t.status}</Tag>
                  </td>
                  <td style={{ padding:"10px 10px", fontSize:10, color:C.sub, maxWidth:160 }}>{t.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

/* ═══════════════════════════════════════════
   ROOT APP
═══════════════════════════════════════════ */
const TABS = [
  { id:"dashboard",       label:"Dashboard" },
  { id:"recommendations", label:"Recommendations" },
  { id:"smartmoney",      label:"Smart Money" },
  { id:"accuracy",        label:"Accuracy" },
  { id:"journal",         label:"Journal" },
];

export default function App() {
  const [tab, setTab] = useState("dashboard");

  return (
    <div style={{ minHeight:"100vh", background:C.bg, fontFamily:"'IBM Plex Sans', sans-serif", color:C.text }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;700;900&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:${C.bg}}
        ::-webkit-scrollbar-thumb{background:${C.border2};border-radius:2px}
        body{background:${C.bg}}
      `}</style>

      {/* Ticker */}
      <Ticker />

      {/* Header */}
      <div style={{ borderBottom:`1px solid ${C.border2}`, padding:"0 24px", display:"flex", alignItems:"center", justifyContent:"space-between", height:52 }}>
        <div style={{ display:"flex", alignItems:"center", gap:16 }}>
          <div>
            <span style={{ fontSize:16, fontWeight:900, color:C.amber, letterSpacing:-0.5, fontFamily:"'IBM Plex Mono',monospace" }}>NSE</span>
            <span style={{ fontSize:16, fontWeight:900, color:C.text, letterSpacing:-0.5, fontFamily:"'IBM Plex Mono',monospace" }}>·AI</span>
          </div>
          <div style={{ width:1, height:20, background:C.border2 }} />
          <nav style={{ display:"flex" }}>
            {TABS.map(t=>(
              <button key={t.id} onClick={()=>setTab(t.id)} style={{
                background:"none", border:"none", cursor:"pointer", fontFamily:"'IBM Plex Sans',sans-serif",
                color: tab===t.id ? C.amber : C.muted, fontWeight: tab===t.id ? 700 : 400,
                fontSize:13, padding:"0 16px", height:52,
                borderBottom: tab===t.id ? `2px solid ${C.amber}` : "2px solid transparent",
                transition:"all 0.2s",
              }}>{t.label}</button>
            ))}
          </nav>
        </div>
        <div style={{ display:"flex", gap:16, alignItems:"center", fontSize:12 }}>
          <span style={{ color:C.green, fontFamily:"'IBM Plex Mono',monospace" }}>● LIVE</span>
          <span style={{ color:C.muted }}>NIFTY <strong style={{ color:C.text }}>23,287.45</strong> <span style={{ color:C.green }}>+0.82%</span></span>
          <span style={{ color:C.muted }}>VIX <strong style={{ color:C.amber }}>14.32</strong></span>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding:24, maxWidth:1400, margin:"0 auto" }}>
        {tab==="dashboard"        && <Dashboard />}
        {tab==="recommendations"  && <Recommendations />}
        {tab==="smartmoney"       && <SmartMoney />}
        {tab==="accuracy"         && <Accuracy />}
        {tab==="journal"          && <Journal />}
      </div>
    </div>
  );
}
