package com.supptrack.vegan

import android.Manifest
import android.app.AlarmManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

private val SagePrimary = Color(0xFF2D6A4F)
private val SageDark = Color(0xFF1B4332)
private val SageLight = Color(0xFF52B788)

class MainActivity : ComponentActivity() {

    private val externalRefreshTick = mutableIntStateOf(0)

    private val dataUpdateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            externalRefreshTick.intValue++
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ReminderScheduler.rescheduleAll(this)
        SupplementWidgetProvider.updateAllWidgets(this)

        ContextCompat.registerReceiver(
            this,
            dataUpdateReceiver,
            IntentFilter(SupplementRepository.ACTION_DATA_UPDATED),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )

        setContent {
            SuppTrackRoot(externalRefreshTick = externalRefreshTick.intValue)
        }
    }

    override fun onResume() {
        super.onResume()
        externalRefreshTick.intValue++
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            unregisterReceiver(dataUpdateReceiver)
        } catch (_: Exception) {}
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SuppTrackRoot(externalRefreshTick: Int) {
    val context = LocalContext.current
    val repo = remember { SupplementRepository(context) }
    val systemDark = isSystemInDarkTheme()

    var darkMode by remember { mutableStateOf(repo.isDarkMode(systemDark)) }
    var selectedTab by remember { mutableIntStateOf(0) }
    var supplements by remember { mutableStateOf(repo.getSupplements()) }
    var logs by remember { mutableStateOf(repo.getAllLogs()) }

    var activeDate by remember { mutableStateOf(LocalDate.now()) }
    var calYearMonth by remember { mutableStateOf(YearMonth.now()) }
    var calSelectedDate by remember { mutableStateOf(LocalDate.now()) }

    var editingSupplement by remember { mutableStateOf<Supplement?>(null) }
    var showEditDialog by remember { mutableStateOf(false) }
    var deletingSupplement by remember { mutableStateOf<Supplement?>(null) }

    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    fun reload() {
        supplements = repo.getSupplements()
        logs = repo.getAllLogs()
    }

    LaunchedEffect(externalRefreshTick) {
        reload()
    }

    val colorScheme = if (darkMode) {
        darkColorScheme(
            primary = SageLight,
            onPrimary = Color(0xFF0A1F15),
            primaryContainer = SageDark,
            onPrimaryContainer = Color(0xFFD8F3DC),
            background = Color(0xFF111513),
            surface = Color(0xFF19201C),
            surfaceVariant = Color(0xFF232E28)
        )
    } else {
        lightColorScheme(
            primary = SagePrimary,
            onPrimary = Color.White,
            primaryContainer = Color(0xFFDFECE4),
            onPrimaryContainer = SageDark,
            background = Color(0xFFF6F7F4),
            surface = Color.White,
            surfaceVariant = Color(0xFFECEFE9)
        )
    }

    MaterialTheme(colorScheme = colorScheme) {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbarHostState) },
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("SuppTrack Vegan", fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
                            Text(
                                "Pixel Native · v${BuildConfig.VERSION_NAME}",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = {
                            darkMode = !darkMode
                            repo.setDarkMode(darkMode)
                        }) {
                            Icon(
                                imageVector = if (darkMode) Icons.Default.LightMode else Icons.Default.DarkMode,
                                contentDescription = "Theme umschalten"
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background
                    )
                )
            },
            bottomBar = {
                NavigationBar {
                    NavigationBarItem(
                        selected = selectedTab == 0,
                        onClick = { selectedTab = 0 },
                        icon = { Icon(Icons.Default.CheckCircle, contentDescription = null) },
                        label = { Text("Heute") }
                    )
                    NavigationBarItem(
                        selected = selectedTab == 1,
                        onClick = { selectedTab = 1 },
                        icon = { Icon(Icons.Default.DateRange, contentDescription = null) },
                        label = { Text("Kalender") }
                    )
                    NavigationBarItem(
                        selected = selectedTab == 2,
                        onClick = { selectedTab = 2 },
                        icon = { Icon(Icons.Default.Notifications, contentDescription = null) },
                        label = { Text("Wecker") }
                    )
                    NavigationBarItem(
                        selected = selectedTab == 3,
                        onClick = { selectedTab = 3 },
                        icon = { Icon(Icons.Default.SystemUpdate, contentDescription = null) },
                        label = { Text("Updates") }
                    )
                }
            }
        ) { padding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .background(MaterialTheme.colorScheme.background)
            ) {
                when (selectedTab) {
                    0 -> TodayTab(
                        date = activeDate,
                        supplements = supplements,
                        logs = logs,
                        repo = repo,
                        onDateChange = { activeDate = it },
                        onToggle = { id ->
                            val checked = repo.toggleCheck(activeDate, id)
                            reload()
                            if (checked) {
                                val st = repo.getDayStats(activeDate)
                                if (st.totalReq > 0 && st.pct == 100) {
                                    scope.launch { snackbarHostState.showSnackbar("🎉 100 % Tagesziel erreicht!") }
                                }
                            }
                        },
                        onToggleSlotAll = { slot ->
                            val slotSupps = supplements.filter { it.active && it.slot == slot }
                            val dayChecks = logs[activeDate.format(SupplementRepository.DATE_FMT)] ?: emptySet()
                            val allDone = slotSupps.all { dayChecks.contains(it.id) }
                            repo.setManyChecked(activeDate, slotSupps.map { it.id }, checked = !allDone)
                            reload()
                        },
                        onAdd = {
                            editingSupplement = null
                            showEditDialog = true
                        },
                        onEdit = { supp ->
                            editingSupplement = supp
                            showEditDialog = true
                        },
                        onDelete = { supp -> deletingSupplement = supp }
                    )

                    1 -> CalendarTab(
                        yearMonth = calYearMonth,
                        selectedDate = calSelectedDate,
                        supplements = supplements,
                        logs = logs,
                        repo = repo,
                        onMonthChange = { calYearMonth = it },
                        onSelectDate = { calSelectedDate = it },
                        onToggleDaySupp = { date, id ->
                            repo.toggleCheck(date, id)
                            reload()
                        },
                        onOpenInToday = { date ->
                            activeDate = date
                            selectedTab = 0
                        }
                    )

                    2 -> RemindersTab(
                        supplements = supplements,
                        repo = repo,
                        onAdd = {
                            editingSupplement = null
                            showEditDialog = true
                        },
                        onEdit = { supp ->
                            editingSupplement = supp
                            showEditDialog = true
                        },
                        onDelete = { supp -> deletingSupplement = supp },
                        onUpdateSupp = { updated ->
                            repo.upsertSupplement(updated)
                            reload()
                        },
                        onShowMessage = { msg ->
                            scope.launch { snackbarHostState.showSnackbar(msg) }
                        }
                    )

                    3 -> UpdatesAndBackupTab(
                        repo = repo,
                        onReload = { reload() },
                        onShowMessage = { msg ->
                            scope.launch { snackbarHostState.showSnackbar(msg) }
                        }
                    )
                }
            }
        }

        if (showEditDialog) {
            SupplementEditDialog(
                initial = editingSupplement,
                onDismiss = { showEditDialog = false },
                onSave = { saved ->
                    repo.upsertSupplement(saved)
                    reload()
                    showEditDialog = false
                    scope.launch { snackbarHostState.showSnackbar("„${saved.name}“ gespeichert ✓") }
                },
                onDelete = if (editingSupplement != null) {
                    {
                        showEditDialog = false
                        deletingSupplement = editingSupplement
                    }
                } else null
            )
        }

        deletingSupplement?.let { target ->
            AlertDialog(
                onDismissRequest = { deletingSupplement = null },
                title = { Text("„${target.name}“ entfernen?") },
                text = { Text("Das Supplement wird dauerhaft aus deinem Plan und aus dem Verlauf entfernt.") },
                confirmButton = {
                    Button(
                        onClick = {
                            repo.deleteSupplement(target.id)
                            reload()
                            deletingSupplement = null
                            scope.launch { snackbarHostState.showSnackbar("„${target.name}“ entfernt") }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                    ) { Text("Entfernen") }
                },
                dismissButton = {
                    TextButton(onClick = { deletingSupplement = null }) { Text("Abbrechen") }
                }
            )
        }
    }
}

