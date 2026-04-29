// ═══════════════════════════════════════════════════════════════════
// NSE AI TRADING — ENTERPRISE ANDROID APP v7.0
// New screens + enterprise UI upgrade
//
// New files:
//   models/EnterpriseModels.kt      — new data classes
//   network/EnterpriseApiService.kt — new endpoints
//   ui/screens/OptionsScannerScreen.kt
//   ui/screens/MultiStrikeScreen.kt
//   ui/screens/EnsembleScreen.kt
//   ui/screens/InstitutionalScreen.kt
//   ui/theme/EnterpriseTheme.kt     — upgraded design system
//   Updated MainActivity.kt          — 8-tab nav
// ═══════════════════════════════════════════════════════════════════


// ─────────────────────────────────────────────────────────────────
// ui/theme/EnterpriseTheme.kt — Full design system
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.*
import androidx.compose.ui.unit.sp

// ── Colors ──────────────────────────────────────────────────────
val Bg0     = Color(0xFF020817)
val Bg1     = Color(0xFF050D1A)
val Bg2     = Color(0xFF080E1C)
val Border1 = Color(0xFF0F1E35)
val Border2 = Color(0xFF1A2F50)

val Amber   = Color(0xFFF59E0B)
val AmberD  = Color(0xFF92400E)
val TGreen  = Color(0xFF00D4A0)
val GreenD  = Color(0xFF003D2E)
val TRed    = Color(0xFFFF4757)
val RedD    = Color(0xFF3D0A10)
val TBlue   = Color(0xFF3B82F6)
val BlueD   = Color(0xFF0A1F4A)
val Purple  = Color(0xFF8B5CF6)
val PurpleD = Color(0xFF2E1065)
val Orange  = Color(0xFFF97316)
val Cyan    = Color(0xFF06B6D4)
val TextMain= Color(0xFFE2E8F0)
val TextMuted=Color(0xFF475569)
val TextSub = Color(0xFF334155)

val Mono = FontFamily.Monospace

private val EnterpriseColors = darkColorScheme(
    primary         = Amber,
    onPrimary       = Color.Black,
    secondary       = TGreen,
    onSecondary     = Color.Black,
    background      = Bg0,
    onBackground    = TextMain,
    surface         = Bg2,
    onSurface       = TextMain,
    surfaceVariant  = Border2,
    outline         = Border2,
    error           = TRed,
    tertiary        = Purple,
)

@Composable
fun TradingTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = EnterpriseColors, content = content)
}

fun stratColor(strategy: String) = when (strategy) {
    "EMA_TREND_FOLLOW"  -> Amber
    "BB_SQUEEZE_BREAK"  -> TBlue
    "RSI_DIVERGENCE"    -> TGreen
    "VWAP_MOMENTUM"     -> Purple
    "ADX_BREAKOUT"      -> Orange
    "STOCH_REVERSAL"    -> TRed
    else                -> TextMuted
}


// ─────────────────────────────────────────────────────────────────
// models/EnterpriseModels.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.models

import com.google.gson.annotations.SerializedName

// Options Scanner
data class OptionsSignal(
    val id: Int,
    val stock: String,
    val strike: Double,
    @SerializedName("option_type")  val optionType: String,
    @SerializedName("signal_type")  val signalType: String,
    val direction: String,
    val confidence: Double,
    val oi: Long,
    @SerializedName("oi_change")     val oiChange: Long,
    @SerializedName("oi_change_pct") val oiChangePct: Double,
    val iv: Double,
    val ltp: Double,
    val spot: Double,
    val rationale: String,
    @SerializedName("scanned_at")   val scannedAt: String
)

data class ScannerStatus(
    val running: Boolean,
    @SerializedName("latest_signals") val latestSignals: Int,
    @SerializedName("last_scan")      val lastScan: String?
)

