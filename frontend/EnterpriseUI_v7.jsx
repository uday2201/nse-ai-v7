import { useState, useEffect, useCallback } from "react";
import { AreaChart, Area, BarChart, Bar, LineChart, Line, RadarChart, Radar, PolarGrid, PolarAngleAxis, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine, ScatterChart, Scatter } from "recharts";

/* ═══════════════════════════════════
   DESIGN SYSTEM
═══════════════════════════════════ */
const T = {
  bg0: "#020817", bg1: "#050d1a", bg2: "#080e1c",
  border: "#0f1e35", border2: "#1a2f50",
  amber: "#f59e0b", amberD: "#92400e",
  green: "#00d4a0", greenD: "#003d2e",
  red: "#ff4757", redD: "#3d0a10",
  blue: "#3b82f6", blueD: "#0a1f4a",
  purple: "#8b5cf6", purpleD: "#2e1065",
  orange: "#f97316", cyan: "#06b6d4",
  text: "#e2e8f0", muted: "#475569", sub: "#334155",
  mono: "'IBM Plex Mono', monospace",
  sans: "'IBM Plex Sans', sans-serif",
};

const STRATEGY_COLORS = {
  EMA_TREND_FOLLOW:"#f59e0b", BB_SQUEEZE_BREAK:"#3b82f6",
  RSI_DIVERGENCE:"#00d4a0", VWAP_MOMENTUM:"#8b5cf6",
  ADX_BREAKOUT:"#f97316", STOCH_REVERSAL:"#ff4757",
};

/* ═══════════════════════════════════
   MOCK DATA
═══════════════════════════════════ */
const MOCK_OPTIONS_SIGNALS = [
  { id:1, stock:"RELIANCE", strike:2950, option_type:"PE", signal_type:"PUT_WRITING", direction:"BULLISH", confidence:8.9, oi:8500000, oi_change:2100000, oi_change_pct:32.8, iv:18.4, ltp:42.5, spot:2942, rationale:"Smart money writing puts at 2950 — defending support, strong bullish signal", scanned_at:"2025-04-27T09:22:00" },
  { id:2, stock:"TCS", strike:3800, option_type:"CE", signal_type:"OI_SPIKE", direction:"BEARISH", confidence:8.2, oi:6200000, oi_change:3100000, oi_change_pct:100, iv:21.2, ltp:28.0, spot:3756, rationale:"CE OI doubled at 3800 — institutional resistance building", scanned_at:"2025-04-27T09:22:10" },
  { id:3, stock:"HDFCBANK", strike:1650, option_type:"BOTH", signal_type:"STRADDLE_BUY", direction:"NEUTRAL", confidence:7.8, oi:14200000, oi_change:0, oi_change_pct:0, iv:15.9, ltp:0, spot:1672, rationale:"Balanced CE+PE OI at 1650 — big move expected, direction unclear", scanned_at:"2025-04-27T09:22:20" },
  { id:4, stock:"NIFTY", strike:23000, option_type:"PE", signal_type:"GAMMA_SQUEEZE", direction:"BULLISH", confidence:9.1, oi:9200000, oi_change:4100000, oi_change_pct:80, iv:14.8, ltp:95.0, spot:23287, rationale:"GAMMA SQUEEZE risk — MM delta-hedging may amplify upward move", scanned_at:"2025-04-27T09:22:30" },
  { id:5, stock:"BAJFINANCE", strike:7100, option_type:"CE", signal_type:"IV_EXPANSION", direction:"NEUTRAL", confidence:7.2, oi:3100000, oi_change:900000, oi_change_pct:41, iv:32.5, ltp:85.0, spot:7120, rationale:"IV expanded 38% with OI building — large directional move expected", scanned_at:"2025-04-27T09:22:40" },
  { id:6, stock:"SBIN", strike:800, option_type:"PE", signal_type:"PUT_WRITING", direction:"BULLISH", confidence:8.0, oi:5800000, oi_change:1400000, oi_change_pct:31.8, iv:22.1, ltp:12.5, spot:812, rationale:"Smart money writing puts at 800 support — institutional buying signal", scanned_at:"2025-04-27T09:22:50" },
];

