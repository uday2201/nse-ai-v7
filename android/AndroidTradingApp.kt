// ═══════════════════════════════════════════════════════════════════════
// NSE AI TRADING — COMPLETE ANDROID APP
// Jetpack Compose · Material 3 · Retrofit · ViewModel
//
// File structure this covers:
//   ui/theme/Theme.kt            Dark trading theme
//   models/Models.kt             All data classes
//   network/ApiService.kt        Retrofit API
//   viewmodel/MainViewModel.kt   Shared state
//   ui/screens/DashboardScreen   Market overview
//   ui/screens/RecommendationsScreen  Picks + levels
//   ui/screens/SmartMoneyScreen  PCR + OI buildups
//   ui/screens/AccuracyScreen    Strategy win rates
//   ui/screens/JournalScreen     Trade history + PnL
//   MainActivity.kt              Nav + Bottom bar
// ═══════════════════════════════════════════════════════════════════════


// ─────────────────────────────────────────────────────────────────────
// build.gradle (app) — dependencies
// ─────────────────────────────────────────────────────────────────────
/*
dependencies {
    implementation("androidx.compose.ui:ui:1.6.7")
    implementation("androidx.compose.material3:material3:1.2.1")
    implementation("androidx.compose.material:material-icons-extended:1.6.7")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.7.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.google.code.gson:gson:2.10.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
*/


// ─────────────────────────────────────────────────────────────────────
// ui/theme/Theme.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Amber    = Color(0xFFF59E0B)
val AmberDim = Color(0xFF78450A)
val TGreen   = Color(0xFF00D4A0)
val GreenDim = Color(0xFF003D2E)
val TRed     = Color(0xFFFF4757)
val RedDim   = Color(0xFF3D0A10)
val TBlue    = Color(0xFF3B82F6)
val BlueDim  = Color(0xFF0A1F4A)
val BgDeep   = Color(0xFF03060F)
val BgPanel  = Color(0xFF080E1C)
val Border   = Color(0xFF1A2540)
val TextMain = Color(0xFFE2E8F0)
val TextMuted= Color(0xFF475569)
val TextSub  = Color(0xFF64748B)

private val DarkColors = darkColorScheme(
    primary          = Amber,
    onPrimary        = Color.Black,
    secondary        = TGreen,
    onSecondary      = Color.Black,
    background       = BgDeep,
    onBackground     = TextMain,
    surface          = BgPanel,
    onSurface        = TextMain,
    surfaceVariant   = Border,
    outline          = Border,
    error            = TRed,
)

@Composable
fun TradingTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = DarkColors, content = content)
}


// ─────────────────────────────────────────────────────────────────────
// models/Models.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.models

import com.google.gson.annotations.SerializedName

data class Recommendation(
    val id: Int,
    val stock: String,
    val strategy: String,
    val direction: String = "LONG",
    val entry: Double,
    val target: Double,
    val stop: Double,
    val rr: Double,
    @SerializedName("duration_days")  val durationDays: Int,
    @SerializedName("expiry_date")    val expiryDate: String,
    val conviction: Double?,
    val reasons: List<String> = emptyList(),
    val status: String,
    val outcome: String?,
    @SerializedName("exit_price")   val exitPrice: Double?,
    @SerializedName("exit_date")    val exitDate: String?,
    @SerializedName("max_price")    val maxPrice: Double?,
    @SerializedName("min_price")    val minPrice: Double?,
    @SerializedName("created_at")   val createdAt: String,
    @SerializedName("last_checked") val lastChecked: String?
)

data class SmartMoneyData(
    val pcr: Double,
    @SerializedName("ce_oi_total") val ceOiTotal: Long,
    @SerializedName("pe_oi_total") val peOiTotal: Long,
    val support: Int,
    val resistance: Int,
    @SerializedName("max_pain")    val maxPain: Int,
    val bias: String,
    val buildups: List<Buildup>
)

data class Buildup(
    val strike: Int,
    val type: String,
    val oi: Long,
    @SerializedName("oi_change") val oiChange: Long,
    val buildup: String
)

data class Insights(
    val date: String,
    @SerializedName("market_bias")     val marketBias: String,
    val pcr: Double,
    val support: Int,
    val resistance: Int,
    @SerializedName("max_pain")        val maxPain: Int,
    val summary: String,
    @SerializedName("top_pick")        val topPick: StockResult?,
    @SerializedName("high_conviction") val highConviction: List<StockResult>
)

data class StockResult(
    val stock: String,
    val price: Double,
    val conviction: Double,
    val grade: String,
    val prediction: String,
    val components: Map<String, Double>,
    @SerializedName("smart_money") val smartMoney: String,
    val pcr: Double,
    val support: Int,
    val resistance: Int
)

data class Trade(
    val id: Int,
    val stock: String,
    val entry: Double?,
    val exit: Double?,
    val quantity: Int = 1,
    val pnl: Double?,
    val conviction: Double?,
    @SerializedName("conviction_grade") val convictionGrade: String?,
    val reason: String?,
    val status: String,
    @SerializedName("entry_time") val entryTime: String?,
    @SerializedName("exit_time")  val exitTime: String?
)