// ==============================================================================
// TAB 1: HEUTE
// ==============================================================================
@Composable
fun TodayTab(
    date: LocalDate,
    supplements: List<Supplement>,
    logs: Map<String, Set<String>>,
    repo: SupplementRepository,
    onDateChange: (LocalDate) -> Unit,
    onToggle: (String) -> Unit,
    onToggleSlotAll: (DaySlot) -> Unit,
    onAdd: () -> Unit,
    onEdit: (Supplement) -> Unit,
    onDelete: (Supplement) -> Unit
) {
    val today = LocalDate.now()
    val stats = repo.getDayStats(date, supplements, logs)
    val streak = repo.calculateStreak(supplements, logs)
    val checks = logs[date.format(SupplementRepository.DATE_FMT)] ?: emptySet()
    val activeSupps = supplements.filter { it.active }
    val dateFmt = remember { DateTimeFormatter.ofPattern("EEE, d. MMM yyyy", Locale.GERMAN) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Datums-Zeile
        item {
            Card(shape = RoundedCornerShape(20.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    IconButton(onClick = { onDateChange(date.minusDays(1)) }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Zurück")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            text = if (date == today) "Heute · ${date.format(dateFmt)}" else date.format(dateFmt),
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                        if (date != today) {
                            TextButton(onClick = { onDateChange(today) }, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)) {
                                Text("Heute", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                    IconButton(onClick = { onDateChange(date.plusDays(1)) }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Vor")
                    }
                }
            }
        }

        // Fortschritts-Hero-Card
        item {
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = SageDark, contentColor = Color.White)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = when {
                                stats.totalReq == 0 -> "Keine Pflicht-Supplemente aktiv"
                                stats.pct == 100 -> "✅ Perfekt! Tagesziel erreicht"
                                stats.pct >= 50 -> "💪 Auf sehr gutem Kurs"
                                else -> "🎯 Tagesziel läuft"
                            },
                            fontSize = 12.sp,
                            color = Color(0xFFD8F3DC),
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = "${stats.reqDone} / ${stats.totalReq} Pflicht",
                            fontSize = 24.sp,
                            fontWeight = FontWeight.ExtraBold
                        )
                        Text(
                            text = "🔥 Serie: $streak ${if (streak == 1) "Tag" else "Tage"}",
                            fontSize = 12.sp,
                            color = Color(0xFFB7E4C7)
                        )
                    }

                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(72.dp)) {
                        CircularProgressIndicator(
                            progress = { stats.pct / 100f },
                            modifier = Modifier.fillMaxSize(),
                            strokeWidth = 7.dp,
                            color = if (stats.pct == 100) Color(0xFF4ADE80) else Color(0xFFFDE047),
                            trackColor = Color.White.copy(alpha = 0.2f)
                        )
                        Text("${stats.pct}%", fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
                    }
                }
            }
        }

        // Slots gruppiert
        DaySlot.entries.sortedBy { it.order }.forEach { slot ->
            val itemsInSlot = activeSupps.filter { it.slot == slot }
            if (itemsInSlot.isNotEmpty()) {
                val allChecked = itemsInSlot.all { checks.contains(it.id) }
                item(key = "header_${slot.key}") {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp, start = 4.dp, end = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${slot.emoji} ${slot.label}",
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = if (allChecked) "Alle aufheben" else "Alle abhaken",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.clickable { onToggleSlotAll(slot) }.padding(4.dp)
                        )
                    }
                }

                items(itemsInSlot, key = { it.id }) { supp ->
                    val isDone = checks.contains(supp.id)
                    Card(
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (isDone) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                            else MaterialTheme.colorScheme.surface
                        )
                    ) {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onToggle(supp.id) }
                                    .padding(14.dp),
                                verticalAlignment = Alignment.Top,
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(26.dp)
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isDone) SagePrimary else Color.Transparent)
                                        .border(2.dp, if (isDone) SagePrimary else MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    if (isDone) {
                                        Icon(Icons.Default.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                                    }
                                }

                                Column(modifier = Modifier.weight(1f)) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Text(
                                            text = supp.name,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 15.sp,
                                            textDecoration = if (isDone) TextDecoration.LineThrough else TextDecoration.None,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                            modifier = Modifier.weight(1f, fill = false)
                                        )
                                        if (!supp.required) {
                                            Text(
                                                "Optional",
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(6.dp))
                                                    .background(MaterialTheme.colorScheme.surfaceVariant)
                                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                                            )
                                        }
                                    }
                                    Text(
                                        text = supp.dose,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                    if (supp.note.isNotBlank()) {
                                        Text(
                                            text = supp.note,
                                            fontSize = 11.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.padding(top = 3.dp)
                                        )
                                    }
                                }
                            }

                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))

                            Row(
                                modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = if (supp.reminderEnabled) "⏰ ${supp.time} Uhr" else "Kein Wecker",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                    TextButton(
                                        onClick = { onEdit(supp) },
                                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp)
                                    ) {
                                        Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(14.dp))
                                        Spacer(Modifier.width(4.dp))
                                        Text("Anpassen", fontSize = 11.sp)
                                    }
                                    IconButton(onClick = { onDelete(supp) }, modifier = Modifier.size(32.dp)) {
                                        Icon(Icons.Default.Delete, contentDescription = "Entfernen", tint = Color(0xFFDC2626), modifier = Modifier.size(16.dp))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        item {
            OutlinedButton(
                onClick = onAdd,
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                shape = RoundedCornerShape(18.dp)
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Neues Supplement hinzufügen", fontWeight = FontWeight.Bold)
            }
        }
    }
}