// Multi-Strike
data class MultiStrikeAnalysis(
    val symbol: String,
    val spot: Double,
    val expiry: String,
    @SerializedName("aggregate_pcr")    val aggregatePcr: AggregatePcr,
    @SerializedName("max_pain")         val maxPain: MaxPain,
    @SerializedName("mm_range")         val mmRange: MMRange,
    val skew: SkewData,
    val bias: String,
    val summary: String,
    @SerializedName("support_levels")    val supportLevels: List<OILevel>,
    @SerializedName("resistance_levels") val resistanceLevels: List<OILevel>,
    @SerializedName("top_strikes")       val topStrikes: List<StrikeRow>,
    @SerializedName("pcr_trend")         val pcrTrend: List<PcrPoint>
)

data class AggregatePcr(
    val pcr: Double,
    @SerializedName("total_ce_oi") val totalCeOi: Long,
    @SerializedName("total_pe_oi") val totalPeOi: Long,
    val bias: String
)

data class MaxPain(
    @SerializedName("max_pain_strike") val strike: Int,
    @SerializedName("zone_low")        val zoneLow: Int,
    @SerializedName("zone_high")       val zoneHigh: Int,
    val interpretation: String
)

data class MMRange(
    val lower: Int, val upper: Int,
    @SerializedName("width_pct")          val widthPct: Double,
    @SerializedName("spot_in_range")      val spotInRange: Boolean,
    @SerializedName("spot_position_pct")  val spotPositionPct: Double,
    val interpretation: String
)

data class SkewData(
    @SerializedName("otm_put_iv")  val otmPutIv: Double,
    @SerializedName("otm_call_iv") val otmCallIv: Double,
    val skew: Double,
    val signal: String
)

data class OILevel(
    val strike: Int,
    @SerializedName("pe_oi") val peOi: Long?,
    @SerializedName("pe_iv") val peIv: Double?,
    @SerializedName("ce_oi") val ceOi: Long?,
    @SerializedName("ce_iv") val ceIv: Double?,
    val label: String
)

data class StrikeRow(
    val strike: Int, val moneyness: Double,
    @SerializedName("ce_oi") val ceOi: Long,
    @SerializedName("pe_oi") val peOi: Long,
    val pcr: Double,
    @SerializedName("ce_iv") val ceIv: Double,
    @SerializedName("pe_iv") val peIv: Double,
    @SerializedName("total_oi") val totalOi: Long
)

data class PcrPoint(val pcr: Double, val time: String)

// Ensemble
data class EnsembleResult(
    val stock: String,
    @SerializedName("final_score")       val finalScore: Double,
    val confidence: String,
    @SerializedName("ensemble_grade")    val grade: String,
    val direction: String,
    @SerializedName("strategies_agree")  val strategiesAgree: Int,
    @SerializedName("strategies_fired")  val strategiesFired: List<String>,
    val votes: Map<String, Double>,
    val rationale: String
)

// Institutional
data class PromoterSignal(
    val stock: String,
    val quarter: String,
    @SerializedName("promoter_pct") val promoterPct: Double,
    @SerializedName("prev_pct")     val prevPct: Double,
    @SerializedName("change_pct")   val changePct: Double,
    val signal: String,
    val direction: String,
    val confidence: Double,
    val rationale: String
)

data class BulkDeal(
    val stock: String,
    val client: String,
    @SerializedName("deal_type") val dealType: String,
    val action: String,
    val qty: Long,
    val price: Double,
    @SerializedName("value_cr")  val valueCr: Double,
    @SerializedName("deal_date") val dealDate: String,
    val signal: String,
    val direction: String,
    val rationale: String
)


// ─────────────────────────────────────────────────────────────────
// network/EnterpriseApiService.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.network

import com.trading.ai.models.*
import retrofit2.http.*

interface EnterpriseApiService {
    // Options Scanner
    @GET("options-scanner/signals")
    suspend fun getOptionsSignals(
        @Query("min_conf") minConf: Float = 6f,
        @Query("direction") direction: String? = null,
        @Query("signal_type") signalType: String? = null,
        @Query("limit") limit: Int = 50
    ): List<OptionsSignal>

    @POST("options-scanner/start")
    suspend fun startScanner(): Map<String, Any>

    @GET("options-scanner/status")
    suspend fun getScannerStatus(): ScannerStatus

    @POST("options-scanner/scan")
    suspend fun runScan(): List<OptionsSignal>