data class JournalAnalytics(
    @SerializedName("total_trades")  val totalTrades: Int,
    @SerializedName("win_rate")      val winRate: Double,
    @SerializedName("total_pnl")     val totalPnl: Double,
    @SerializedName("avg_win")       val avgWin: Double,
    @SerializedName("avg_loss")      val avgLoss: Double,
    @SerializedName("profit_factor") val profitFactor: Double?,
    @SerializedName("best_signal")   val bestSignal: String?,
    @SerializedName("worst_signal")  val worstSignal: String?
)

data class AccuracyReport(
    @SerializedName("total_recommendations") val total: Int,
    val overall: OverallAccuracy,
    @SerializedName("by_strategy")    val byStrategy: List<StrategyAccuracy>,
    @SerializedName("best_strategy")  val bestStrategy: String?,
    @SerializedName("worst_strategy") val worstStrategy: String?
)

data class OverallAccuracy(
    val wins: Int, val losses: Int, val expired: Int,
    @SerializedName("win_rate") val winRate: Double
)

data class StrategyAccuracy(
    val strategy: String, val total: Int, val wins: Int, val losses: Int, val expired: Int,
    @SerializedName("win_rate")          val winRate: Double,
    @SerializedName("avg_rr_offered")    val avgRrOffered: Double,
    @SerializedName("avg_rr_achieved")   val avgRrAchieved: Double,
    @SerializedName("avg_days_to_close") val avgDays: Double,
    @SerializedName("edge_score")        val edgeScore: Double
)

data class ValidationResult(
    val checked: Int,
    @SerializedName("target_hit") val targetHit: Int,
    @SerializedName("stop_hit")   val stopHit: Int,
    val expired: Int,
    @SerializedName("still_open") val stillOpen: Int
)

data class TradeRequest(val stock: String, val entry: Double, val quantity: Int = 1, val reason: String = "")
data class CloseRequest(@SerializedName("exit_price") val exitPrice: Double)


// ─────────────────────────────────────────────────────────────────────
// network/ApiService.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.network

import com.trading.ai.models.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

interface ApiService {
    @GET("insights")             suspend fun getInsights(): Insights
    @GET("smart-money")          suspend fun getSmartMoney(): SmartMoneyData
    @GET("high-conviction")      suspend fun getHighConviction(): List<StockResult>
    @GET("recommendations")      suspend fun getRecommendations(@Query("status") status: String? = null): List<Recommendation>
    @GET("recommendations/open") suspend fun getOpenRecommendations(): List<Recommendation>
    @POST("recommendations/generate") suspend fun generateRecommendations(): List<Recommendation>
    @GET("validate")             suspend fun validateAll(): ValidationResult
    @GET("accuracy")             suspend fun getAccuracy(): AccuracyReport
    @GET("journal")              suspend fun getJournal(): List<Trade>
    @GET("journal/analytics")    suspend fun getAnalytics(): JournalAnalytics
    @POST("trade")               suspend fun addTrade(@Body trade: TradeRequest): Map<String, Any>
    @PUT("trade/{id}/close")     suspend fun closeTrade(@Path("id") id: Int, @Body body: CloseRequest): Map<String, Any>
}

object RetrofitClient {
    private const val BASE_URL = "http://10.0.2.2:8000/"
    val api: ApiService by lazy {
        Retrofit.Builder().baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create()).build()
            .create(ApiService::class.java)
    }
}


// ─────────────────────────────────────────────────────────────────────
// viewmodel/MainViewModel.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trading.ai.models.*
import com.trading.ai.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

class MainViewModel : ViewModel() {
    private val api = RetrofitClient.api

    val insights         = MutableStateFlow<Insights?>(null)
    val smartMoney       = MutableStateFlow<SmartMoneyData?>(null)
    val predictions      = MutableStateFlow<List<StockResult>>(emptyList())
    val recommendations  = MutableStateFlow<List<Recommendation>>(emptyList())
    val accuracy         = MutableStateFlow<AccuracyReport?>(null)
    val journal          = MutableStateFlow<List<Trade>>(emptyList())
    val analytics        = MutableStateFlow<JournalAnalytics?>(null)
    val validationResult = MutableStateFlow<ValidationResult?>(null)
    val isLoading        = MutableStateFlow(false)
    val error            = MutableStateFlow<String?>(null)

    fun loadInsights()         = launch { insights.value         = api.getInsights() }
    fun loadSmartMoney()       = launch { smartMoney.value       = api.getSmartMoney() }
    fun loadPredictions()      = launch { predictions.value      = api.getHighConviction() }
    fun loadRecommendations(s: String? = null) = launch { recommendations.value = api.getRecommendations(s) }
    fun generateRecommendations() = launch { recommendations.value = api.generateRecommendations() }
    fun loadAccuracy()         = launch { accuracy.value         = api.getAccuracy() }
    fun loadJournal()          = launch { journal.value = api.getJournal(); analytics.value = api.getAnalytics() }
    fun validateAll()          = launch { validationResult.value = api.validateAll(); loadRecommendations() }
    fun closeTrade(id: Int, price: Double, onDone: () -> Unit) = launch { api.closeTrade(id, CloseRequest(price)); loadJournal(); onDone() }

