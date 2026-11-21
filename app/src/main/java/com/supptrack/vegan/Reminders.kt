package com.supptrack.vegan

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.time.LocalDate
import java.util.Calendar

/**
 * Plant exakte tägliche System-Alarme (auch im Doze-/Standby-Modus des Pixel 11).
 */
object ReminderScheduler {
    const val CHANNEL_ID = "supptrack_reminders_channel"
    const val ACTION_TRIGGER_REMINDER = "com.supptrack.vegan.ACTION_TRIGGER_REMINDER"
    const val ACTION_MARK_TIME_DONE = "com.supptrack.vegan.ACTION_MARK_TIME_DONE"
    const val EXTRA_TIME = "extra_time"
    private const val PREFS_ALARMS = "supptrack_alarms_registry"
    private const val KEY_TIMES = "scheduled_times"

    fun ensureChannel(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Supplement-Erinnerungen",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Tägliche Erinnerungen für deine veganen Supplemente"
            enableVibration(true)
        }
        nm.createNotificationChannel(channel)
    }

    fun rescheduleAll(context: Context) {
        ensureChannel(context)
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val regPrefs = context.getSharedPreferences(PREFS_ALARMS, Context.MODE_PRIVATE)

        // Alte Alarme sauber abmelden
        val oldTimes = regPrefs.getStringSet(KEY_TIMES, emptySet()) ?: emptySet()
        oldTimes.forEach { timeStr ->
            val pi = buildTriggerPendingIntent(context, timeStr)
            alarmManager.cancel(pi)
        }

        // Neue eindeutige Zeiten sammeln
        val repo = SupplementRepository(context)
        val newTimes = repo.getSupplements()
            .filter { it.active && it.reminderEnabled && it.time.matches(Regex("^\\d{2}:\\d{2}$")) }
            .map { it.time }
            .toSet()

        regPrefs.edit().putStringSet(KEY_TIMES, newTimes).apply()

        newTimes.forEach { timeStr ->
            scheduleForTime(context, timeStr, forceNextDay = false)
        }
    }

    fun scheduleForTime(context: Context, timeStr: String, forceNextDay: Boolean) {
        val parts = timeStr.split(":")
        if (parts.size != 2) return
        val hour = parts[0].toIntOrNull() ?: return
        val minute = parts[1].toIntOrNull() ?: return

        val cal = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (forceNextDay || timeInMillis <= System.currentTimeMillis() + 3000L) {
                add(Calendar.DAY_OF_YEAR, 1)
            }
        }

        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = buildTriggerPendingIntent(context, timeStr)

        try {
            val canExact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()
            if (canExact) {
                alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
            } else {
                alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
            }
        } catch (_: SecurityException) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
        }
    }

    private fun buildTriggerPendingIntent(context: Context, timeStr: String): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            action = ACTION_TRIGGER_REMINDER
            putExtra(EXTRA_TIME, timeStr)
        }
        return PendingIntent.getBroadcast(
            context,
            timeStr.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    fun showNotification(context: Context, title: String, body: String, timeTag: String?, notifId: Int) {
        ensureChannel(context)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val openAppIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPi = PendingIntent.getActivity(
            context,
            notifId,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_leaf)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openAppPi)

        // Direkt-Abhaken-Button in der Benachrichtigung!
        if (timeTag != null) {
            val doneIntent = Intent(context, ReminderReceiver::class.java).apply {
                action = ACTION_MARK_TIME_DONE
                putExtra(EXTRA_TIME, timeTag)
            }
            val donePi = PendingIntent.getBroadcast(
                context,
                notifId + 9000,
                doneIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.addAction(R.drawable.ic_stat_leaf, "Alle abhaken ✓", donePi)
        }

        NotificationManagerCompat.from(context).notify(notifId, builder.build())
    }
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val timeStr = intent.getStringExtra(ReminderScheduler.EXTRA_TIME) ?: return
        val repo = SupplementRepository(context)
        val today = LocalDate.now()

        when (intent.action) {
            ReminderScheduler.ACTION_TRIGGER_REMINDER -> {
                // Sofort für morgen neu planen
                ReminderScheduler.scheduleForTime(context, timeStr, forceNextDay = true)

                val checkedToday = repo.getDayChecks(today)
                val dueSupps = repo.getSupplements().filter {
                    it.active && it.reminderEnabled && it.time == timeStr && !checkedToday.contains(it.id)
                }

                if (dueSupps.isNotEmpty()) {
                    val body = dueSupps.joinToString("\n") { "• ${it.name} (${it.dose})" }
                    ReminderScheduler.showNotification(
                        context = context,
                        title = "⏰ Supplemente ($timeStr Uhr)",
                        body = body,
                        timeTag = timeStr,
                        notifId = timeStr.hashCode()
                    )
                }
            }

            ReminderScheduler.ACTION_MARK_TIME_DONE -> {
                val matchingIds = repo.getSupplements()
                    .filter { it.active && it.reminderEnabled && it.time == timeStr }
                    .map { it.id }
                repo.setManyChecked(today, matchingIds, checked = true)
                NotificationManagerCompat.from(context).cancel(timeStr.hashCode())
            }
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action in listOf(
                Intent.ACTION_BOOT_COMPLETED,
                Intent.ACTION_TIME_CHANGED,
                Intent.ACTION_TIMEZONE_CHANGED
            )
        ) {
            ReminderScheduler.rescheduleAll(context)
            SupplementWidgetProvider.updateAllWidgets(context)
        }
    }
}