    // Multi-Strike
    @GET("multi-strike/{symbol}")
    suspend fun getMultiStrike(@Path("symbol") symbol: String): MultiStrikeAnalysis

    // Ensemble
    @GET("ensemble/history")
    suspend fun getEnsembleHistory(@Query("limit") limit: Int = 20): List<EnsembleResult>

    // Institutional
    @GET("promoter/signals")
    suspend fun getPromoterSignals(
        @Query("direction") direction: String? = null,
        @Query("min_change") minChange: Float = 0.5f
    ): List<PromoterSignal>

    @POST("promoter/fetch")
    suspend fun fetchPromoterData(): Map<String, Any>

    @GET("bulk-deals")
    suspend fun getBulkDeals(@Query("days") days: Int = 30): List<BulkDeal>

    @POST("bulk-deals/fetch")
    suspend fun fetchBulkDeals(): List<BulkDeal>

    // Adaptive Sizing
    @POST("adaptive-size")
    suspend fun getAdaptiveSize(@Body request: Map<String, Any>): Map<String, Any>
}


// ─────────────────────────────────────────────────────────────────
// ui/screens/OptionsScannerScreen.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.OptionsSignal
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.EnterpriseViewModel

@Composable
fun OptionsScannerScreen(vm: EnterpriseViewModel) {
    val signals by vm.optionsSignals.collectAsState()
    val loading by vm.isLoading.collectAsState()
    var filter  by remember { mutableStateOf("ALL") }

    LaunchedEffect(Unit) { vm.loadOptionsSignals() }

    val filtered = when (filter) {
        "BULLISH"   -> signals.filter { it.direction == "BULLISH" }
        "BEARISH"   -> signals.filter { it.direction == "BEARISH" }
        "OI_SPIKE"  -> signals.filter { it.signalType == "OI_SPIKE" }
        "GAMMA"     -> signals.filter { it.signalType == "GAMMA_SQUEEZE" }
        else        -> signals
    }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(Bg0),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("Options Scanner", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                    Text("Unusual activity across F&O stocks", fontSize = 10.sp, color = TextMuted)
                }
                Button(onClick = { vm.runOptionsScan() }, colors = ButtonDefaults.buttonColors(containerColor = TGreen), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 7.dp)) {
                    Text("⟳ SCAN", fontSize = 11.sp, fontFamily = Mono, fontWeight = FontWeight.Bold, color = Bg0)
                }
            }
        }

        // Filter chips
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf("ALL","BULLISH","BEARISH","OI_SPIKE","GAMMA").forEach { f ->
                    FilterChip(selected = filter == f, onClick = { filter = f },
                        label = { Text(f.replace("_"," "), fontSize = 10.sp, fontFamily = Mono) },
                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Amber, selectedLabelColor = Bg0))
                }
            }
        }

        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        items(filtered) { s -> OptionsSignalCard(s) }

        if (!loading && filtered.isEmpty()) {
            item { Box(Modifier.fillMaxWidth().padding(32.dp), Alignment.Center) { Text("No signals. Tap SCAN to run.", color = TextMuted) } }
        }
    }
}