    private fun launch(block: suspend () -> Unit) {
        viewModelScope.launch {
            isLoading.value = true; error.value = null
            try { block() } catch (e: Exception) { error.value = e.message }
            finally { isLoading.value = false }
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// ui/components/SharedComponents.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.components

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.ui.theme.*

val Mono = FontFamily.Monospace

@Composable
fun TradingCard(modifier: Modifier = Modifier, accentColor: Color = Border, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier,
        colors   = CardDefaults.cardColors(containerColor = BgPanel),
        shape    = MaterialTheme.shapes.medium,
        border   = BorderStroke(1.dp, Border)
    ) {
        Box(modifier = Modifier.padding(top = 3.dp)) {
            Box(modifier = Modifier.fillMaxWidth().height(3.dp).background(accentColor))
        }
        Column(modifier = Modifier.padding(16.dp), content = content)
    }
}

@Composable
fun SectionLabel(text: String) {
    Text(text, fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.5.sp,
         fontWeight = FontWeight.Bold, modifier = Modifier.padding(bottom = 12.dp))
}

@Composable
fun StatusBadge(status: String) {
    val (color, bg, label) = when (status) {
        "TARGET_HIT" -> Triple(TGreen,  GreenDim, "✓ TARGET HIT")
        "STOP_HIT"   -> Triple(TRed,    RedDim,   "✗ STOP HIT")
        "EXPIRED"    -> Triple(Amber,   AmberDim, "◷ EXPIRED")
        "WIN"        -> Triple(TGreen,  GreenDim, "WIN")
        "LOSS"       -> Triple(TRed,    RedDim,   "LOSS")
        else         -> Triple(TBlue,   BlueDim,  "● OPEN")
    }
    Surface(color = bg, shape = MaterialTheme.shapes.small) {
        Text(label, modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
             color = color, fontSize = 10.sp, fontFamily = Mono, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun PriceBox(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Column(modifier = modifier.background(BgDeep, MaterialTheme.shapes.small).padding(10.dp),
           horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
        Spacer(Modifier.height(3.dp))
        Text(value, fontSize = 14.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
    }
}

@Composable
fun TradingProgressBar(progress: Float, color: Color, modifier: Modifier = Modifier) {
    Box(modifier = modifier.height(5.dp).background(Border, CircleShape).clip(CircleShape)) {
        Box(modifier = Modifier.fillMaxWidth(progress.coerceIn(0f, 1f)).fillMaxHeight()
                .background(color, CircleShape))
    }
}

fun strategyColor(strategy: String): Color = when (strategy) {
    "EMA_TREND_FOLLOW"  -> Color(0xFFF59E0B)
    "BB_SQUEEZE_BREAK"  -> Color(0xFF3B82F6)
    "RSI_DIVERGENCE"    -> Color(0xFF00D4A0)
    "VWAP_MOMENTUM"     -> Color(0xFF8B5CF6)
    "ADX_BREAKOUT"      -> Color(0xFFF97316)
    "STOCH_REVERSAL"    -> Color(0xFFFF4757)
    else                -> TextMuted
}


// ─────────────────────────────────────────────────────────────────────
// ui/screens/DashboardScreen.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.StockResult
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.MainViewModel

@Composable
fun DashboardScreen(vm: MainViewModel) {
    val insights by vm.insights.collectAsState()
    val loading  by vm.isLoading.collectAsState()

    LaunchedEffect(Unit) { vm.loadInsights(); vm.loadPredictions() }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(BgDeep),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("NSE·AI", fontSize = 22.sp, fontWeight = FontWeight.Black, color = Amber, fontFamily = Mono)
                    Text("TRADING TERMINAL", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 2.sp)
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(modifier = Modifier.size(6.dp).background(TGreen, androidx.compose.foundation.shape.CircleShape))
                    Text("LIVE", fontSize = 10.sp, color = TGreen, fontFamily = Mono, fontWeight = FontWeight.Bold)
                }
            }
        }

        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        // Market Bias Hero
        insights?.let { ins ->
            item {
                val biasColor = when (ins.marketBias) { "BULLISH" -> TGreen; "BEARISH" -> TRed; else -> Amber }
                TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = biasColor) {
                    SectionLabel("MARKET INTELLIGENCE")
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column {
                            Text(ins.marketBias, fontSize = 32.sp, fontWeight = FontWeight.Black, color = biasColor, fontFamily = Mono)
                            Spacer(Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                StatusBadge("PCR ${ins.pcr}")
                                // Support/Resistance chips
                            }
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text("${ins.support.toLocaleString()}", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TGreen, fontFamily = Mono)
                            Text("SUPPORT", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                            Spacer(Modifier.height(8.dp))
                            Text("${ins.resistance.toLocaleString()}", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TRed, fontFamily = Mono)
                            Text("RESISTANCE", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(ins.summary, fontSize = 12.sp, color = TextSub, lineHeight = 18.sp,
                         modifier = Modifier.padding(start = 8.dp).background(Color.Transparent).run {
                             this
                         })
                }
            }

            // Stats Row
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    val hc = ins.highConviction
                    val wins  = 0 // would come from journal
                    listOf(
                        Triple("HIGH CV PICKS", "${hc.size}", TGreen),
                        Triple("MAX PAIN", "${ins.maxPain}", Amber),
                        Triple("PCR", "${ins.pcr}", TBlue),
                    ).forEach { (l, v, c) ->
                        TradingCard(modifier = Modifier.weight(1f), accentColor = c) {
                            Text(l, fontSize = 8.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                            Spacer(Modifier.height(4.dp))
                            Text(v, fontSize = 22.sp, fontWeight = FontWeight.Black, color = c, fontFamily = Mono)
                        }
                    }
                }
            }

            // High Conviction Picks
            if (ins.highConviction.isNotEmpty()) {
                item { Text("HIGH CONVICTION PICKS", fontSize = 10.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 2.sp) }
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(ins.highConviction) { stock -> PickCard(stock) }
                    }
                }
            }
        }
    }
}

fun Int.toLocaleString() = String.format("%,d", this)

@Composable
fun PickCard(s: StockResult) {
    val gradeColor = if (s.grade == "HIGH") TGreen else Amber
    TradingCard(modifier = Modifier.width(180.dp), accentColor = gradeColor) {
        Text(s.stock, fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain)
        Text("₹${s.price}", fontSize = 13.sp, color = TextSub, fontFamily = Mono)
        Spacer(Modifier.height(10.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("CV", fontSize = 9.sp, color = TextMuted)
            Text("${s.conviction}/10", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = gradeColor, fontFamily = Mono)
        }
        Spacer(Modifier.height(4.dp))
        TradingProgressBar(progress = (s.conviction / 10f).toFloat(), color = gradeColor, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(10.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("S", fontSize = 8.sp, color = TextMuted)
                Text(s.support.toString(), fontSize = 11.sp, fontWeight = FontWeight.Bold, color = TGreen, fontFamily = Mono)
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("R", fontSize = 8.sp, color = TextMuted)
                Text(s.resistance.toString(), fontSize = 11.sp, fontWeight = FontWeight.Bold, color = TRed, fontFamily = Mono)
            }
            StatusBadge(s.prediction)
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// ui/screens/RecommendationsScreen.kt
// ─────────────────────────────────────────────────────────────────────
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
import com.trading.ai.models.Recommendation
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.MainViewModel

@Composable
fun RecommendationsScreen(vm: MainViewModel) {
    val recos   by vm.recommendations.collectAsState()
    val loading by vm.isLoading.collectAsState()
    val vResult by vm.validationResult.collectAsState()
    var filter  by remember { mutableStateOf("ALL") }

    LaunchedEffect(Unit) { vm.loadRecommendations() }

    val filtered = when (filter) {
        "OPEN" -> recos.filter { it.status == "OPEN" }
        "WIN"  -> recos.filter { it.outcome == "WIN" }
        "LOSS" -> recos.filter { it.outcome in listOf("LOSS","EXPIRED") }
        else   -> recos
    }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(BgDeep),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("RECOMMENDATIONS", fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { vm.generateRecommendations() }, colors = ButtonDefaults.buttonColors(containerColor = Amber), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)) {
                        Text("SCAN", fontSize = 11.sp, fontFamily = Mono, fontWeight = FontWeight.Bold, color = BgDeep)
                    }
                    OutlinedButton(onClick = { vm.validateAll() }, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp), border = BorderStroke(1.dp, TGreen)) {
                        Text("VALIDATE", fontSize = 11.sp, fontFamily = Mono, fontWeight = FontWeight.Bold, color = TGreen)
                    }
                }
            }
        }