// ==============================================================================
// TAB 2: KALENDER MIT 5-STUFIGER FARBSKALA
// ==============================================================================
private fun heatmapBgColor(pct: Int, isFuture: Boolean, isDark: Boolean): Color = when {
    isFuture -> Color.Transparent
    pct == 0 -> if (isDark) Color(0xFF232C27) else Color(0xFFECEFE9)
    pct < 40 -> if (isDark) Color(0xFF7F1D1D) else Color(0xFFFECDD3)
    pct < 70 -> if (isDark) Color(0xFF92400E) else Color(0xFFFDE68A)
    pct < 100 -> if (isDark) Color(0xFF3F6212) else Color(0xFFD9F99D)
    else -> Color(0xFF16A34A)
}

private fun heatmapTextColor(pct: Int, isFuture: Boolean, isDark: Boolean): Color = when {
    isFuture -> if (isDark) Color(0xFF4B5563) else Color(0xFFCBD5E1)
    pct == 100 -> Color.White
    isDark -> Color.White
    else -> Color(0xFF111827)
}

@Composable
fun CalendarTab(
    yearMonth: YearMonth,
    selectedDate: LocalDate,
    supplements: List<Supplement>,
    logs: Map<String, Set<String>>,
    repo: SupplementRepository,
    onMonthChange: (YearMonth) -> Unit,
    onSelectDate: (LocalDate) -> Unit,
    onToggleDaySupp: (LocalDate, String) -> Unit,
    onOpenInToday: (LocalDate) -> Unit
) {
    val today = LocalDate.now()
    val isDark = MaterialTheme.colorScheme.background.red < 0.2f
    val monthTitle = "${yearMonth.month.getDisplayName(TextStyle.FULL, Locale.GERMAN)} ${yearMonth.year}"
    val daysInMonth = yearMonth.lengthOfMonth()
    val firstWeekdayOffset = yearMonth.atDay(1).dayOfWeek.value - 1 // Mo=0..So=6

    var sumPct = 0
    var countedDays = 0
    var perfectDays = 0
    for (d in 1..daysInMonth) {
        val date = yearMonth.atDay(d)
        if (!date.isAfter(today)) {
            val st = repo.getDayStats(date, supplements, logs)
            sumPct += st.pct
            countedDays++
            if (st.totalReq > 0 && st.pct == 100) perfectDays++
        }
    }
    val avgPct = if (countedDays > 0) sumPct / countedDays else 0
    val streak = repo.calculateStreak(supplements, logs)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Card(shape = RoundedCornerShape(24.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(onClick = { onMonthChange(yearMonth.minusMonths(1)) }) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Vormonat")
                        }
                        Text(monthTitle, fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                        IconButton(onClick = { onMonthChange(yearMonth.plusMonths(1)) }) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Nächster Monat")
                        }
                    }

                    // 3 Monats-KPIs
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        KpiTile("Ø Quote", "$avgPct%", Modifier.weight(1f))
                        KpiTile("100%-Tage", "$perfectDays", Modifier.weight(1f))
                        KpiTile("Serie", "$streak d", Modifier.weight(1f))
                    }

                    // Wochentage
                    Row(modifier = Modifier.fillMaxWidth()) {
                        listOf("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So").forEach { wd ->
                            Text(
                                text = wd,
                                modifier = Modifier.weight(1f),
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    // Monats-Grid (6 Zeilen max)
                    val totalCells = firstWeekdayOffset + daysInMonth
                    val rows = (totalCells + 6) / 7
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        for (row in 0 until rows) {
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                for (col in 0 until 7) {
                                    val cellIndex = row * 7 + col
                                    val dayNum = cellIndex - firstWeekdayOffset + 1
                                    if (dayNum in 1..daysInMonth) {
                                        val d = yearMonth.atDay(dayNum)
                                        val isFuture = d.isAfter(today)
                                        val isSelected = d == selectedDate
                                        val st = repo.getDayStats(d, supplements, logs)
                                        val bg = heatmapBgColor(st.pct, isFuture, isDark)
                                        val fg = heatmapTextColor(st.pct, isFuture, isDark)

                                        Box(
                                            modifier = Modifier
                                                .weight(1f)
                                                .aspectRatio(1f)
                                                .clip(RoundedCornerShape(12.dp))
                                                .background(bg)
                                                .border(
                                                    width = if (isSelected) 2.dp else if (d == today) 1.5.dp else 0.dp,
                                                    color = if (isSelected) MaterialTheme.colorScheme.onSurface
                                                    else if (d == today) MaterialTheme.colorScheme.primary
                                                    else Color.Transparent,
                                                    shape = RoundedCornerShape(12.dp)
                                                )
                                                .clickable { onSelectDate(d) },
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                                Text("$dayNum", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = fg)
                                                if (!isFuture) {
                                                    Text(
                                                        text = if (st.pct == 100 && st.totalReq > 0) "✓" else if (st.pct > 0) "${st.pct}%" else "·",
                                                        fontSize = 8.sp,
                                                        fontWeight = FontWeight.Bold,
                                                        color = fg.copy(alpha = 0.85f)
                                                    )
                                                }
                                            }
                                        }
                                    } else {
                                        Spacer(Modifier.weight(1f))
                                    }
                                }
                            }
                        }
                    }

                    // Farbskala-Legende
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        LegendChip("0%", heatmapBgColor(0, false, isDark))
                        LegendChip("<40%", heatmapBgColor(25, false, isDark))
                        LegendChip("<70%", heatmapBgColor(55, false, isDark))
                        LegendChip("<100%", heatmapBgColor(85, false, isDark))
                        LegendChip("100%", heatmapBgColor(100, false, isDark))
                    }
                }
            }
        }

        // Einzeltag-Inspektor
        item {
            val selStats = repo.getDayStats(selectedDate, supplements, logs)
            val selChecks = logs[selectedDate.format(SupplementRepository.DATE_FMT)] ?: emptySet()
            val activeSupps = supplements.filter { it.active }
            val fmt = DateTimeFormatter.ofPattern("EEEE, d. MMMM yyyy", Locale.GERMAN)

            Card(shape = RoundedCornerShape(24.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("EINZELTAG-ANSICHT", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(selectedDate.format(fmt), fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
                        }
                        Text(
                            "${selStats.pct}% (${selStats.reqDone}/${selStats.totalReq})",
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }

                    activeSupps.forEach { s ->
                        val done = selChecks.contains(s.id)
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .background(
                                    if (done) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f)
                                    else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                                )
                                .clickable { onToggleDaySupp(selectedDate, s.id) }
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(s.name, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                Text(s.dose, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Text(if (done) "✓ Erledigt" else "Offen", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = if (done) SagePrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }

                    FilledTonalButton(
                        onClick = { onOpenInToday(selectedDate) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp)
                    ) {
                        Text("Diesen Tag in „Heute“ öffnen →", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
private fun KpiTile(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            .padding(vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Bold)
        Text(value, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun LegendChip(label: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Box(modifier = Modifier.size(10.dp).clip(CircleShape).background(color))
        Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

// ==============================================================================
// TAB 3: WECKER & STACK VERWALTEN
// ==============================================================================
@Composable
fun RemindersTab(
    supplements: List<Supplement>,
    repo: SupplementRepository,
    onAdd: () -> Unit,
    onEdit: (Supplement) -> Unit,
    onDelete: (Supplement) -> Unit,
    onUpdateSupp: (Supplement) -> Unit,
    onShowMessage: (String) -> Unit
) {
    val context = LocalContext.current
    var hasNotifPerm by remember {
        mutableStateOf(
            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        )
    }
    val alarmManager = remember { context.getSystemService(Context.ALARM_SERVICE) as AlarmManager }
    val hasExactAlarm = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()

    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasNotifPerm = granted
        if (granted) {
            ReminderScheduler.rescheduleAll(context)
            onShowMessage("🔔 Benachrichtigungen aktiviert!")
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(shape = RoundedCornerShape(22.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("🔔 System-Wecker (Pixel)", fontWeight = FontWeight.ExtraBold, fontSize = 15.sp)
                    Text(
                        "Native Android-Alarme laufen zuverlässig im Hintergrund – auch nach einem Neustart. Jede Benachrichtigung enthält einen „Alle abhaken“-Button.",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (!hasNotifPerm && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            Button(
                                onClick = { permLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(14.dp)
                            ) { Text("Erlauben") }
                        }
                        OutlinedButton(
                            onClick = {
                                ReminderScheduler.showNotification(
                                    context,
                                    "🧪 SuppTrack Test-Wecker",
                                    "Deine nativen Pixel-Benachrichtigungen funktionieren einwandfrei!",
                                    null,
                                    99999
                                )
                                onShowMessage("Test-Benachrichtigung gesendet")
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(14.dp)
                        ) { Text("Test-Alarm") }
                    }

                    if (!hasExactAlarm && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        FilledTonalButton(
                            onClick = {
                                val i = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
                                    data = Uri.parse("package:${context.packageName}")
                                }
                                context.startActivity(i)
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(14.dp)
                        ) { Text("Exakte Alarme in Android freigeben") }
                    }
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("💊 Dein Supplement-Stack", fontWeight = FontWeight.ExtraBold, fontSize = 15.sp)
                FilledTonalButton(onClick = onAdd, shape = RoundedCornerShape(12.dp)) {
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Neu")
                }
            }
        }

        items(supplements, key = { it.id }) { supp ->
            Card(shape = RoundedCornerShape(20.dp)) {
                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(supp.name, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            Text("${supp.slot.emoji} ${supp.slot.label} · ${supp.dose}", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                            if (supp.note.isNotBlank()) {
                                Text(supp.note, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Row {
                            IconButton(onClick = { onEdit(supp) }) {
                                Icon(Icons.Default.Edit, contentDescription = "Anpassen")
                            }
                            IconButton(onClick = { onDelete(supp) }) {
                                Icon(Icons.Default.Delete, contentDescription = "Entfernen", tint = Color(0xFFDC2626))
                            }
                        }
                    }

                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = supp.active,
                                onCheckedChange = { onUpdateSupp(supp.copy(active = it)) }
                            )
                            Text("Aktiv", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = supp.reminderEnabled,
                                enabled = supp.active,
                                onCheckedChange = { onUpdateSupp(supp.copy(reminderEnabled = it)) }
                            )
                            Text("⏰ ${supp.time}", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}

// ==============================================================================
// TAB 4: IN-APP-UPDATES & BACKUP
// ==============================================================================
@Composable
fun UpdatesAndBackupTab(
    repo: SupplementRepository,
    onReload: () -> Unit,
    onShowMessage: (String) -> Unit
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()

    var githubRepo by remember { mutableStateOf(repo.getUpdateRepo()) }
    var directUrl by remember { mutableStateOf(repo.getDirectApkUrl()) }
    var checking by remember { mutableStateOf(false) }
    var downloading by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableFloatStateOf(0f) }
    var releaseInfo by remember { mutableStateOf<ReleaseInfo?>(null) }
    var statusMsg by remember { mutableStateOf("") }
    var importText by remember { mutableStateOf("") }
    var showImportDialog by remember { mutableStateOf(false) }
    var showResetDialog by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        // In-App Updater Card
        Card(shape = RoundedCornerShape(22.dp)) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("🚀 Updates direkt installieren", fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                Text(
                    "Aktuelle Version: v${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE}). Hinterlege dein GitHub-Repo, um neue von der KI erzeugte Builds mit einem Tipp ohne Datenverlust zu installieren.",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                OutlinedTextField(
                    value = githubRepo,
                    onValueChange = {
                        githubRepo = it
                        repo.setUpdateRepo(it)
                    },
                    label = { Text("GitHub Repository (z. B. deinname/supptrack)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Button(
                    onClick = {
                        checking = true
                        statusMsg = "Suche nach neuem Release..."
                        releaseInfo = null
                        scope.launch {
                            val res = UpdateManager.checkGitHubRelease(githubRepo)
                            checking = false
                            res.onSuccess { info ->
                                releaseInfo = info
                                statusMsg = if (info.isNewer) "🎉 Neues Update verfügbar: ${info.tagName}"
                                else "✅ Du nutzt bereits die neueste Version (${info.tagName})."
                            }.onFailure { err ->
                                statusMsg = "Fehler: ${err.message}"
                            }
                        }
                    },
                    enabled = !checking && !downloading && githubRepo.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Text(if (checking) "Prüfe..." else "Nach Update suchen")
                }

                if (statusMsg.isNotBlank()) {
                    Text(statusMsg, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
                }

                releaseInfo?.let { info ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("${info.title} (${info.tagName})", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            Text(info.notes, fontSize = 11.sp)
                            Button(
                                onClick = {
                                    downloading = true
                                    downloadProgress = 0f
                                    scope.launch {
                                        val dl = UpdateManager.downloadApk(context, info.apkDownloadUrl) { p ->
                                            downloadProgress = p
                                        }
                                        downloading = false
                                        dl.onSuccess { apk ->
                                            val started = UpdateManager.triggerApkInstall(context, apk)
                                            if (!started) {
                                                onShowMessage("Bitte einmalig „Aus dieser Quelle zulassen“ aktivieren und erneut tippen.")
                                            }
                                        }.onFailure { e ->
                                            onShowMessage("Download-Fehler: ${e.message}")
                                        }
                                    }
                                },
                                enabled = !downloading,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Text(if (downloading) "Lade herunter (${(downloadProgress * 100).toInt()}%)..." else "Update herunterladen & installieren")
                            }
                        }
                    }
                }

                if (downloading) {
                    LinearProgressIndicator(progress = { downloadProgress }, modifier = Modifier.fillMaxWidth())
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                Text("Alternative: Direkt-Link zu einer .apk", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                OutlinedTextField(
                    value = directUrl,
                    onValueChange = {
                        directUrl = it
                        repo.setDirectApkUrl(it)
                    },
                    label = { Text("https://.../SuppTrack.apk") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedButton(
                    onClick = {
                        downloading = true
                        downloadProgress = 0f
                        scope.launch {
                            val dl = UpdateManager.downloadApk(context, directUrl) { p -> downloadProgress = p }
                            downloading = false
                            dl.onSuccess { apk ->
                                val started = UpdateManager.triggerApkInstall(context, apk)
                                if (!started) onShowMessage("Bitte einmalig App-Installation in Einstellungen erlauben.")
                            }.onFailure { e -> onShowMessage("Fehler: ${e.message}") }
                        }
                    },
                    enabled = !downloading && directUrl.startsWith("http"),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Text("APK direkt laden & installieren")
                }
            }
        }

        // Backup & Wiederherstellung
        Card(shape = RoundedCornerShape(22.dp)) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("💾 Datensicherung (JSON)", fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                Text(
                    "Kopiere deinen gesamten Kalender-Verlauf und Supplement-Plan als Text-Backup in die Zwischenablage.",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            clipboard.setText(AnnotatedString(repo.exportBackupJson()))
                            onShowMessage("Backup in Zwischenablage kopiert ✓")
                        },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(14.dp)
                    ) { Text("Backup kopieren") }

                    OutlinedButton(
                        onClick = {
                            importText = clipboard.getText()?.text ?: ""
                            showImportDialog = true
                        },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(14.dp)
                    ) { Text("Backup laden") }
                }
                TextButton(
                    onClick = { showResetDialog = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Auf Standard-Plan zurücksetzen", color = Color(0xFFDC2626))
                }
            }
        }
    }

    if (showImportDialog) {
        AlertDialog(
            onDismissRequest = { showImportDialog = false },
            title = { Text("JSON-Backup einfügen") },
            text = {
                OutlinedTextField(
                    value = importText,
                    onValueChange = { importText = it },
                    label = { Text("Backup-JSON") },
                    minLines = 4,
                    maxLines = 8,
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                Button(onClick = {
                    if (repo.importBackupJson(importText)) {
                        onReload()
                        showImportDialog = false
                        onShowMessage("Backup erfolgreich wiederhergestellt ✓")
                    } else {
                        onShowMessage("Ungültiges JSON-Format")
                    }
                }) { Text("Wiederherstellen") }
            },
            dismissButton = {
                TextButton(onClick = { showImportDialog = false }) { Text("Abbrechen") }
            }
        )
    }

    if (showResetDialog) {
        AlertDialog(
            onDismissRequest = { showResetDialog = false },
            title = { Text("Alles zurücksetzen?") },
            text = { Text("Alle abgehakten Tage und eigenen Anpassungen werden gelöscht.") },
            confirmButton = {
                Button(
                    onClick = {
                        repo.resetToDefault()
                        onReload()
                        showResetDialog = false
                        onShowMessage("Auf Standard-Plan zurückgesetzt")
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                ) { Text("Zurücksetzen") }
            },
            dismissButton = {
                TextButton(onClick = { showResetDialog = false }) { Text("Abbrechen") }
            }
        )
    }
}

// ==============================================================================
// DIALOG: SUPPLEMENT HINZUFÜGEN / ANPASSEN
// ==============================================================================
@Composable
fun SupplementEditDialog(
    initial: Supplement?,
    onDismiss: () -> Unit,
    onSave: (Supplement) -> Unit,
    onDelete: (() -> Unit)?
) {
    var name by remember { mutableStateOf(initial?.name ?: "") }
    var dose by remember { mutableStateOf(initial?.dose ?: "") }
    var slot by remember { mutableStateOf(initial?.slot ?: DaySlot.MEAL) }
    var time by remember { mutableStateOf(initial?.time ?: "13:00") }
    var note by remember { mutableStateOf(initial?.note ?: "") }
    var required by remember { mutableStateOf(initial?.required ?: true) }
    var reminderEnabled by remember { mutableStateOf(initial?.reminderEnabled ?: true) }
    var timeError by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "Neues Supplement" else "Supplement anpassen", fontWeight = FontWeight.ExtraBold) },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Supplementname") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = dose,
                    onValueChange = { dose = it },
                    label = { Text("Menge (z. B. 2.000 IE / 5 g)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = time,
                    onValueChange = {
                        time = it
                        timeError = !it.matches(Regex("^([01]\\d|2[0-3]):[0-5]\\d$"))
                    },
                    label = { Text("Erinnerungszeit (HH:mm)") },
                    isError = timeError,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Text("Tageszeit", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    DaySlot.entries.forEach { option ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .background(
                                    if (slot == option) MaterialTheme.colorScheme.primaryContainer
                                    else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                                )
                                .clickable { slot = option }
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("${option.emoji} ${option.label}", fontSize = 13.sp, fontWeight = if (slot == option) FontWeight.Bold else FontWeight.Normal)
                        }
                    }
                }

                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Beschreibung") },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth()
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = required, onCheckedChange = { required = it })
                    Text("Zählt zur 100%-Tagesquote (Pflicht)", fontSize = 12.sp)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = reminderEnabled, onCheckedChange = { reminderEnabled = it })
                    Text("Wecker aktiv", fontSize = 12.sp)
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val cleanTime = if (time.matches(Regex("^([01]\\d|2[0-3]):[0-5]\\d$"))) time else "13:00"
                    onSave(
                        Supplement(
                            id = initial?.id ?: ("supp_" + System.currentTimeMillis()),
                            name = name.trim(),
                            dose = dose.trim(),
                            slot = slot,
                            time = cleanTime,
                            reminderEnabled = reminderEnabled,
                            required = required,
                            active = initial?.active ?: true,
                            note = note.trim()
                        )
                    )
                },
                enabled = name.isNotBlank() && dose.isNotBlank() && !timeError
            ) { Text("Speichern") }
        },
        dismissButton = {
            Row {
                if (onDelete != null) {
                    TextButton(onClick = onDelete) {
                        Text("Entfernen", color = Color(0xFFDC2626))
                    }
                }
                TextButton(onClick = onDismiss) { Text("Abbrechen") }
            }
        }
    )
}