@Composable
fun OptionsSignalCard(s: OptionsSignal) {
    val (accent, icon) = when (s.signalType) {
        "PUT_WRITING"   -> TGreen  to "🟢"
        "CALL_WRITING"  -> TRed    to "🔴"
        "OI_SPIKE"      -> Amber   to "⚡"
        "GAMMA_SQUEEZE" -> Purple  to "💥"
        "STRADDLE_BUY"  -> Cyan    to "⚖️"
        "IV_EXPANSION"  -> Orange  to "📈"
        else            -> TextMuted to "○"
    }
    val dirColor = when (s.direction) {
        "BULLISH" -> TGreen; "BEARISH" -> TRed; else -> Amber
    }

    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, accent.copy(alpha = 0.4f))) {
        Box(modifier = Modifier.height(3.dp).fillMaxWidth().background(accent))
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(icon, fontSize = 18.sp)
                        Text(s.stock, fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                        BadgeChip(s.signalType.replace("_"," "), accent)
                        BadgeChip(s.direction, dirColor)
                    }
                    Text("Strike ₹${s.strike.toInt().toLocale()} · ${s.optionType} · IV ${s.iv}%",
                         fontSize = 10.sp, color = TextMuted, fontFamily = Mono)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(String.format("%.1f", s.confidence), fontSize = 28.sp, fontWeight = FontWeight.Black, color = accent, fontFamily = Mono)
                    Text("CONFIDENCE", fontSize = 8.sp, color = TextMuted, fontFamily = Mono)
                }
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(
                    Triple("OI", "${String.format("%.1f",s.oi/1e5f)}L", TextMain),
                    Triple("OI Δ", "${if(s.oiChange>0)"+" else ""}${String.format("%.1f",s.oiChange/1e5f)}L", if(s.oiChange>0) TGreen else TRed),
                    Triple("OI %", "${if(s.oiChangePct>0)"+" else ""}${String.format("%.1f",s.oiChangePct)}%", if(s.oiChangePct>0) TGreen else TRed),
                    Triple("LTP", "₹${s.ltp}", Amber),
                ).forEach { (l,v,c) -> MetricBox(l, v, c, Modifier.weight(1f)) }
            }

            Text(s.rationale, fontSize = 11.sp, color = TextSub, lineHeight = 16.sp,
                 modifier = Modifier.padding(start = 8.dp).run { this })
        }
    }
}


// ─────────────────────────────────────────────────────────────────
// ui/screens/MultiStrikeScreen.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.MultiStrikeAnalysis
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.EnterpriseViewModel