const MOCK_STRIKE_DATA = {
  symbol:"NIFTY", spot:23287, expiry:"2025-04-24",
  aggregate_pcr:{ pcr:1.31, total_ce_oi:18420000, total_pe_oi:24130000, bias:"BULLISH" },
  max_pain:{ max_pain_strike:23200, zone_low:22968, zone_high:23432 },
  mm_range:{ lower:23000, upper:23500, width_pct:2.15, spot_in_range:true, spot_position_pct:58 },
  skew:{ otm_put_iv:16.2, otm_call_iv:12.8, skew:3.4, signal:"MODERATE_FEAR" },
  bias:"BULLISH",
  summary:"NIFTY multi-strike: PCR 1.31 (BULLISH). Max pain ₹23200. Key support ₹23000, resistance ₹23500. MM range ₹23000–₹23500.",
  support_levels:[
    {strike:23000,pe_oi:9200000,pe_iv:16.4,label:"SUPPORT"},
    {strike:22900,pe_oi:6200000,pe_iv:17.1,label:"SUPPORT"},
    {strike:22800,pe_oi:4800000,pe_iv:18.2,label:"SUPPORT"},
    {strike:22700,pe_oi:3900000,pe_iv:19.0,label:"SUPPORT"},
    {strike:22600,pe_oi:3100000,pe_iv:20.1,label:"SUPPORT"},
  ],
  resistance_levels:[
    {strike:23500,ce_oi:9100000,ce_iv:12.4,label:"RESISTANCE"},
    {strike:23600,ce_oi:7200000,ce_iv:13.1,label:"RESISTANCE"},
    {strike:23700,ce_oi:5800000,ce_iv:13.9,label:"RESISTANCE"},
    {strike:24000,ce_oi:4500000,ce_iv:14.8,label:"RESISTANCE"},
    {strike:24500,ce_oi:3200000,ce_iv:16.2,label:"RESISTANCE"},
  ],
  top_strikes:[
    {strike:23000,moneyness:-1.24,ce_oi:4100000,ce_iv:13.2,pe_oi:9200000,pe_iv:16.4,pcr:2.24,ce_chg:-200000,pe_chg:420000,total_oi:13300000},
    {strike:23500,moneyness:0.91, ce_oi:9100000,ce_iv:12.4,pe_oi:2800000,pe_iv:14.8,pcr:0.31,ce_chg:-180000,pe_chg:-90000, total_oi:11900000},
    {strike:23200,moneyness:-0.37,ce_oi:5100000,ce_iv:12.8,pe_oi:6200000,pe_iv:15.6,pcr:1.22,ce_chg:310000, pe_chg:180000, total_oi:11300000},
    {strike:23300,moneyness:0.06, ce_oi:5800000,ce_iv:12.6,pe_oi:4900000,pe_iv:15.1,pcr:0.84,ce_chg:120000, pe_chg:240000, total_oi:10700000},
    {strike:22800,moneyness:-2.10,ce_oi:1800000,ce_iv:14.1,pe_oi:4800000,pe_iv:18.2,pcr:2.67,ce_chg:-80000, pe_chg:310000, total_oi:6600000},
  ],
};

const MOCK_ENSEMBLE = [
  { stock:"HDFCBANK", final_score:8.9, confidence:"VERY_HIGH", grade:"A", direction:"BULLISH", strategies_agree:4, strategies_fired:["ADX_BREAKOUT","EMA_TREND_FOLLOW","VWAP_MOMENTUM","BB_SQUEEZE_BREAK"], votes:{ADX_BREAKOUT:8.2,EMA_TREND_FOLLOW:7.9,VWAP_MOMENTUM:7.1,BB_SQUEEZE_BREAK:6.8} },
  { stock:"RELIANCE", final_score:8.1, confidence:"VERY_HIGH", grade:"A", direction:"BULLISH", strategies_agree:4, strategies_fired:["EMA_TREND_FOLLOW","ADX_BREAKOUT","RSI_DIVERGENCE","VWAP_MOMENTUM"], votes:{EMA_TREND_FOLLOW:8.1,ADX_BREAKOUT:7.8,RSI_DIVERGENCE:7.2,VWAP_MOMENTUM:6.9} },
  { stock:"TCS",      final_score:7.4, confidence:"HIGH",      grade:"B", direction:"BULLISH", strategies_agree:3, strategies_fired:["BB_SQUEEZE_BREAK","EMA_TREND_FOLLOW","VWAP_MOMENTUM"], votes:{BB_SQUEEZE_BREAK:7.8,EMA_TREND_FOLLOW:7.1,VWAP_MOMENTUM:6.8} },
  { stock:"SBIN",     final_score:7.2, confidence:"HIGH",      grade:"B", direction:"BULLISH", strategies_agree:3, strategies_fired:["ADX_BREAKOUT","EMA_TREND_FOLLOW","STOCH_REVERSAL"], votes:{ADX_BREAKOUT:7.6,EMA_TREND_FOLLOW:7.0,STOCH_REVERSAL:6.2} },
  { stock:"BAJFINANCE",final_score:6.8,confidence:"HIGH",      grade:"B", direction:"BULLISH", strategies_agree:2, strategies_fired:["VWAP_MOMENTUM","RSI_DIVERGENCE"], votes:{VWAP_MOMENTUM:7.2,RSI_DIVERGENCE:6.8} },
];