        // Validation result
        vResult?.let { v ->
            item {
                Card(colors = CardDefaults.cardColors(containerColor = GreenDim), modifier = Modifier.fillMaxWidth()) {
                    Row(modifier = Modifier.padding(12.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                        listOf("Checked ${v.checked}", "Hits ${v.targetHit}", "Stops ${v.stopHit}", "Open ${v.stillOpen}").forEach {
                            Text(it, fontSize = 11.sp, color = TGreen, fontFamily = Mono)
                        }
                    }
                }
            }
        }

        // Filter chips
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("ALL","OPEN","WIN","LOSS").forEach { f ->
                    FilterChip(
                        selected = filter == f,
                        onClick  = { filter = f },
                        label    = { Text(f, fontSize = 11.sp, fontFamily = Mono) },
                        colors   = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Amber, selectedLabelColor = BgDeep
                        )
                    )
                }
            }
        }

        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }
        items(filtered) { r -> RecoCard(r, vm) }
        if (!loading && filtered.isEmpty()) {
            item {
                Box(modifier = Modifier.fillMaxWidth().padding(48.dp), contentAlignment = Alignment.Center) {
                    Text("No recommendations. Tap SCAN to generate.", color = TextMuted, fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
fun RecoCard(r: Recommendation, vm: MainViewModel) {
    val sc = strategyColor(r.strategy)
    var expanded by remember { mutableStateOf(false) }
    val progress = if (r.target != r.entry && r.maxPrice != null)
        ((r.maxPrice - r.entry) / (r.target - r.entry)).coerceIn(0.0, 1.0).toFloat()
    else 0f

    TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = sc) {
        // Header
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(r.stock, fontSize = 20.sp, fontWeight = FontWeight.Black, color = TextMain)
                Text(r.strategy.replace("_"," "), fontSize = 10.sp, color = sc, fontFamily = Mono, letterSpacing = 0.5.sp)
            }
            Column(horizontalAlignment = Alignment.End) {
                r.conviction?.let { Text(String.format("%.1f",it), fontSize = 22.sp, fontWeight = FontWeight.Black, color = sc, fontFamily = Mono) }
                StatusBadge(r.status)
            }
        }

        Spacer(Modifier.height(12.dp))

        // Price levels grid
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            PriceBox("ENTRY",  "₹${r.entry}",  TBlue,  Modifier.weight(1f))
            PriceBox("TARGET", "₹${r.target}", TGreen, Modifier.weight(1f))
            PriceBox("STOP",   "₹${r.stop}",   TRed,   Modifier.weight(1f))
            PriceBox("RR",     "${r.rr}:1",    Amber,  Modifier.weight(1f))
        }

        Spacer(Modifier.height(10.dp))

        // Duration info
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("${r.durationDays}d hold · exp ${r.expiryDate}", fontSize = 10.sp, color = TextMuted, fontFamily = Mono)
            r.outcome?.takeIf { it != "OPEN" }?.let { StatusBadge(it) }
        }

        // Progress bar for OPEN
        if (r.status == "OPEN" && r.maxPrice != null && progress > 0) {
            Spacer(Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Progress to target", fontSize = 9.sp, color = TextMuted, fontFamily = Mono)
                Text("${(progress*100).toInt()}% · High ₹${r.maxPrice}", fontSize = 9.sp, color = TGreen, fontFamily = Mono)
            }
            Spacer(Modifier.height(3.dp))
            TradingProgressBar(progress = progress, color = sc, modifier = Modifier.fillMaxWidth())
        }

        // Closed result
        if (r.status != "OPEN") {
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                r.exitPrice?.let { Surface(color = if(r.outcome=="WIN") GreenDim else RedDim, shape = MaterialTheme.shapes.small) {
                    Text("Exit ₹$it on ${r.exitDate}", modifier = Modifier.padding(6.dp, 3.dp), fontSize = 10.sp, color = if(r.outcome=="WIN") TGreen else TRed, fontFamily = Mono)
                }}
                r.maxPrice?.let { Surface(color = GreenDim, shape = MaterialTheme.shapes.small) {
                    Text("High ₹$it", modifier = Modifier.padding(6.dp, 3.dp), fontSize = 10.sp, color = TGreen, fontFamily = Mono)
                }}
            }
        }

        // Reasons toggle
        if (r.reasons.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { expanded = !expanded }, contentPadding = PaddingValues(0.dp)) {
                Text(if (expanded) "▲ hide rationale" else "▼ show rationale", fontSize = 11.sp, color = TextSub, fontFamily = Mono)
            }
            if (expanded) {
                Spacer(Modifier.height(6.dp))
                Column(modifier = Modifier.padding(start = 12.dp).background(BgDeep, MaterialTheme.shapes.small).padding(10.dp)) {
                    r.reasons.forEach { reason ->
                        Text("· $reason", fontSize = 11.sp, color = TextSub, lineHeight = 16.sp)
                        Spacer(Modifier.height(4.dp))
                    }
                }
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// ui/screens/SmartMoneyScreen.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.Buildup
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.MainViewModel

@Composable
fun SmartMoneyScreen(vm: MainViewModel) {
    val sm      by vm.smartMoney.collectAsState()
    val loading by vm.isLoading.collectAsState()
    LaunchedEffect(Unit) { vm.loadSmartMoney() }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(BgDeep),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { Text("SMART MONEY", fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain) }
        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        sm?.let { data ->
            // PCR Overview
            item {
                val biasColor = when (data.bias) { "BULLISH" -> TGreen; "BEARISH" -> TRed; else -> Amber }
                TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = biasColor) {
                    SectionLabel("PUT-CALL RATIO ANALYSIS")
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                        Column {
                            Text(data.pcr.toString(), fontSize = 48.sp, fontWeight = FontWeight.Black, color = biasColor, fontFamily = Mono)
                            Text("PUT-CALL RATIO", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(data.bias, fontSize = 20.sp, fontWeight = FontWeight.Black, color = biasColor)
                            Spacer(Modifier.height(4.dp))
                            Text("Max Pain: ${data.maxPain.toLocaleString()}", fontSize = 11.sp, color = TextMuted, fontFamily = Mono)
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    TradingProgressBar(progress = (data.pcr / 2f).toFloat(), color = biasColor, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("0 — BEARISH", fontSize = 9.sp, color = TRed, fontFamily = Mono)
                        Text("1 — NEUTRAL", fontSize = 9.sp, color = Amber, fontFamily = Mono)
                        Text("2 — BULLISH", fontSize = 9.sp, color = TGreen, fontFamily = Mono)
                    }
                }
            }

            // OI Totals
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    PriceBox("CE OI (Total)",    "${String.format("%.1f",data.ceOiTotal/1e6f)}M", TRed,   Modifier.weight(1f))
                    PriceBox("PE OI (Total)",    "${String.format("%.1f",data.peOiTotal/1e6f)}M", TGreen, Modifier.weight(1f))
                }
            }

            // Levels
            item {
                TradingCard(modifier = Modifier.fillMaxWidth()) {
                    SectionLabel("OI-DERIVED KEY LEVELS")
                    listOf(
                        Triple("RESISTANCE", data.resistance, TRed),
                        Triple("MAX PAIN",   data.maxPain,    Amber),
                        Triple("SUPPORT",    data.support,    TGreen),
                    ).forEach { (label, value, color) ->
                        Row(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(label, fontSize = 11.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                            Text(value.toLocaleString(), fontSize = 20.sp, fontWeight = FontWeight.Black, color = color, fontFamily = Mono)
                        }
                        Divider(color = Border, thickness = 1.dp)
                    }
                }
            }

            // Buildups
            item { SectionLabel("STRIKE-LEVEL OI BUILDUPS") }
            items(data.buildups) { b -> BuildupCard(b) }
        }
    }
}