@Composable
fun MultiStrikeScreen(vm: EnterpriseViewModel) {
    val data    by vm.multiStrike.collectAsState()
    val loading by vm.isLoading.collectAsState()
    var symbol  by remember { mutableStateOf("NIFTY") }

    LaunchedEffect(symbol) { vm.loadMultiStrike(symbol) }

    LazyColumn(modifier = Modifier.fillMaxSize().background(Bg0), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("Multi-Strike OI Analysis", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                    Text("Strike-level PCR, MM range, support/resistance", fontSize = 10.sp, color = TextMuted)
                }
                // Symbol selector
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("NIFTY","BANKNIFTY").forEach { s ->
                        FilterChip(selected = symbol == s, onClick = { symbol = s },
                            label = { Text(s, fontSize = 10.sp, fontFamily = Mono) },
                            colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Amber, selectedLabelColor = Bg0))
                    }
                }
            }
        }

        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        data?.let { d ->
            // PCR + Bias
            item {
                val biasColor = when (d.bias) { "BULLISH" -> TGreen; "BEARISH" -> TRed; else -> Amber }
                Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, Border2)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Column {
                                Text("PCR", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                                Text(d.aggregatePcr.pcr.toString(), fontSize = 48.sp, fontWeight = FontWeight.Black, color = biasColor, fontFamily = Mono)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                BadgeChip(d.bias, biasColor)
                                Spacer(Modifier.height(4.dp))
                                Text("CE ${String.format("%.1f",d.aggregatePcr.totalCeOi/1e6f)}M", fontSize = 10.sp, color = TRed, fontFamily = Mono)
                                Text("PE ${String.format("%.1f",d.aggregatePcr.totalPeOi/1e6f)}M", fontSize = 10.sp, color = TGreen, fontFamily = Mono)
                            }
                        }
                        LinearProgressIndicator(progress = (d.aggregatePcr.pcr / 2f).toFloat().coerceIn(0f,1f),
                            modifier = Modifier.fillMaxWidth(), color = biasColor, trackColor = Border2)
                    }
                }
            }

            // Max Pain + MM Range
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Card(modifier = Modifier.weight(1f), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, Border2)) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("MAX PAIN", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                            Text("₹${d.maxPain.strike.toLocale()}", fontSize = 24.sp, fontWeight = FontWeight.Black, color = Amber, fontFamily = Mono)
                            Text("Zone: ₹${d.maxPain.zoneLow.toLocale()} – ₹${d.maxPain.zoneHigh.toLocale()}", fontSize = 9.sp, color = TextMuted, fontFamily = Mono)
                        }
                    }
                    Card(modifier = Modifier.weight(1f), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, Border2)) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("SKEW", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                            Text("+${d.skew.skew}", fontSize = 24.sp, fontWeight = FontWeight.Black, color = TRed, fontFamily = Mono)
                            Text(d.skew.signal.substringBefore("—").trim(), fontSize = 9.sp, color = TextMuted)
                        }
                    }
                }
            }

            // MM Range
            item {
                Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, Border2)) {
                    Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("MM EXPECTED RANGE", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("₹${d.mmRange.lower.toLocale()}", color = TGreen, fontWeight = FontWeight.Black, fontFamily = Mono)
                            BadgeChip(if (d.mmRange.spotInRange) "SPOT INSIDE" else "SPOT OUTSIDE", if (d.mmRange.spotInRange) TGreen else TRed)
                            Text("₹${d.mmRange.upper.toLocale()}", color = TRed, fontWeight = FontWeight.Black, fontFamily = Mono)
                        }
                        LinearProgressIndicator(progress = (d.mmRange.spotPositionPct / 100f).toFloat(), modifier = Modifier.fillMaxWidth(), color = Amber, trackColor = Border2)
                        Text(d.mmRange.interpretation, fontSize = 10.sp, color = TextSub, lineHeight = 15.sp)
                    }
                }
            }

            // Support / Resistance
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("PE OI SUPPORT", fontSize = 9.sp, color = TGreen, fontFamily = Mono, letterSpacing = 1.sp)
                        d.supportLevels.take(4).forEachIndexed { i, s ->
                            OILevelRow(i+1, s.strike, s.peOi, s.peIv, TGreen)
                        }
                    }
                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("CE OI RESISTANCE", fontSize = 9.sp, color = TRed, fontFamily = Mono, letterSpacing = 1.sp)
                        d.resistanceLevels.take(4).forEachIndexed { i, s ->
                            OILevelRow(i+1, s.strike, s.ceOi, s.ceIv, TRed)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun OILevelRow(rank: Int, strike: Int, oi: Long?, iv: Double?, color: androidx.compose.ui.graphics.Color) {
    Row(modifier = Modifier.fillMaxWidth().background(color.copy(0.06f), MaterialTheme.shapes.small).padding(8.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(modifier = Modifier.size(20.dp).background(color.copy(0.2f), MaterialTheme.shapes.extraSmall), contentAlignment = Alignment.Center) {
                Text("$rank", fontSize = 9.sp, color = color, fontWeight = FontWeight.Bold)
            }
            Text("₹${strike.toLocale()}", fontSize = 14.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
        }
        Column(horizontalAlignment = Alignment.End) {
            oi?.let { Text("${String.format("%.1f",it/1e5f)}L OI", fontSize = 10.sp, color = TextMain, fontFamily = Mono) }
            iv?.let { Text("IV ${String.format("%.1f",it)}%", fontSize = 9.sp, color = TextMuted, fontFamily = Mono) }
        }
    }
}


// ─────────────────────────────────────────────────────────────────
// ui/screens/EnsembleScreen.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.EnsembleResult
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.EnterpriseViewModel

@Composable
fun EnsembleScreen(vm: EnterpriseViewModel) {
    val ensemble by vm.ensembleResults.collectAsState()
    val loading  by vm.isLoading.collectAsState()

    LaunchedEffect(Unit) { vm.loadEnsemble() }

    LazyColumn(modifier = Modifier.fillMaxSize().background(Bg0), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("Ensemble Voting", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
            Spacer(Modifier.height(2.dp))
            Text("Stocks where 3+ strategies agree — highest probability signals", fontSize = 10.sp, color = TextMuted)
        }
        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }
        items(ensemble) { e -> EnsembleCard(e) }
    }
}

@Composable
fun EnsembleCard(e: EnsembleResult) {
    val gradeColor = when (e.grade) { "A" -> TGreen; "B" -> Amber; else -> TRed }
    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, Border2)) {
        Box(modifier = Modifier.height(3.dp).fillMaxWidth().background(gradeColor))
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(e.stock, fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                        Box(modifier = Modifier.background(gradeColor, MaterialTheme.shapes.small).padding(horizontal = 8.dp, vertical = 3.dp)) {
                            Text("GRADE ${e.grade}", fontSize = 11.sp, fontWeight = FontWeight.Black, color = Bg0, fontFamily = Mono)
                        }
                        BadgeChip(e.direction, TGreen)
                    }
                    Text("${e.strategiesAgree} strategies: ${e.strategiesFired.joinToString(" · "){ it.replace("_"," ").take(10) }}", fontSize = 9.sp, color = TextMuted)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(String.format("%.1f", e.finalScore), fontSize = 32.sp, fontWeight = FontWeight.Black, color = gradeColor, fontFamily = Mono)
                    Text(e.confidence, fontSize = 9.sp, color = Amber, fontFamily = Mono)
                }
            }

            // Vote bars
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                e.votes.entries.sortedByDescending { it.value }.take(4).forEach { (strategy, score) ->
                    val sc = stratColor(strategy)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(strategy.replace("_"," ").take(16), fontSize = 9.sp, color = TextMuted, fontFamily = Mono, modifier = Modifier.width(130.dp))
                        LinearProgressIndicator(progress = (score / 10f).toFloat(), modifier = Modifier.weight(1f).height(4.dp), color = sc, trackColor = Border2)
                        Text(String.format("%.1f", score), fontSize = 10.sp, fontWeight = FontWeight.Bold, color = sc, fontFamily = Mono, modifier = Modifier.width(32.dp).wrapContentWidth(Alignment.End))
                    }
                }
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────
// ui/screens/InstitutionalScreen.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.EnterpriseViewModel