const MOCK_PROMOTER = [
  { stock:"ADANIENT",   change_pct:2.8, promoter_pct:74.2, prev_pct:71.4, signal:"STRONG_BUY", quarter:"Dec 2024" },
  { stock:"TATASTEEL",  change_pct:1.4, promoter_pct:34.1, prev_pct:32.7, signal:"BUY",         quarter:"Dec 2024" },
  { stock:"BAJFINANCE", change_pct:-1.8,promoter_pct:55.9, prev_pct:57.7, signal:"SELL",        quarter:"Dec 2024" },
  { stock:"HCLTECH",    change_pct:0.9, promoter_pct:60.8, prev_pct:59.9, signal:"BUY",         quarter:"Dec 2024" },
  { stock:"INFY",       change_pct:-0.7,promoter_pct:14.9, prev_pct:15.6, signal:"SELL",        quarter:"Dec 2024" },
];

const MOCK_BULK = [
  { stock:"HDFCBANK", client:"Nippon India MF", action:"BUY",  value_cr:284, price:1672, qty:1700000, deal_type:"BLOCK", deal_date:"2025-04-26" },
  { stock:"RELIANCE", client:"LIC of India",    action:"BUY",  value_cr:445, price:2942, qty:1512000, deal_type:"BULK",  deal_date:"2025-04-26" },
  { stock:"WIPRO",    client:"Foreign Inst",    action:"SELL", value_cr:120, price:462,  qty:2597000, deal_type:"BLOCK", deal_date:"2025-04-26" },
  { stock:"SBIN",     client:"SBI MF",          action:"BUY",  value_cr:98,  price:812,  qty:1207000, deal_type:"BULK",  deal_date:"2025-04-26" },
];

const MOCK_REGIME = { vix:14.32, regime:"NORMAL", size_mult:1.0, stop_mult:1.0, min_conviction:6.0, vix_change_1d:2.1, signals:["IV_CHEAP — options underpriced, prefer buying strategies"] };

/* ═══════════════════════════════════
   SHARED COMPONENTS
═══════════════════════════════════ */
const Panel = ({children,style={}}) => (
  <div style={{background:T.bg2,border:`1px solid ${T.border2}`,borderRadius:12,overflow:"hidden",...style}}>{children}</div>
);
const Label = ({children,style={}}) => (
  <div style={{fontSize:9,color:T.muted,letterSpacing:2,fontFamily:T.mono,fontWeight:700,marginBottom:12,...style}}>{children}</div>
);
const Tag = ({children,color=T.muted,bg}) => (
  <span style={{background:bg||`${color}20`,color,borderRadius:4,padding:"2px 8px",fontSize:10,fontWeight:700,fontFamily:T.mono,whiteSpace:"nowrap"}}>{children}</span>
);
const Bar2 = ({value,max=100,color,h=5}) => (
  <div style={{background:T.border,borderRadius:99,height:h,overflow:"hidden"}}>
    <div style={{width:`${Math.min(100,(value/max)*100)}%`,height:"100%",background:color,borderRadius:99,transition:"width 1s"}}/>
  </div>
);

const SIGNAL_META = {
  PUT_WRITING:  {color:T.green, icon:"🟢", short:"Put Write"},
  CALL_WRITING: {color:T.red,   icon:"🔴", short:"Call Write"},
  OI_SPIKE:     {color:T.amber, icon:"⚡", short:"OI Spike"},
  GAMMA_SQUEEZE:{color:T.purple,icon:"💥", short:"Gamma Squeeze"},
  STRADDLE_BUY: {color:T.cyan,  icon:"⚖️", short:"Straddle"},
  IV_EXPANSION: {color:T.orange,icon:"📈", short:"IV Expand"},
  IV_CRUSH:     {color:T.blue,  icon:"📉", short:"IV Crush"},
};

