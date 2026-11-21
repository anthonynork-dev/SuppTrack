package com.supptrack.vegan

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

/**
 * Echtes natives Pixel-Homescreen-Widget mit Direkt-Abhaken & 7-Tage-Farbskala.
 */
class SupplementWidgetProvider : AppWidgetProvider() {

    companion object {
        const val ACTION_TOGGLE_SUPP = "com.supptrack.vegan.ACTION_TOGGLE_SUPP"
        const val EXTRA_SUPP_ID = "extra_supp_id"

        fun updateAllWidgets(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, SupplementWidgetProvider::class.java)
            val ids = manager.getAppWidgetIds(component)
            ids.forEach { id ->
                updateSingleWidget(context, manager, id)
            }
        }

        private fun dotDrawableForPct(pct: Int): Int = when {
            pct == 0 -> R.drawable.dot_gray
            pct < 40 -> R.drawable.dot_rose
            pct < 70 -> R.drawable.dot_amber
            pct < 100 -> R.drawable.dot_lime
            else -> R.drawable.dot_emerald
        }

        fun updateSingleWidget(context: Context, manager: AppWidgetManager, widgetId: Int) {
            val repo = SupplementRepository(context)
            val supps = repo.getSupplements()
            val logs = repo.getAllLogs()
            val today = LocalDate.now()
            val stats = repo.getDayStats(today, supps, logs)
            val streak = repo.calculateStreak(supps, logs)
            val todayChecks = logs[today.format(SupplementRepository.DATE_FMT)] ?: emptySet()

            val views = RemoteViews(context.packageName, R.layout.widget_supptrack)

            // Kopfzeile -> App öffnen
            val openIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val openPi = PendingIntent.getActivity(
                context,
                0,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(R.id.widget_header, openPi)

            views.setTextViewText(R.id.widget_subtitle, "SUPPTRACK · 🔥 $streak d SERIE")
            views.setTextViewText(R.id.widget_title, "${stats.reqDone}/${stats.totalReq} Pflicht erledigt")
            views.setTextViewText(R.id.widget_pct_badge, if (stats.pct == 100 && stats.totalReq > 0) "✓ 100%" else "${stats.pct}%")

            // Bis zu 4 offene aktive Supplemente direkt abhakbar machen
            val openSupps = supps
                .filter { it.active && !todayChecks.contains(it.id) }
                .sortedWith(compareBy<Supplement> { !it.required }.thenBy { it.slot.order }.thenBy { it.time })
                .take(4)

            val rowIds = listOf(R.id.widget_row_0, R.id.widget_row_1, R.id.widget_row_2, R.id.widget_row_3)

            if (openSupps.isEmpty()) {
                views.setViewVisibility(R.id.widget_empty_msg, View.VISIBLE)
                rowIds.forEach { views.setViewVisibility(it, View.GONE) }
            } else {
                views.setViewVisibility(R.id.widget_empty_msg, View.GONE)
                rowIds.forEachIndexed { index, rowViewId ->
                    if (index < openSupps.size) {
                        val supp = openSupps[index]
                        views.setViewVisibility(rowViewId, View.VISIBLE)
                        views.setTextViewText(rowViewId, "○  ${supp.name} · ${supp.dose}")

                        val toggleIntent = Intent(context, SupplementWidgetProvider::class.java).apply {
                            action = ACTION_TOGGLE_SUPP
                            putExtra(EXTRA_SUPP_ID, supp.id)
                        }
                        val togglePi = PendingIntent.getBroadcast(
                            context,
                            500 + index,
                            toggleIntent,
                            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                        )
                        views.setOnClickPendingIntent(rowViewId, togglePi)
                    } else {
                        views.setViewVisibility(rowViewId, View.GONE)
                    }
                }
            }

            // 7-Tage-Farbskala aktualisieren
            val barIds = listOf(
                R.id.day_bar_0, R.id.day_bar_1, R.id.day_bar_2,
                R.id.day_bar_3, R.id.day_bar_4, R.id.day_bar_5, R.id.day_bar_6
            )
            val lblIds = listOf(
                R.id.day_lbl_0, R.id.day_lbl_1, R.id.day_lbl_2,
                R.id.day_lbl_3, R.id.day_lbl_4, R.id.day_lbl_5, R.id.day_lbl_6
            )

            for (i in 0..6) {
                val d = today.minusDays((6 - i).toLong())
                val st = repo.getDayStats(d, supps, logs)
                val shortWd = d.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.GERMAN).take(2)
                views.setImageViewResource(barIds[i], dotDrawableForPct(st.pct))
                views.setTextViewText(lblIds[i], shortWd)
            }

            manager.updateAppWidget(widgetId, views)
        }
    }

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        appWidgetIds.forEach { id ->
            updateSingleWidget(context, appWidgetManager, id)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_TOGGLE_SUPP) {
            val suppId = intent.getStringExtra(EXTRA_SUPP_ID) ?: return
            val repo = SupplementRepository(context)
            repo.toggleCheck(LocalDate.now(), suppId)
        }
    }
}