@Composable
fun InstitutionalScreen(vm: EnterpriseViewModel) {
    val promoter by vm.promoterSignals.collectAsState()
    val bulk     by vm.bulkDeals.collectAsState()
    val loading  by vm.isLoading.collectAsState()
    var tab      by remember { mutableStateOf("PROMOTER") }

    LaunchedEffect(Unit) { vm.loadInstitutional() }

    LazyColumn(modifier = Modifier.fillMaxSize().background(Bg0), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Institutional Intelligence", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                Button(onClick = { vm.fetchInstitutionalData() }, colors = ButtonDefaults.buttonColors(containerColor = Amber), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 7.dp)) {
                    Text("⟳ REFRESH", fontSize = 10.sp, fontFamily = Mono, fontWeight = FontWeight.Bold, color = Bg0)
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("PROMOTER","BULK DEALS").forEach { t ->
                    FilterChip(selected = tab == t, onClick = { tab = t },
                        label = { Text(t, fontSize = 10.sp, fontFamily = Mono) },
                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Amber, selectedLabelColor = Bg0))
                }
            }
        }

        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        if (tab == "PROMOTER") {
            items(promoter) { p ->
                val isUp    = p.changePct > 0
                val color   = if (isUp) TGreen else TRed
                Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, color.copy(0.4f))) {
                    Row(modifier = Modifier.padding(14.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column {
                            Text(p.stock, fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain)
                            Text("${p.quarter} · ${p.promoterPct}%", fontSize = 9.sp, color = TextMuted, fontFamily = Mono)
                            Spacer(Modifier.height(4.dp))
                            Text(p.rationale, fontSize = 10.sp, color = TextSub)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text("${if(isUp)"+" else ""}${String.format("%.1f",p.changePct)}%", fontSize = 22.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
                            BadgeChip(p.signal.replace("_"," "), color)
                        }
                    }
                }
            }
        } else {
            items(bulk) { d ->
                val isBuy = d.action == "BUY"
                val color  = if (isBuy) TGreen else TRed
                Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Bg2), border = BorderStroke(1.dp, color.copy(0.3f))) {
                    Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text(d.stock, fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain)
                                BadgeChip(d.dealType, TextMuted)
                            }
                            Text("${d.action} ₹${d.valueCr}Cr", fontSize = 14.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
                        }
                        Text(d.client, fontSize = 11.sp, color = TextMuted)
                        Text("${d.qty.toLocale()} shares @ ₹${d.price} on ${d.dealDate}", fontSize = 10.sp, color = TextSub, fontFamily = Mono)
                    }
                }
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────
// viewmodel/EnterpriseViewModel.kt
// ─────────────────────────────────────────────────────────────────
package com.trading.ai.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trading.ai.models.*
import com.trading.ai.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

