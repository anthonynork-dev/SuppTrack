package com.supptrack.vegan

import android.content.Context
import android.content.Intent
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/**
 * Tageszeit-Kategorien für den Einnahmeplan.
 */
enum class DaySlot(val key: String, val label: String, val emoji: String, val order: Int) {
    MORNING("morning", "Morgens (nüchtern)", "🌅", 1),
    MEAL("meal", "Hauptmahlzeit (fetthaltig)", "🍽️", 2),
    WORKOUT("workout", "Training / Situativ", "🏃", 3),
    EVENING("evening", "Abends (Regeneration)", "🌙", 4);

    companion object {
        fun fromKey(key: String): DaySlot = entries.firstOrNull { it.key == key } ?: MEAL
    }
}

data class Supplement(
    val id: String,
    val name: String,
    val dose: String,
    val slot: DaySlot,
    val time: String, // "HH:mm"
    val reminderEnabled: Boolean,
    val required: Boolean,
    val active: Boolean,
    val note: String
)

data class DayStats(
    val reqDone: Int,
    val totalReq: Int,
    val optDone: Int,
    val pct: Int
)

/**
 * Zentrale Datenhaltung über SharedPreferences + JSON.
 * Synchronisiert automatisch das Pixel-Homescreen-Widget und die System-Wecker.
 */
class SupplementRepository(private val context: Context) {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {
        private const val PREFS_NAME = "supptrack_native_prefs_v1"
        private const val KEY_SUPPLEMENTS = "supplements_json"
        private const val KEY_LOGS = "logs_json"
        private const val KEY_DARK_MODE = "dark_mode"
        private const val KEY_UPDATE_REPO = "update_github_repo"
        private const val KEY_DIRECT_APK_URL = "update_direct_url"
        const val ACTION_DATA_UPDATED = "com.supptrack.vegan.ACTION_DATA_UPDATED"

        val DATE_FMT: DateTimeFormatter = DateTimeFormatter.ISO_LOCAL_DATE

        fun defaultSupplements(): List<Supplement> = listOf(
            Supplement(
                id = "jod_selen",
                name = "Jod & Selen",
                dose = "100–150 µg Jod + 50–70 µg Selen",
                slot = DaySlot.MORNING,
                time = "07:30",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Morgens nüchtern oder mit Abstand zu Kaffee & isoliertem Vitamin C."
            ),
            Supplement(
                id = "omega3",
                name = "Omega-3 (Algenöl)",
                dose = "2 Kapseln (900 mg EPA+DHA)",
                slot = DaySlot.MEAL,
                time = "13:00",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Präparat 1 – immer zu einer fetthaltigen Mahlzeit einnehmen."
            ),
            Supplement(
                id = "b12",
                name = "Vitamin B12",
                dose = "1 Tablette (500 µg)",
                slot = DaySlot.MEAL,
                time = "13:00",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Präparat 2 – optimal abgedeckt."
            ),
            Supplement(
                id = "vitd3",
                name = "Veganes Vitamin D3",
                dose = "2.000 IE (Okt–Apr)",
                slot = DaySlot.MEAL,
                time = "13:00",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Zusammen mit Fett (Mittagessen + Omega-3) einnehmen."
            ),
            Supplement(
                id = "kreatin",
                name = "Kreatin-Monohydrat",
                dose = "5 g täglich",
                slot = DaySlot.MEAL,
                time = "13:00",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Jeden Tag in Wasser oder im Protein-Shake (auch an Ruhetagen)."
            ),
            Supplement(
                id = "taurin",
                name = "Taurin (Vorrat)",
                dose = "1–2 g vor Ausdauer/Hitze",
                slot = DaySlot.WORKOUT,
                time = "17:00",
                reminderEnabled = false,
                required = false,
                active = true,
                note = "Optional 60–90 Min. vor harten Ausdauereinheiten. Keine Tagespflicht."
            ),
            Supplement(
                id = "magnesium",
                name = "Magnesium (5-Formen)",
                dose = "1 Tablette (200 mg)",
                slot = DaySlot.EVENING,
                time = "21:30",
                reminderEnabled = true,
                required = true,
                active = true,
                note = "Präparat 3 – abends für Muskelentspannung & Regeneration."
            ),
            Supplement(
                id = "zink",
                name = "Zinkbisglycinat (Optional)",
                dose = "10–15 mg",
                slot = DaySlot.EVENING,
                time = "21:30",
                reminderEnabled = false,
                required = false,
                active = false,
                note = "Aktivieren, sobald günstig nachgekauft (abends mit Magnesium)."
            )
        )
    }