@Composable
fun BuildupCard(b: Buildup) {
    val isBullish = b.buildup in listOf("LONG_BUILDUP", "SHORT_COVER")
    val color     = if (isBullish) TGreen else TRed
    val bg        = if (isBullish) GreenDim else RedDim
    val emoji = mapOf("LONG_BUILDUP" to "🟢", "SHORT_BUILDUP" to "🔴", "SHORT_COVER" to "⬆️", "LONG_UNWIND" to "⬇️")[b.buildup] ?: "○"

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(containerColor = BgPanel),
        border   = BorderStroke(1.dp, color.copy(alpha = 0.3f))
    ) {
        Row(modifier = Modifier.padding(14.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(modifier = Modifier.size(40.dp).background(bg, MaterialTheme.shapes.small), contentAlignment = Alignment.Center) {
                    Text(emoji, fontSize = 18.sp)
                }
                Column {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(b.strike.toLocaleString(), fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain, fontFamily = Mono)
                        Surface(color = if (b.type == "PE") GreenDim else RedDim, shape = MaterialTheme.shapes.extraSmall) {
                            Text(b.type, modifier = Modifier.padding(4.dp, 2.dp), fontSize = 9.sp, fontWeight = FontWeight.Bold, color = if (b.type == "PE") TGreen else TRed, fontFamily = Mono)
                        }
                    }
                    Text(b.buildup.replace("_"," "), fontSize = 11.sp, color = color, fontFamily = Mono, fontWeight = FontWeight.SemiBold)
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("${String.format("%.1f",b.oi/1e5f)}L OI", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = TextMain, fontFamily = Mono)
                val chgStr = if (b.oiChange >= 0) "+${String.format("%.1f",b.oiChange/1e5f)}L" else "${String.format("%.1f",b.oiChange/1e5f)}L"
                Text(chgStr, fontSize = 11.sp, color = if (b.oiChange >= 0) TGreen else TRed, fontFamily = Mono)
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// ui/screens/AccuracyScreen.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.StrategyAccuracy
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.MainViewModel

@Composable
fun AccuracyScreen(vm: MainViewModel) {
    val accuracy by vm.accuracy.collectAsState()
    val loading  by vm.isLoading.collectAsState()
    LaunchedEffect(Unit) { vm.loadAccuracy() }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(BgDeep),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { Text("ACCURACY REPORT", fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain) }
        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }

        accuracy?.let { acc ->
            val ov = acc.overall
            val wc = if (ov.winRate >= 60) TGreen else if (ov.winRate >= 50) Amber else TRed

            // Overall card
            item {
                TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = wc) {
                    SectionLabel("OVERALL PERFORMANCE")
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column {
                            Text("${ov.winRate}%", fontSize = 48.sp, fontWeight = FontWeight.Black, color = wc, fontFamily = Mono)
                            Text("WIN RATE", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            listOf(Triple("WINS",ov.wins.toString(),TGreen), Triple("LOSSES",ov.losses.toString(),TRed), Triple("EXPIRED",ov.expired.toString(),Amber)).forEach { (l,v,c) ->
                                Row(modifier = Modifier.padding(bottom = 2.dp)) {
                                    Text("$l ", fontSize = 10.sp, color = TextMuted, fontFamily = Mono)
                                    Text(v, fontSize = 14.sp, fontWeight = FontWeight.Black, color = c, fontFamily = Mono)
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    TradingProgressBar(progress = (ov.winRate/100f).toFloat(), color = wc, modifier = Modifier.fillMaxWidth())
                    acc.bestStrategy?.let {
                        Spacer(Modifier.height(10.dp))
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("🏆 Best: ${it.replace("_"," ")}", fontSize = 10.sp, color = TGreen)
                            Text("⚠️ Worst: ${acc.worstStrategy?.replace("_"," ")}", fontSize = 10.sp, color = TRed)
                        }
                    }
                }
            }

            item { SectionLabel("STRATEGY BREAKDOWN") }
            items(acc.byStrategy) { s -> StrategyCard(s) }
        }
    }
}

@Composable
fun StrategyCard(s: StrategyAccuracy) {
    val sc = strategyColor(s.strategy)
    val wc = if (s.winRate >= 65) TGreen else if (s.winRate >= 50) Amber else TRed

    TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = sc) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(modifier = Modifier.size(10.dp).background(sc, androidx.compose.foundation.shape.CircleShape))
                Text(s.strategy.replace("_"," "), fontSize = 13.sp, fontWeight = FontWeight.Bold, color = TextMain)
            }
            Text("${s.winRate}%", fontSize = 24.sp, fontWeight = FontWeight.Black, color = wc, fontFamily = Mono)
        }
        Spacer(Modifier.height(8.dp))
        TradingProgressBar(progress = (s.winRate/100f).toFloat(), color = sc, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            listOf(
                Triple("${s.wins}W/${s.losses}L","W/L", TextMain),
                Triple("${s.avgRrOffered}:1", "OFFERED", TBlue),
                Triple("${s.avgRrAchieved}:1","ACHIEVED", Amber),
                Triple("${s.avgDays}d","AVG HOLD", TextMuted),
            ).forEach { (v,l,c) ->
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(v, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = c, fontFamily = Mono)
                    Text(l, fontSize = 8.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                }
            }
        }
        val edgeColor = if (s.edgeScore > 0) TGreen else TRed
        Spacer(Modifier.height(8.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("EDGE SCORE", fontSize = 9.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
            Surface(color = if (s.edgeScore > 0) GreenDim else RedDim, shape = MaterialTheme.shapes.extraSmall) {
                Text("${if(s.edgeScore>0)"+" else ""}${s.edgeScore}", modifier = Modifier.padding(8.dp, 3.dp), fontSize = 12.sp, fontWeight = FontWeight.Bold, color = edgeColor, fontFamily = Mono)
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// ui/screens/JournalScreen.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.trading.ai.models.Trade
import com.trading.ai.ui.components.*
import com.trading.ai.ui.theme.*
import com.trading.ai.viewmodel.MainViewModel

@Composable
fun JournalScreen(vm: MainViewModel) {
    val trades    by vm.journal.collectAsState()
    val analytics by vm.analytics.collectAsState()
    val loading   by vm.isLoading.collectAsState()
    LaunchedEffect(Unit) { vm.loadJournal() }

    LazyColumn(
        modifier            = Modifier.fillMaxSize().background(BgDeep),
        contentPadding      = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item { Text("TRADE JOURNAL", fontSize = 16.sp, fontWeight = FontWeight.Black, color = TextMain) }

        analytics?.let { a ->
            item {
                val pnlColor = if (a.totalPnl >= 0) TGreen else TRed
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    TradingCard(modifier = Modifier.weight(1f), accentColor = pnlColor) {
                        Text("TOTAL P&L", fontSize = 8.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        Spacer(Modifier.height(2.dp))
                        Text("₹${String.format("%,.0f",a.totalPnl)}", fontSize = 18.sp, fontWeight = FontWeight.Black, color = pnlColor, fontFamily = Mono)
                    }
                    TradingCard(modifier = Modifier.weight(1f), accentColor = TGreen) {
                        Text("WIN RATE", fontSize = 8.sp, color = TextMuted, fontFamily = Mono, letterSpacing = 1.sp)
                        Spacer(Modifier.height(2.dp))
                        Text("${a.winRate}%", fontSize = 18.sp, fontWeight = FontWeight.Black, color = TGreen, fontFamily = Mono)
                    }
                }
            }

            item {
                TradingCard(modifier = Modifier.fillMaxWidth()) {
                    SectionLabel("PERFORMANCE METRICS")
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        listOf(
                            Triple("Avg Win",    "₹${a.avgWin}",  TGreen),
                            Triple("Avg Loss",   "₹${a.avgLoss}", TRed),
                            Triple("Profit Factor", "${a.profitFactor ?: "-"}", Amber),
                        ).forEach { (l,v,c) ->
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(v, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = c, fontFamily = Mono)
                                Text(l, fontSize = 9.sp, color = TextMuted)
                            }
                        }
                    }
                    a.bestSignal?.let {
                        Spacer(Modifier.height(10.dp))
                        Text("✅ Best signal: $it  ·  ❌ Worst: ${a.worstSignal}", fontSize = 11.sp, color = TextSub)
                    }
                }
            }
        }

        item { SectionLabel("TRADE HISTORY") }
        if (loading) item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Amber) }
        items(trades) { t -> TradeCard(t, vm) }
    }
}

@Composable
fun TradeCard(t: Trade, vm: MainViewModel) {
    val isOpen   = t.status == "OPEN"
    val pnlColor = when { t.pnl == null -> TBlue; t.pnl >= 0 -> TGreen; else -> TRed }
    var closing  by remember { mutableStateOf(false) }
    var exitInput by remember { mutableStateOf("") }
    val accentColor = if (isOpen) TBlue else if ((t.pnl ?: 0.0) >= 0) TGreen else TRed

    TradingCard(modifier = Modifier.fillMaxWidth(), accentColor = accentColor) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(t.stock, fontSize = 18.sp, fontWeight = FontWeight.Black, color = TextMain)
                Text(t.entryTime ?: "", fontSize = 10.sp, color = TextMuted, fontFamily = Mono)
            }
            StatusBadge(t.status)
        }
        Spacer(Modifier.height(10.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            t.entry?.let { PriceBox("ENTRY", "₹$it", TBlue, Modifier.weight(1f)) }
            Spacer(Modifier.width(6.dp))
            if (t.exit != null) PriceBox("EXIT", "₹${t.exit}", accentColor, Modifier.weight(1f))
            Spacer(Modifier.width(6.dp))
            PriceBox("QTY", "${t.quantity}", TextMuted, Modifier.weight(1f))
            Spacer(Modifier.width(6.dp))
            PriceBox("P&L", if (t.pnl != null) "${if(t.pnl>=0)"+₹" else "-₹"}${Math.abs(t.pnl).toInt()}" else "OPEN", pnlColor, Modifier.weight(1f))
        }
        t.conviction?.let {
            Spacer(Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Conviction: $it (${t.convictionGrade})", fontSize = 10.sp, color = TextMuted)
            }
        }
        t.reason?.takeIf { it.isNotBlank() }?.let {
            Spacer(Modifier.height(4.dp))
            Text("Reason: $it", fontSize = 10.sp, color = TextSub)
        }
        if (isOpen) {
            Spacer(Modifier.height(10.dp))
            if (closing) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = exitInput, onValueChange = { exitInput = it },
                        label = { Text("Exit Price", fontSize = 11.sp) },
                        modifier = Modifier.weight(1f), singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Amber, focusedLabelColor = Amber)
                    )
                    Button(
                        onClick = { exitInput.toDoubleOrNull()?.let { price -> vm.closeTrade(t.id, price) { closing = false } } },
                        colors = ButtonDefaults.buttonColors(containerColor = Amber)
                    ) { Text("CLOSE", color = BgDeep, fontSize = 11.sp, fontFamily = Mono, fontWeight = FontWeight.Bold) }
                }
            } else {
                OutlinedButton(onClick = { closing = true }, border = BorderStroke(1.dp, Amber)) {
                    Text("Close Trade", color = Amber, fontSize = 11.sp, fontFamily = Mono)
                }
            }
        }
    }
}