class EnterpriseViewModel : ViewModel() {
    private val api = RetrofitClient.enterpriseApi   // add to RetrofitClient

    val optionsSignals   = MutableStateFlow<List<OptionsSignal>>(emptyList())
    val multiStrike      = MutableStateFlow<MultiStrikeAnalysis?>(null)
    val ensembleResults  = MutableStateFlow<List<EnsembleResult>>(emptyList())
    val promoterSignals  = MutableStateFlow<List<PromoterSignal>>(emptyList())
    val bulkDeals        = MutableStateFlow<List<BulkDeal>>(emptyList())
    val isLoading        = MutableStateFlow(false)
    val error            = MutableStateFlow<String?>(null)

    fun loadOptionsSignals(minConf: Float = 6f) = launch { optionsSignals.value = api.getOptionsSignals(minConf = minConf) }
    fun runOptionsScan()                         = launch { optionsSignals.value = api.runScan() }
    fun loadMultiStrike(symbol: String = "NIFTY") = launch { multiStrike.value = api.getMultiStrike(symbol) }
    fun loadEnsemble()                           = launch { ensembleResults.value = api.getEnsembleHistory() }
    fun loadInstitutional()                      = launch { promoterSignals.value = api.getPromoterSignals(); bulkDeals.value = api.getBulkDeals() }
    fun fetchInstitutionalData()                 = launch { api.fetchPromoterData(); api.fetchBulkDeals(); loadInstitutional() }

    private fun launch(block: suspend () -> Unit) {
        viewModelScope.launch {
            isLoading.value = true; error.value = null
            try { block() } catch (e: Exception) { error.value = e.message }
            finally { isLoading.value = false }
        }
    }
}


// ─────────────────────────────────────────────────────────────────
// Helper extensions
// ─────────────────────────────────────────────────────────────────
fun Int.toLocale(): String    = String.format("%,d", this)
fun Long.toLocale(): String   = String.format("%,d", this)


// ─────────────────────────────────────────────────────────────────
// ui/components additions
// ─────────────────────────────────────────────────────────────────

@Composable
fun BadgeChip(text: String, color: Color) {
    Surface(color = color.copy(alpha = 0.15f), shape = MaterialTheme.shapes.extraSmall) {
        Text(text, modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
             color = color, fontSize = 9.sp, fontWeight = FontWeight.Bold, fontFamily = Mono)
    }
}

@Composable
fun MetricBox(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Column(modifier = modifier.background(Bg0, MaterialTheme.shapes.small).padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, fontSize = 8.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
        Spacer(Modifier.height(2.dp))
        Text(value, fontSize = 12.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
    }
}


// ─────────────────────────────────────────────────────────────────
// Updated MainActivity.kt — 8-tab navigation
// ─────────────────────────────────────────────────────────────────
/*
val tabs = listOf(
    Triple("dashboard",        "Market",       Icons.Default.Dashboard),
    Triple("recommendations",  "Picks",        Icons.Default.Star),
    Triple("options-scanner",  "OI Scanner",   Icons.Default.Search),
    Triple("multi-strike",     "Strike OI",    Icons.Default.BarChart),
    Triple("ensemble",         "Ensemble",     Icons.Default.HowToVote),
    Triple("institutional",    "Institutional",Icons.Default.AccountBalance),
    Triple("accuracy",         "Accuracy",     Icons.Default.Analytics),
    Triple("journal",          "Journal",      Icons.Default.MenuBook),
)

NavHost(nav, startDestination = "dashboard") {
    composable("dashboard")       { DashboardScreen(mainVm) }
    composable("recommendations") { RecommendationsScreen(mainVm) }
    composable("options-scanner") { OptionsScannerScreen(enterpriseVm) }
    composable("multi-strike")    { MultiStrikeScreen(enterpriseVm) }
    composable("ensemble")        { EnsembleScreen(enterpriseVm) }
    composable("institutional")   { InstitutionalScreen(enterpriseVm) }
    composable("accuracy")        { AccuracyScreen(mainVm) }
    composable("journal")         { JournalScreen(mainVm) }
}
*/