/* ═══════════════════════════════════
   OPTIONS SCANNER SCREEN
═══════════════════════════════════ */
function OptionsScannerScreen() {
  const [filter, setFilter] = useState("ALL");
  const [scanning, setScanning] = useState(false);

  const signals = filter === "ALL" ? MOCK_OPTIONS_SIGNALS
    : MOCK_OPTIONS_SIGNALS.filter(s => s.direction === filter || s.signal_type === filter);

  const runScan = () => { setScanning(true); setTimeout(()=>setScanning(false), 2000); };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      {/* Controls */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div>
          <div style={{fontSize:20,fontWeight:900,color:T.text}}>Options Chain Scanner</div>
          <div style={{fontSize:11,color:T.muted,marginTop:2}}>Real-time unusual activity detection across all F&O stocks</div>
        </div>
        <div style={{display:"flex",gap:8}}>
          <button onClick={runScan} style={{background:scanning?T.border:T.green,color:scanning?T.muted:"#000",border:"none",borderRadius:8,padding:"8px 20px",fontSize:12,fontWeight:700,cursor:scanning?"not-allowed":"pointer",fontFamily:T.mono}}>
            {scanning?"Scanning...":"⟳ Scan Now"}
          </button>
        </div>
      </div>

      {/* Signal type filters */}
      <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
        {["ALL","BULLISH","BEARISH","PUT_WRITING","OI_SPIKE","GAMMA_SQUEEZE","STRADDLE_BUY"].map(f=>(
          <button key={f} onClick={()=>setFilter(f)} style={{
            background:filter===f?T.amber:T.border,color:filter===f?"#000":T.muted,
            border:"none",borderRadius:6,padding:"4px 12px",fontSize:10,fontWeight:700,
            cursor:"pointer",fontFamily:T.mono,letterSpacing:0.5,
          }}>{f.replace(/_/g," ")}</button>
        ))}
      </div>

      {/* Signal cards */}
      {signals.map(s=>{
        const meta = SIGNAL_META[s.signal_type] || {color:T.muted,icon:"○",short:s.signal_type};
        const dirColor = s.direction==="BULLISH"?T.green:s.direction==="BEARISH"?T.red:T.amber;
        return (
          <Panel key={s.id} style={{borderLeft:`3px solid ${meta.color}`}}>
            <div style={{padding:"14px 16px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
                <div style={{display:"flex",gap:10,alignItems:"center"}}>
                  <span style={{fontSize:20}}>{meta.icon}</span>
                  <div>
                    <div style={{display:"flex",gap:8,alignItems:"center"}}>
                      <span style={{fontSize:17,fontWeight:900,color:T.text}}>{s.stock}</span>
                      <Tag color={meta.color}>{meta.short}</Tag>
                      <Tag color={dirColor}>{s.direction}</Tag>
                    </div>
                    <div style={{fontSize:10,color:T.muted,marginTop:2,fontFamily:T.mono}}>Strike ₹{s.strike.toLocaleString()} · {s.option_type} · IV {s.iv}%</div>
                  </div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontSize:22,fontWeight:900,color:meta.color,fontFamily:T.mono}}>{s.confidence}</div>
                  <div style={{fontSize:9,color:T.muted}}>CONFIDENCE</div>
                </div>
              </div>

              <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:8,marginBottom:10}}>
                {[
                  ["OI",`${(s.oi/1e5).toFixed(1)}L`,T.text],
                  ["OI ΔΔ",`${s.oi_change>0?"+":""}${(s.oi_change/1e5).toFixed(1)}L`,s.oi_change>0?T.green:T.red],
                  ["OI %",`${s.oi_change_pct>0?"+":""}${s.oi_change_pct}%`,s.oi_change_pct>0?T.green:T.red],
                  ["LTP",`₹${s.ltp}`,T.amber],
                ].map(([l,v,c])=>(
                  <div key={l} style={{background:T.bg1,borderRadius:8,padding:"8px",textAlign:"center"}}>
                    <div style={{fontSize:9,color:T.muted,fontFamily:T.mono}}>{l}</div>
                    <div style={{fontSize:13,fontWeight:800,color:c,fontFamily:T.mono}}>{v}</div>
                  </div>
                ))}
              </div>

              <div style={{fontSize:11,color:T.sub,borderLeft:`2px solid ${meta.color}40`,paddingLeft:10}}>
                {s.rationale}
              </div>
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════
   MULTI-STRIKE SCREEN
═══════════════════════════════════ */
function MultiStrikeScreen() {
  const d   = MOCK_STRIKE_DATA;
  const pcr = d.aggregate_pcr;

  const strikeChartData = d.top_strikes.map(s=>({
    name: s.strike.toString(),
    ce: Math.round(s.ce_oi/1e5),
    pe: Math.round(s.pe_oi/1e5),
    pcr: s.pcr,
  }));

  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div style={{fontSize:20,fontWeight:900,color:T.text}}>Multi-Strike OI Analysis</div>

      {/* Top row */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
        {/* PCR */}
        <Panel style={{padding:16}}>
          <Label>AGGREGATE PCR</Label>
          <div style={{fontSize:48,fontWeight:900,color:pcr.pcr>1.2?T.green:pcr.pcr<0.8?T.red:T.amber,fontFamily:T.mono,lineHeight:1}}>{pcr.pcr}</div>
          <Tag color={pcr.pcr>1.2?T.green:T.red}>{pcr.bias}</Tag>
          <div style={{display:"flex",justifyContent:"space-between",marginTop:12,fontSize:10,color:T.muted}}>
            <span>CE {(pcr.total_ce_oi/1e6).toFixed(1)}M</span>
            <span>PE {(pcr.total_pe_oi/1e6).toFixed(1)}M</span>
          </div>
          <Bar2 value={pcr.pcr} max={2} color={T.green} h={6} />
        </Panel>

        {/* Max Pain */}
        <Panel style={{padding:16}}>
          <Label>MAX PAIN</Label>
          <div style={{fontSize:32,fontWeight:900,color:T.amber,fontFamily:T.mono}}>₹{d.max_pain.max_pain_strike.toLocaleString()}</div>
          <div style={{fontSize:10,color:T.muted,marginTop:4}}>Zone: ₹{d.max_pain.zone_low.toLocaleString()} – ₹{d.max_pain.zone_high.toLocaleString()}</div>
          <div style={{fontSize:10,color:T.sub,marginTop:8,lineHeight:1.5}}>Price gravitates here near expiry — option buyer pain maximised</div>
        </Panel>

        {/* Skew */}
        <Panel style={{padding:16}}>
          <Label>VOL SKEW</Label>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
            <div>
              <div style={{fontSize:9,color:T.muted}}>OTM PUT IV</div>
              <div style={{fontSize:20,fontWeight:800,color:T.red,fontFamily:T.mono}}>{d.skew.otm_put_iv}%</div>
            </div>
            <div style={{fontSize:18,color:T.muted}}>–</div>
            <div>
              <div style={{fontSize:9,color:T.muted}}>OTM CALL IV</div>
              <div style={{fontSize:20,fontWeight:800,color:T.green,fontFamily:T.mono}}>{d.skew.otm_call_iv}%</div>
            </div>
            <div>
              <div style={{fontSize:9,color:T.muted}}>SKEW</div>
              <div style={{fontSize:20,fontWeight:800,color:T.amber,fontFamily:T.mono}}>+{d.skew.skew}</div>
            </div>
          </div>
          <Tag color={T.amber}>{d.skew.signal.split("—")[0].trim()}</Tag>
        </Panel>
      </div>

      {/* MM Range */}
      <Panel style={{padding:16}}>
        <Label>MARKET MAKER EXPECTED RANGE</Label>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:8}}>
          <span style={{color:T.green,fontFamily:T.mono,fontWeight:700}}>₹{d.mm_range.lower.toLocaleString()}</span>
          <div style={{flex:1,position:"relative",height:24}}>
            <div style={{height:8,background:T.border,borderRadius:99,marginTop:8}}/>
            <div style={{
              position:"absolute",top:0,left:`${d.mm_range.spot_position_pct}%`,
              transform:"translateX(-50%)",background:T.amber,color:"#000",
              borderRadius:4,padding:"2px 6px",fontSize:9,fontWeight:700,fontFamily:T.mono,whiteSpace:"nowrap"
            }}>SPOT {d.spot.toLocaleString()}</div>
            <div style={{
              position:"absolute",top:8,height:8,
              left:"0%",right:`${100-d.mm_range.spot_position_pct}%`,
              background:`${T.green}40`,borderRadius:"99px 0 0 99px"
            }}/>
          </div>
          <span style={{color:T.red,fontFamily:T.mono,fontWeight:700}}>₹{d.mm_range.upper.toLocaleString()}</span>
        </div>
        <div style={{fontSize:10,color:T.sub}}>{d.mm_range.interpretation}</div>
      </Panel>

      {/* OI Chart */}
      <Panel style={{padding:16}}>
        <Label>CE vs PE OI BY STRIKE (Lakhs)</Label>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={strikeChartData} barGap={1}>
            <XAxis dataKey="name" tick={{fill:T.muted,fontSize:9,fontFamily:T.mono}} axisLine={false} tickLine={false}/>
            <YAxis tick={{fill:T.muted,fontSize:9,fontFamily:T.mono}} axisLine={false} tickLine={false}/>
            <Tooltip contentStyle={{background:T.bg2,border:`1px solid ${T.border2}`,borderRadius:6,fontSize:10}}/>
            <Bar dataKey="pe" name="PE OI" fill={T.green} fillOpacity={0.8} radius={[3,3,0,0]}/>
            <Bar dataKey="ce" name="CE OI" fill={T.red}   fillOpacity={0.8} radius={[3,3,0,0]}/>
            <ReferenceLine x={d.spot.toString()} stroke={T.amber} strokeDasharray="4 2" label={{value:"SPOT",fill:T.amber,fontSize:9}}/>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {/* Support / Resistance */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
        <Panel style={{padding:16}}>
          <Label>PE OI SUPPORT LEVELS</Label>
          {d.support_levels.map((s,i)=>(
            <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8,padding:"6px 8px",background:`${T.green}08`,borderRadius:6}}>
              <div style={{display:"flex",gap:8,alignItems:"center"}}>
                <div style={{width:18,height:18,borderRadius:"50%",background:`${T.green}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,color:T.green,fontWeight:700}}>{i+1}</div>
                <span style={{fontSize:14,fontWeight:700,color:T.green,fontFamily:T.mono}}>₹{s.strike.toLocaleString()}</span>
              </div>
              <div style={{textAlign:"right"}}>
                <div style={{fontSize:10,color:T.text,fontFamily:T.mono}}>{(s.pe_oi/1e5).toFixed(1)}L OI</div>
                <div style={{fontSize:9,color:T.muted}}>IV {s.pe_iv}%</div>
              </div>
            </div>
          ))}
        </Panel>
        <Panel style={{padding:16}}>
          <Label>CE OI RESISTANCE LEVELS</Label>
          {d.resistance_levels.map((s,i)=>(
            <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8,padding:"6px 8px",background:`${T.red}08`,borderRadius:6}}>
              <div style={{display:"flex",gap:8,alignItems:"center"}}>
                <div style={{width:18,height:18,borderRadius:"50%",background:`${T.red}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,color:T.red,fontWeight:700}}>{i+1}</div>
                <span style={{fontSize:14,fontWeight:700,color:T.red,fontFamily:T.mono}}>₹{s.strike.toLocaleString()}</span>
              </div>
              <div style={{textAlign:"right"}}>
                <div style={{fontSize:10,color:T.text,fontFamily:T.mono}}>{(s.ce_oi/1e5).toFixed(1)}L OI</div>
                <div style={{fontSize:9,color:T.muted}}>IV {s.ce_iv}%</div>
              </div>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════
   ENSEMBLE SCREEN
═══════════════════════════════════ */
function EnsembleScreen() {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div>
        <div style={{fontSize:20,fontWeight:900,color:T.text}}>Strategy Ensemble Voting</div>
        <div style={{fontSize:11,color:T.muted,marginTop:2}}>Stocks where multiple strategies agree simultaneously — highest edge</div>
      </div>

      {MOCK_ENSEMBLE.map((e,i)=>{
        const gradeColor = e.grade==="A"?T.green:e.grade==="B"?T.amber:T.red;
        const voteData   = Object.entries(e.votes).map(([s,v])=>({strategy:s.replace(/_/g," ").slice(0,12),score:v,color:STRATEGY_COLORS[s]||T.muted}));
        return (
          <Panel key={i} style={{borderTop:`3px solid ${gradeColor}`}}>
            <div style={{padding:"14px 16px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
                <div>
                  <div style={{display:"flex",gap:10,alignItems:"center"}}>
                    <span style={{fontSize:20,fontWeight:900,color:T.text}}>{e.stock}</span>
                    <div style={{background:gradeColor,color:"#000",borderRadius:6,padding:"3px 10px",fontSize:12,fontWeight:900,fontFamily:T.mono}}>GRADE {e.grade}</div>
                    <Tag color={T.green}>{e.direction}</Tag>
                  </div>
                  <div style={{fontSize:10,color:T.muted,marginTop:4}}>{e.strategies_agree} strategies agree: {e.strategies_fired.map(s=>s.replace(/_/g," ")).join(" · ")}</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontSize:36,fontWeight:900,color:gradeColor,fontFamily:T.mono,lineHeight:1}}>{e.final_score}</div>
                  <div style={{fontSize:9,color:T.muted}}>ENSEMBLE SCORE</div>
                  <div style={{fontSize:10,color:T.amber,marginTop:2}}>{e.confidence}</div>
                </div>
              </div>

              {/* Vote bars */}
              <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:8}}>
                {voteData.map((v,j)=>(
                  <div key={j}>
                    <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
                      <span style={{fontSize:9,color:T.muted,fontFamily:T.mono}}>{v.strategy}</span>
                      <span style={{fontSize:10,fontWeight:700,color:v.color,fontFamily:T.mono}}>{v.score}</span>
                    </div>
                    <Bar2 value={v.score} max={10} color={v.color} h={4}/>
                  </div>
                ))}
              </div>
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════
   INSTITUTIONAL FLOW SCREEN
═══════════════════════════════════ */
function InstitutionalScreen() {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div style={{fontSize:20,fontWeight:900,color:T.text}}>Institutional Flow Intelligence</div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
        {/* Promoter Holdings */}
        <Panel style={{padding:16}}>
          <Label>PROMOTER SHAREHOLDING CHANGES</Label>
          <div style={{fontSize:10,color:T.sub,marginBottom:12}}>Quarterly NSE data — strongest long-term signal</div>
          {MOCK_PROMOTER.map((p,i)=>{
            const isUp = p.change_pct > 0;
            return (
              <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10,padding:"8px 10px",background:isUp?`${T.green}08`:`${T.red}08`,borderRadius:8}}>
                <div>
                  <div style={{fontSize:13,fontWeight:700,color:T.text}}>{p.stock}</div>
                  <div style={{fontSize:9,color:T.muted}}>{p.quarter} · {p.promoter_pct}%</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontSize:16,fontWeight:900,color:isUp?T.green:T.red,fontFamily:T.mono}}>{isUp?"+":""}{p.change_pct}%</div>
                  <Tag color={isUp?T.green:T.red} bg={isUp?T.greenD:T.redD}>{p.signal.replace(/_/g," ")}</Tag>
                </div>
              </div>
            );
          })}
        </Panel>

        {/* Bulk/Block Deals */}
        <Panel style={{padding:16}}>
          <Label>BULK / BLOCK DEALS</Label>
          <div style={{fontSize:10,color:T.sub,marginBottom:12}}>Actual completed institutional transactions</div>
          {MOCK_BULK.map((d,i)=>{
            const isBuy = d.action==="BUY";
            return (
              <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10,padding:"8px 10px",background:isBuy?`${T.green}08`:`${T.red}08`,borderRadius:8,borderLeft:`2px solid ${isBuy?T.green:T.red}`}}>
                <div>
                  <div style={{display:"flex",gap:6,alignItems:"center"}}>
                    <span style={{fontSize:13,fontWeight:700,color:T.text}}>{d.stock}</span>
                    <Tag color={T.muted}>{d.deal_type}</Tag>
                  </div>
                  <div style={{fontSize:9,color:T.muted,marginTop:2}}>{d.client}</div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontSize:14,fontWeight:800,color:isBuy?T.green:T.red,fontFamily:T.mono}}>{isBuy?"BUY":"SELL"} ₹{d.value_cr}Cr</div>
                  <div style={{fontSize:9,color:T.muted}}>@ ₹{d.price}</div>
                </div>
              </div>
            );
          })}
        </Panel>
      </div>

      {/* Regime + sizing */}
      <Panel style={{padding:16}}>
        <Label>ADAPTIVE REGIME CONTEXT</Label>
        <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
          {[
            ["VIX",MOCK_REGIME.vix.toString(),T.amber,"India VIX"],
            ["REGIME",MOCK_REGIME.regime,T.green,"Market State"],
            ["SIZE ×",MOCK_REGIME.size_mult.toString(),T.blue,"Position Mult"],
            ["STOP ×",MOCK_REGIME.stop_mult.toString(),T.orange,"Stop Mult"],
            ["MIN CV",MOCK_REGIME.min_conviction.toString(),T.purple,"Min Conviction"],
          ].map(([l,v,c,sub])=>(
            <div key={l} style={{background:T.bg1,borderRadius:10,padding:12,textAlign:"center"}}>
              <div style={{fontSize:9,color:T.muted,fontFamily:T.mono,marginBottom:4}}>{l}</div>
              <div style={{fontSize:18,fontWeight:900,color:c,fontFamily:T.mono}}>{v}</div>
              <div style={{fontSize:8,color:T.sub,marginTop:2}}>{sub}</div>
            </div>
          ))}
        </div>
        {MOCK_REGIME.signals.map((s,i)=>(
          <div key={i} style={{marginTop:10,background:`${T.blue}10`,border:`1px solid ${T.blue}30`,borderRadius:6,padding:"8px 12px",fontSize:11,color:T.blue}}>💡 {s}</div>
        ))}
      </Panel>
    </div>
  );
}