    fun getSupplements(): List<Supplement> {
        val raw = prefs.getString(KEY_SUPPLEMENTS, null) ?: return defaultSupplements()
        return try {
            val arr = JSONArray(raw)
            val list = mutableListOf<Supplement>()
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                list.add(
                    Supplement(
                        id = o.optString("id", "supp_$i"),
                        name = o.optString("name", "Supplement"),
                        dose = o.optString("dose", ""),
                        slot = DaySlot.fromKey(o.optString("slot", "meal")),
                        time = o.optString("time", "13:00"),
                        reminderEnabled = o.optBoolean("reminderEnabled", true),
                        required = o.optBoolean("required", true),
                        active = o.optBoolean("active", true),
                        note = o.optString("note", "")
                    )
                )
            }
            list
        } catch (_: Exception) {
            defaultSupplements()
        }
    }

    fun saveSupplements(list: List<Supplement>) {
        val arr = JSONArray()
        list.forEach { s ->
            arr.put(JSONObject().apply {
                put("id", s.id)
                put("name", s.name)
                put("dose", s.dose)
                put("slot", s.slot.key)
                put("time", s.time)
                put("reminderEnabled", s.reminderEnabled)
                put("required", s.required)
                put("active", s.active)
                put("note", s.note)
            })
        }
        prefs.edit().putString(KEY_SUPPLEMENTS, arr.toString()).apply()
        notifySystemChanged(rescheduleAlarms = true)
    }

    fun upsertSupplement(supp: Supplement) {
        val current = getSupplements().toMutableList()
        val idx = current.indexOfFirst { it.id == supp.id }
        if (idx >= 0) {
            current[idx] = supp
        } else {
            current.add(supp)
        }
        saveSupplements(current)
    }

    fun deleteSupplement(suppId: String) {
        val updatedSupps = getSupplements().filterNot { it.id == suppId }
        // Veraltete Häkchen aus dem Verlauf bereinigen
        val logs = getAllLogs().toMutableMap()
        logs.keys.toList().forEach { dayKey ->
            val set = logs[dayKey]?.filterNot { it == suppId }?.toSet() ?: emptySet()
            logs[dayKey] = set
        }
        saveLogsInternal(logs)
        saveSupplements(updatedSupps)
    }

    fun getAllLogs(): Map<String, Set<String>> {
        val raw = prefs.getString(KEY_LOGS, null) ?: return emptyMap()
        return try {
            val obj = JSONObject(raw)
            val result = mutableMapOf<String, Set<String>>()
            val keys = obj.keys()
            while (keys.hasNext()) {
                val dayKey = keys.next()
                val arr = obj.optJSONArray(dayKey) ?: continue
                val set = mutableSetOf<String>()
                for (i in 0 until arr.length()) {
                    set.add(arr.getString(i))
                }
                result[dayKey] = set
            }
            result
        } catch (_: Exception) {
            emptyMap()
        }
    }

    private fun saveLogsInternal(logs: Map<String, Set<String>>) {
        val obj = JSONObject()
        logs.forEach { (dayKey, set) ->
            if (set.isNotEmpty()) {
                val arr = JSONArray()
                set.forEach { arr.put(it) }
                obj.put(dayKey, arr)
            }
        }
        prefs.edit().putString(KEY_LOGS, obj.toString()).apply()
    }

    fun getDayChecks(date: LocalDate): Set<String> {
        return getAllLogs()[date.format(DATE_FMT)] ?: emptySet()
    }

    fun toggleCheck(date: LocalDate, suppId: String): Boolean {
        val key = date.format(DATE_FMT)
        val logs = getAllLogs().toMutableMap()
        val current = (logs[key] ?: emptySet()).toMutableSet()
        val nowChecked = if (current.contains(suppId)) {
            current.remove(suppId)
            false
        } else {
            current.add(suppId)
            true
        }
        logs[key] = current
        saveLogsInternal(logs)
        notifySystemChanged(rescheduleAlarms = false)
        return nowChecked
    }

    fun setManyChecked(date: LocalDate, suppIds: List<String>, checked: Boolean) {
        val key = date.format(DATE_FMT)
        val logs = getAllLogs().toMutableMap()
        val current = (logs[key] ?: emptySet()).toMutableSet()
        if (checked) current.addAll(suppIds) else current.removeAll(suppIds.toSet())
        logs[key] = current
        saveLogsInternal(logs)
        notifySystemChanged(rescheduleAlarms = false)
    }

    fun getDayStats(date: LocalDate, supps: List<Supplement> = getSupplements(), logs: Map<String, Set<String>> = getAllLogs()): DayStats {
        val checks = logs[date.format(DATE_FMT)] ?: emptySet()
        val reqList = supps.filter { it.active && it.required }
        val optList = supps.filter { it.active && !it.required }
        val reqDone = reqList.count { checks.contains(it.id) }
        val optDone = optList.count { checks.contains(it.id) }
        val totalReq = reqList.size
        val pct = if (totalReq == 0) 0 else Math.round((reqDone * 100f) / totalReq)
        return DayStats(reqDone, totalReq, optDone, pct)
    }

    fun calculateStreak(supps: List<Supplement> = getSupplements(), logs: Map<String, Set<String>> = getAllLogs()): Int {
        var streak = 0
        var cursor = LocalDate.now()
        val todayStats = getDayStats(cursor, supps, logs)
        if (todayStats.totalReq > 0 && todayStats.pct == 100) {
            streak = 1
        }
        cursor = cursor.minusDays(1)
        repeat(365) {
            val st = getDayStats(cursor, supps, logs)
            if (st.totalReq > 0 && st.pct == 100) {
                streak++
                cursor = cursor.minusDays(1)
            } else {
                return streak
            }
        }
        return streak
    }

    fun isDarkMode(systemDefault: Boolean): Boolean =
        if (prefs.contains(KEY_DARK_MODE)) prefs.getBoolean(KEY_DARK_MODE, systemDefault) else systemDefault

    fun setDarkMode(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_DARK_MODE, enabled).apply()
    }

    fun getUpdateRepo(): String = prefs.getString(KEY_UPDATE_REPO, "") ?: ""
    fun setUpdateRepo(repo: String) {
        prefs.edit().putString(KEY_UPDATE_REPO, repo.trim()).apply()
    }

    fun getDirectApkUrl(): String = prefs.getString(KEY_DIRECT_APK_URL, "") ?: ""
    fun setDirectApkUrl(url: String) {
        prefs.edit().putString(KEY_DIRECT_APK_URL, url.trim()).apply()
    }

    fun exportBackupJson(): String {
        val root = JSONObject()
        val suppsArr = JSONArray()
        getSupplements().forEach { s ->
            suppsArr.put(JSONObject().apply {
                put("id", s.id)
                put("name", s.name)
                put("dose", s.dose)
                put("slot", s.slot.key)
                put("time", s.time)
                put("reminderEnabled", s.reminderEnabled)
                put("required", s.required)
                put("active", s.active)
                put("note", s.note)
            })
        }
        val logsObj = JSONObject()
        getAllLogs().forEach { (k, v) ->
            val a = JSONArray()
            v.forEach { a.put(it) }
            logsObj.put(k, a)
        }
        root.put("supplements", suppsArr)
        root.put("logs", logsObj)
        return root.toString(2)
    }

    fun importBackupJson(jsonText: String): Boolean {
        return try {
            val root = JSONObject(jsonText)
            val suppsArr = root.getJSONArray("supplements")
            val parsedSupps = mutableListOf<Supplement>()
            for (i in 0 until suppsArr.length()) {
                val o = suppsArr.getJSONObject(i)
                parsedSupps.add(
                    Supplement(
                        id = o.getString("id"),
                        name = o.getString("name"),
                        dose = o.optString("dose", ""),
                        slot = DaySlot.fromKey(o.optString("slot", "meal")),
                        time = o.optString("time", "13:00"),
                        reminderEnabled = o.optBoolean("reminderEnabled", true),
                        required = o.optBoolean("required", true),
                        active = o.optBoolean("active", true),
                        note = o.optString("note", "")
                    )
                )
            }
            val parsedLogs = mutableMapOf<String, Set<String>>()
            val logsObj = root.optJSONObject("logs")
            if (logsObj != null) {
                val keys = logsObj.keys()
                while (keys.hasNext()) {
                    val k = keys.next()
                    val a = logsObj.getJSONArray(k)
                    val s = mutableSetOf<String>()
                    for (i in 0 until a.length()) s.add(a.getString(i))
                    parsedLogs[k] = s
                }
            }
            saveLogsInternal(parsedLogs)
            saveSupplements(parsedSupps)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun resetToDefault() {
        saveLogsInternal(emptyMap())
        saveSupplements(defaultSupplements())
    }

    private fun notifySystemChanged(rescheduleAlarms: Boolean) {
        if (rescheduleAlarms) {
            ReminderScheduler.rescheduleAll(context)
        }
        SupplementWidgetProvider.updateAllWidgets(context)
        context.sendBroadcast(Intent(ACTION_DATA_UPDATED).setPackage(context.packageName))
    }
}