// ─────────────────────────────────────────────────────────────────────
// MainActivity.kt
// ─────────────────────────────────────────────────────────────────────
package com.trading.ai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.*
import com.trading.ai.ui.screens.*
import com.trading.ai.ui.theme.TradingTheme
import com.trading.ai.viewmodel.MainViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { TradingTheme { TradingApp() } }
    }
}

@Composable
fun TradingApp() {
    val nav = rememberNavController()
    val vm: MainViewModel = viewModel()

    val tabs = listOf(
        Triple("dashboard",       "Market",      Icons.Default.Dashboard),
        Triple("recommendations", "Picks",        Icons.Default.Star),
        Triple("smartmoney",      "Smart Money",  Icons.Default.ShowChart),
        Triple("accuracy",        "Accuracy",     Icons.Default.Analytics),
        Triple("journal",         "Journal",      Icons.Default.MenuBook),
    )

    Scaffold(
        bottomBar = {
            NavigationBar(containerColor = com.trading.ai.ui.theme.BgPanel) {
                val current by nav.currentBackStackEntryAsState()
                tabs.forEach { (route, label, icon) ->
                    NavigationBarItem(
                        selected  = current?.destination?.route == route,
                        onClick   = { nav.navigate(route) { launchSingleTop = true } },
                        icon      = { Icon(icon, label) },
                        label     = { Text(label, fontSize = 9.sp) },
                        colors    = NavigationBarItemDefaults.colors(
                            selectedIconColor      = com.trading.ai.ui.theme.Amber,
                            selectedTextColor      = com.trading.ai.ui.theme.Amber,
                            indicatorColor         = com.trading.ai.ui.theme.AmberDim,
                            unselectedIconColor    = com.trading.ai.ui.theme.TextMuted,
                            unselectedTextColor    = com.trading.ai.ui.theme.TextMuted,
                        )
                    )
                }
            }
        }
    ) { padding ->
        NavHost(nav, startDestination = "dashboard") {
            composable("dashboard")       { DashboardScreen(vm) }
            composable("recommendations") { RecommendationsScreen(vm) }
            composable("smartmoney")      { SmartMoneyScreen(vm) }
            composable("accuracy")        { AccuracyScreen(vm) }
            composable("journal")         { JournalScreen(vm) }
        }
    }
}