/* ═══════════════════════════════════
   ROOT APP
═══════════════════════════════════ */
const TABS = [
  {id:"options-scanner",  label:"Options Scanner",   icon:"🔍"},
  {id:"multi-strike",     label:"Multi-Strike OI",   icon:"📊"},
  {id:"ensemble",         label:"Ensemble Votes",    icon:"🗳️"},
  {id:"institutional",    label:"Institutional",     icon:"🏦"},
];

export default function App() {
  const [tab, setTab] = useState("options-scanner");

  return (
    <div style={{minHeight:"100vh",background:T.bg0,fontFamily:T.sans,color:T.text}}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600;700;900&display=swap');*{box-sizing:border-box;margin:0;padding:0}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:${T.border2};border-radius:2px}`}</style>

      {/* Header */}
      <div style={{borderBottom:`1px solid ${T.border2}`,padding:"0 24px",display:"flex",alignItems:"center",justifyContent:"space-between",height:52,background:T.bg1}}>
        <div style={{display:"flex",alignItems:"center",gap:16}}>
          <div>
            <span style={{fontSize:16,fontWeight:900,color:T.amber,fontFamily:T.mono}}>NSE</span>
            <span style={{fontSize:16,fontWeight:900,color:T.text,fontFamily:T.mono}}>·AI</span>
            <span style={{fontSize:10,color:T.muted,marginLeft:8,letterSpacing:2,fontFamily:T.mono}}>v7.0 ENTERPRISE</span>
          </div>
          <div style={{width:1,height:20,background:T.border2}}/>
          <nav style={{display:"flex"}}>
            {TABS.map(t=>(
              <button key={t.id} onClick={()=>setTab(t.id)} style={{
                background:"none",border:"none",cursor:"pointer",fontFamily:T.sans,
                color:tab===t.id?T.amber:T.muted,fontWeight:tab===t.id?700:400,
                fontSize:12,padding:"0 14px",height:52,
                borderBottom:tab===t.id?`2px solid ${T.amber}`:"2px solid transparent",
                display:"flex",alignItems:"center",gap:6,transition:"all 0.2s",
              }}><span>{t.icon}</span>{t.label}</button>
            ))}
          </nav>
        </div>
        <div style={{display:"flex",gap:16,alignItems:"center",fontSize:11}}>
          <span style={{color:T.green,fontFamily:T.mono}}>● LIVE</span>
          <span style={{color:T.muted}}>NIFTY <b style={{color:T.text}}>23,287</b> <span style={{color:T.green}}>+0.82%</span></span>
          <span style={{color:T.muted}}>VIX <b style={{color:T.amber}}>14.32</b></span>
          <div style={{background:`${T.green}20`,border:`1px solid ${T.green}40`,color:T.green,borderRadius:6,padding:"3px 10px",fontSize:10,fontWeight:700,fontFamily:T.mono}}>NORMAL REGIME</div>
        </div>
      </div>

      <div style={{padding:24,maxWidth:1400,margin:"0 auto"}}>
        {tab==="options-scanner" && <OptionsScannerScreen/>}
        {tab==="multi-strike"   && <MultiStrikeScreen/>}
        {tab==="ensemble"       && <EnsembleScreen/>}
        {tab==="institutional"  && <InstitutionalScreen/>}
      </div>
    </div>
  );
}
