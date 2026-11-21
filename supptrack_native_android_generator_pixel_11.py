
#!/usr/bin/env python3
"""
SuppTrack Vegan – Native Android-App Generator (Kotlin + Jetpack Compose + Pixel Widget + In-App Updater)
===========================================================================================================

Dieses Skript erzeugt ein vollständiges, sofort kompilierbares Android-Projekt im Ordner `./SuppTrackNative/`.

Enthaltene Funktionen der nativen Android-App:
1. Echte Hintergrund-Erinnerungen (AlarmManager + BroadcastReceiver + BootReceiver nach Neustart + "Abhaken"-Button direkt in der Benachrichtigung)
2. Tägliches Abhaken & vollständige Verwaltung (Hinzufügen, Anpassen, Entfernen inkl. Tageszeit, Name, Menge, Beschreibung, Uhrzeit, Pflicht/Optional)
3. Interaktiver Monatskalender mit 5-stufiger Farbskala (0%, <40%, <70%, <100%, 100%), Monats-KPIs und Einzeltag-Ansicht
4. Echtes natives Pixel-Homescreen-Widget (AppWidgetProvider) mit Direkt-Abhaken auf dem Startbildschirm & 7-Tage-Farbstreifen
5. Eingebauter In-App-Updater (GitHub Releases oder Direkt-APK-Link + FileProvider-Installer) für nahtlose Updates ohne Datenverlust
6. Fertige GitHub-Actions-Workflow-Datei (.github/workflows/release-apk.yml), um signierte APKs kostenlos in der Cloud ohne Android Studio zu bauen

Verwendung:
    python3 build_supptrack_android.py                 # Erstellt oder aktualisiert das Android-Projekt
    python3 build_supptrack_android.py --gen-keystore  # Erstellt einmalig einen festen Signier-Schlüssel für Updates
"""

import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path

# ==============================================================================
# APP-VERSIONIERUNG (Für zukünftige Updates einfach diese Werte erhöhen!)
# ==============================================================================
APP_VERSION_CODE = 1
APP_VERSION_NAME = "1.0.0"
APP_ID = "com.supptrack.vegan"
PROJECT_DIR = Path("SuppTrackNative")


# ==============================================================================
# PROJEKT-DATEIEN (Gradle, Manifest, Ressourcen, Kotlin-Quellcode, CI/CD)
# ==============================================================================

SETTINGS_GRADLE = r'''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "SuppTrackNative"
include(":app")
'''

ROOT_BUILD_GRADLE = r'''plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}
'''

GRADLE_PROPERTIES = r'''org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
'''

GRADLE_WRAPPER_PROPS = r'''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.9-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
'''

APP_BUILD_GRADLE = f'''import java.io.File

plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}}

android {{
    namespace = "{APP_ID}"
    compileSdk = 35

    defaultConfig {{
        applicationId = "{APP_ID}"
        minSdk = 26
        targetSdk = 35
        versionCode = {APP_VERSION_CODE}
        versionName = "{APP_VERSION_NAME}"
    }}

    signingConfigs {{
        create("release") {{
            val ksPath = System.getenv("KEYSTORE_FILE") ?: "../keystore/supptrack-release.jks"
            val ksFile = file(ksPath)
            if (ksFile.exists()) {{
                storeFile = ksFile
                storePassword = System.getenv("KEYSTORE_PASSWORD") ?: "supptrack123"
                keyAlias = System.getenv("KEY_ALIAS") ?: "supptrack"
                keyPassword = System.getenv("KEY_PASSWORD") ?: "supptrack123"
            }}
        }}
    }}

    buildTypes {{
        release {{
            isMinifyEnabled = false
            val ksPath = System.getenv("KEYSTORE_FILE") ?: "../keystore/supptrack-release.jks"
            signingConfig = if (file(ksPath).exists()) {{
                signingConfigs.getByName("release")
            }} else {{
                signingConfigs.getByName("debug")
            }}
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }}
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlinOptions {{
        jvmTarget = "17"
    }}

    buildFeatures {{
        compose = true
        buildConfig = true
    }}
}}

dependencies {{
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
}}
'''

PROGUARD_RULES = r'''# Keep standard Android classes and JSON structures
-keep class com.supptrack.vegan.** { *; }
'''

ANDROID_MANIFEST = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Benachrichtigungen (Android 13+) & exakte Wecker -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.VIBRATE" />

    <!-- Optional: Für In-App-Updates über GitHub Releases / Direkt-URL -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.SuppTrack">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- Natives Pixel-Homescreen-Widget -->
        <receiver
            android:name=".SupplementWidgetProvider"
            android:exported="true"
            android:label="@string/widget_name">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
                <action android:name="{APP_ID}.ACTION_TOGGLE_SUPP" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/widget_supptrack_info" />
        </receiver>

        <!-- Empfänger für tägliche Erinnerungen & Notification-Aktion "Abhaken" -->
        <receiver
            android:name=".ReminderReceiver"
            android:exported="false" />

        <!-- Stellt Wecker nach Neustart oder Zeitumstellung wieder her -->
        <receiver
            android:name=".BootReceiver"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.TIME_SET" />
                <action android:name="android.intent.action.TIMEZONE_CHANGED" />
            </intent-filter>
        </receiver>

        <!-- FileProvider für In-App APK-Update-Installation -->
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${{applicationId}}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>

    </application>
</manifest>
'''

STRINGS_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">SuppTrack Vegan</string>
    <string name="widget_name">SuppTrack · Tages-Widget</string>
    <string name="widget_description">Zeigt deinen täglichen Supplement-Fortschritt mit Direkt-Abhaken &amp; 7-Tage-Farbskala.</string>
</resources>
'''

THEMES_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.SuppTrack" parent="android:Theme.Material.Light.NoActionBar">
        <item name="android:statusBarColor">#FF1B4332</item>
    </style>
</resources>
'''

COLORS_LIGHT_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="widget_surface">#F5FFFFFF</color>
    <color name="widget_border">#D8E4DD</color>
    <color name="widget_item_bg">#F2F7F4</color>
    <color name="widget_text_primary">#111827</color>
    <color name="widget_text_secondary">#4B5563</color>
    <color name="widget_accent">#2D6A4F</color>
</resources>
'''

COLORS_NIGHT_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="widget_surface">#F219221D</color>
    <color name="widget_border">#2B3B32</color>
    <color name="widget_item_bg">#222F28</color>
    <color name="widget_text_primary">#F3F4F6</color>
    <color name="widget_text_secondary">#9CA3AF</color>
    <color name="widget_accent">#52B788</color>
</resources>
'''

FILE_PATHS_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<paths>
    <cache-path name="updates" path="updates/" />
</paths>
'''

WIDGET_INFO_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/widget_description"
    android:initialLayout="@layout/widget_supptrack"
    android:minWidth="250dp"
    android:minHeight="140dp"
    android:minResizeWidth="180dp"
    android:minResizeHeight="110dp"
    android:resizeMode="horizontal|vertical"
    android:targetCellWidth="4"
    android:targetCellHeight="3"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
'''

# Launcher & Notification Vector Icons
IC_LAUNCHER_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
'''

IC_LAUNCHER_BG_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#1B4332" />
</shape>
'''

IC_LAUNCHER_FG_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:pathData="M54,24 L54,84"
        android:strokeWidth="6"
        android:strokeColor="#86EFAC"
        android:strokeLineCap="round" />
    <path
        android:pathData="M54,24 C34,24 28,48 54,84 C80,48 74,24 54,24 Z"
        android:strokeWidth="6"
        android:strokeColor="#86EFAC"
        android:strokeLineJoin="round" />
</vector>
'''

IC_STAT_LEAF_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M12,2C7.5,2 4,6 4,10.5C4,14.5 7,18 12,22C17,18 20,14.5 20,10.5C20,6 16.5,2 12,2ZM13,17.2V11H11V17.2C8.2,14.9 6.5,12.7 6.5,10.5C6.5,7.4 8.9,4.5 12,4.5C15.1,4.5 17.5,7.4 17.5,10.5C17.5,12.7 15.8,14.9 13,17.2Z" />
</vector>
'''

# Widget Drawables
WIDGET_BG_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_surface" />
    <stroke android:width="1dp" android:color="@color/widget_border" />
    <corners android:radius="24dp" />
</shape>
'''

WIDGET_ITEM_BG_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_item_bg" />
    <corners android:radius="14dp" />
</shape>
'''

WIDGET_BADGE_BG_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_accent" />
    <corners android:radius="12dp" />
</shape>
'''

def make_dot_drawable(color_hex: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="{color_hex}" />
    <corners android:radius="4dp" />
</shape>
'''

WIDGET_LAYOUT_XML = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/widget_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/widget_bg"
    android:orientation="vertical"
    android:padding="14dp">

    <!-- Kopfzeile (Tipp öffnet die App) -->
    <LinearLayout
        android:id="@+id/widget_header"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:gravity="center_vertical"
        android:orientation="horizontal">

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:orientation="vertical">

            <TextView
                android:id="@+id/widget_subtitle"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="SUPPTRACK · HEUTE"
                android:textColor="@color/widget_accent"
                android:textSize="10sp"
                android:textStyle="bold" />

            <TextView
                android:id="@+id/widget_title"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="0/0 erledigt"
                android:textColor="@color/widget_text_primary"
                android:textSize="15sp"
                android:textStyle="bold" />
        </LinearLayout>

        <TextView
            android:id="@+id/widget_pct_badge"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:background="@drawable/widget_badge_bg"
            android:paddingLeft="10dp"
            android:paddingTop="5dp"
            android:paddingRight="10dp"
            android:paddingBottom="5dp"
            android:text="0%"
            android:textColor="#FFFFFF"
            android:textSize="12sp"
            android:textStyle="bold" />
    </LinearLayout>

    <!-- Interaktive offene Supplemente (Direkt auf Homescreen abhakbar) -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_marginTop="8dp"
        android:layout_marginBottom="8dp"
        android:layout_weight="1"
        android:gravity="center_vertical"
        android:orientation="vertical">

        <TextView
            android:id="@+id/widget_empty_msg"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:gravity="center"
            android:padding="8dp"
            android:text="🎉 Alle heutigen Supplemente erledigt!"
            android:textColor="@color/widget_accent"
            android:textSize="13sp"
            android:textStyle="bold"
            android:visibility="gone" />

        <TextView
            android:id="@+id/widget_row_0"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginBottom="4dp"
            android:background="@drawable/widget_item_bg"
            android:ellipsize="end"
            android:maxLines="1"
            android:paddingLeft="10dp"
            android:paddingTop="6dp"
            android:paddingRight="10dp"
            android:paddingBottom="6dp"
            android:textColor="@color/widget_text_primary"
            android:textSize="12sp"
            android:textStyle="bold"
            android:visibility="gone" />

        <TextView
            android:id="@+id/widget_row_1"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginBottom="4dp"
            android:background="@drawable/widget_item_bg"
            android:ellipsize="end"
            android:maxLines="1"
            android:paddingLeft="10dp"
            android:paddingTop="6dp"
            android:paddingRight="10dp"
            android:paddingBottom="6dp"
            android:textColor="@color/widget_text_primary"
            android:textSize="12sp"
            android:textStyle="bold"
            android:visibility="gone" />

        <TextView
            android:id="@+id/widget_row_2"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginBottom="4dp"
            android:background="@drawable/widget_item_bg"
            android:ellipsize="end"
            android:maxLines="1"
            android:paddingLeft="10dp"
            android:paddingTop="6dp"
            android:paddingRight="10dp"
            android:paddingBottom="6dp"
            android:textColor="@color/widget_text_primary"
            android:textSize="12sp"
            android:textStyle="bold"
            android:visibility="gone" />

        <TextView
            android:id="@+id/widget_row_3"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:background="@drawable/widget_item_bg"
            android:ellipsize="end"
            android:maxLines="1"
            android:paddingLeft="10dp"
            android:paddingTop="6dp"
            android:paddingRight="10dp"
            android:paddingBottom="6dp"
            android:textColor="@color/widget_text_primary"
            android:textSize="12sp"
            android:textStyle="bold"
            android:visibility="gone" />
    </LinearLayout>

    <!-- 7-Tage-Farbskala -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal">

        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_0" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_0" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Mo" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_1" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_1" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Di" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_2" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_2" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Mi" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_3" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_3" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Do" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_4" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_4" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Fr" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical" android:paddingRight="2dp">
            <ImageView android:id="@+id/day_bar_5" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_5" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Sa" android:textColor="@color/widget_text_secondary" android:textSize="9sp" />
        </LinearLayout>
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:gravity="center" android:orientation="vertical">
            <ImageView android:id="@+id/day_bar_6" android:layout_width="match_parent" android:layout_height="6dp" android:src="@drawable/dot_gray" android:contentDescription="@null" />
            <TextView android:id="@+id/day_lbl_6" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="So" android:textColor="@color/widget_accent" android:textSize="9sp" android:textStyle="bold" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
'''

# ==============================================================================
# KOTLIN-QUELLCODE
# ==============================================================================

MODELS_AND_REPO_KT = f'''package {APP_ID}

import android.content.Context
import android.content.Intent
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/**
 * Tageszeit-Kategorien für den Einnahmeplan.
 */
enum class DaySlot(val key: String, val label: String, val emoji: String, val order: Int) {{
    MORNING("morning", "Morgens (nüchtern)", "🌅", 1),
    MEAL("meal", "Hauptmahlzeit (fetthaltig)", "🍽️", 2),
    WORKOUT("workout", "Training / Situativ", "🏃", 3),
    EVENING("evening", "Abends (Regeneration)", "🌙", 4);

    companion object {{
        fun fromKey(key: String): DaySlot = entries.firstOrNull {{ it.key == key }} ?: MEAL
    }}
}}

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
class SupplementRepository(private val context: Context) {{

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {{
        private const val PREFS_NAME = "supptrack_native_prefs_v1"
        private const val KEY_SUPPLEMENTS = "supplements_json"
        private const val KEY_LOGS = "logs_json"
        private const val KEY_DARK_MODE = "dark_mode"
        private const val KEY_UPDATE_REPO = "update_github_repo"
        private const val KEY_DIRECT_APK_URL = "update_direct_url"
        const val ACTION_DATA_UPDATED = "{APP_ID}.ACTION_DATA_UPDATED"

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
    }}

    fun getSupplements(): List<Supplement> {{
        val raw = prefs.getString(KEY_SUPPLEMENTS, null) ?: return defaultSupplements()
        return try {{
            val arr = JSONArray(raw)
            val list = mutableListOf<Supplement>()
            for (i in 0 until arr.length()) {{
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
            }}
            list
        }} catch (_: Exception) {{
            defaultSupplements()
        }}
    }}

    fun saveSupplements(list: List<Supplement>) {{
        val arr = JSONArray()
        list.forEach {{ s ->
            arr.put(JSONObject().apply {{
                put("id", s.id)
                put("name", s.name)
                put("dose", s.dose)
                put("slot", s.slot.key)
                put("time", s.time)
                put("reminderEnabled", s.reminderEnabled)
                put("required", s.required)
                put("active", s.active)
                put("note", s.note)
            }})
        }}
        prefs.edit().putString(KEY_SUPPLEMENTS, arr.toString()).apply()
        notifySystemChanged(rescheduleAlarms = true)
    }}

    fun upsertSupplement(supp: Supplement) {{
        val current = getSupplements().toMutableList()
        val idx = current.indexOfFirst {{ it.id == supp.id }}
        if (idx >= 0) {{
            current[idx] = supp
        }} else {{
            current.add(supp)
        }}
        saveSupplements(current)
    }}

    fun deleteSupplement(suppId: String) {{
        val updatedSupps = getSupplements().filterNot {{ it.id == suppId }}
        // Veraltete Häkchen aus dem Verlauf bereinigen
        val logs = getAllLogs().toMutableMap()
        logs.keys.toList().forEach {{ dayKey ->
            val set = logs[dayKey]?.filterNot {{ it == suppId }}?.toSet() ?: emptySet()
            logs[dayKey] = set
        }}
        saveLogsInternal(logs)
        saveSupplements(updatedSupps)
    }}

    fun getAllLogs(): Map<String, Set<String>> {{
        val raw = prefs.getString(KEY_LOGS, null) ?: return emptyMap()
        return try {{
            val obj = JSONObject(raw)
            val result = mutableMapOf<String, Set<String>>()
            val keys = obj.keys()
            while (keys.hasNext()) {{
                val dayKey = keys.next()
                val arr = obj.optJSONArray(dayKey) ?: continue
                val set = mutableSetOf<String>()
                for (i in 0 until arr.length()) {{
                    set.add(arr.getString(i))
                }}
                result[dayKey] = set
            }}
            result
        }} catch (_: Exception) {{
            emptyMap()
        }}
    }}

    private fun saveLogsInternal(logs: Map<String, Set<String>>) {{
        val obj = JSONObject()
        logs.forEach {{ (dayKey, set) ->
            if (set.isNotEmpty()) {{
                val arr = JSONArray()
                set.forEach {{ arr.put(it) }}
                obj.put(dayKey, arr)
            }}
        }}
        prefs.edit().putString(KEY_LOGS, obj.toString()).apply()
    }}

    fun getDayChecks(date: LocalDate): Set<String> {{
        return getAllLogs()[date.format(DATE_FMT)] ?: emptySet()
    }}

    fun toggleCheck(date: LocalDate, suppId: String): Boolean {{
        val key = date.format(DATE_FMT)
        val logs = getAllLogs().toMutableMap()
        val current = (logs[key] ?: emptySet()).toMutableSet()
        val nowChecked = if (current.contains(suppId)) {{
            current.remove(suppId)
            false
        }} else {{
            current.add(suppId)
            true
        }}
        logs[key] = current
        saveLogsInternal(logs)
        notifySystemChanged(rescheduleAlarms = false)
        return nowChecked
    }}

    fun setManyChecked(date: LocalDate, suppIds: List<String>, checked: Boolean) {{
        val key = date.format(DATE_FMT)
        val logs = getAllLogs().toMutableMap()
        val current = (logs[key] ?: emptySet()).toMutableSet()
        if (checked) current.addAll(suppIds) else current.removeAll(suppIds.toSet())
        logs[key] = current
        saveLogsInternal(logs)
        notifySystemChanged(rescheduleAlarms = false)
    }}

    fun getDayStats(date: LocalDate, supps: List<Supplement> = getSupplements(), logs: Map<String, Set<String>> = getAllLogs()): DayStats {{
        val checks = logs[date.format(DATE_FMT)] ?: emptySet()
        val reqList = supps.filter {{ it.active && it.required }}
        val optList = supps.filter {{ it.active && !it.required }}
        val reqDone = reqList.count {{ checks.contains(it.id) }}
        val optDone = optList.count {{ checks.contains(it.id) }}
        val totalReq = reqList.size
        val pct = if (totalReq == 0) 0 else Math.round((reqDone * 100f) / totalReq)
        return DayStats(reqDone, totalReq, optDone, pct)
    }}

    fun calculateStreak(supps: List<Supplement> = getSupplements(), logs: Map<String, Set<String>> = getAllLogs()): Int {{
        var streak = 0
        var cursor = LocalDate.now()
        val todayStats = getDayStats(cursor, supps, logs)
        if (todayStats.totalReq > 0 && todayStats.pct == 100) {{
            streak = 1
        }}
        cursor = cursor.minusDays(1)
        repeat(365) {{
            val st = getDayStats(cursor, supps, logs)
            if (st.totalReq > 0 && st.pct == 100) {{
                streak++
                cursor = cursor.minusDays(1)
            }} else {{
                return streak
            }}
        }}
        return streak
    }}

    fun isDarkMode(systemDefault: Boolean): Boolean =
        if (prefs.contains(KEY_DARK_MODE)) prefs.getBoolean(KEY_DARK_MODE, systemDefault) else systemDefault

    fun setDarkMode(enabled: Boolean) {{
        prefs.edit().putBoolean(KEY_DARK_MODE, enabled).apply()
    }}

    fun getUpdateRepo(): String = prefs.getString(KEY_UPDATE_REPO, "") ?: ""
    fun setUpdateRepo(repo: String) {{
        prefs.edit().putString(KEY_UPDATE_REPO, repo.trim()).apply()
    }}

    fun getDirectApkUrl(): String = prefs.getString(KEY_DIRECT_APK_URL, "") ?: ""
    fun setDirectApkUrl(url: String) {{
        prefs.edit().putString(KEY_DIRECT_APK_URL, url.trim()).apply()
    }}

    fun exportBackupJson(): String {{
        val root = JSONObject()
        val suppsArr = JSONArray()
        getSupplements().forEach {{ s ->
            suppsArr.put(JSONObject().apply {{
                put("id", s.id)
                put("name", s.name)
                put("dose", s.dose)
                put("slot", s.slot.key)
                put("time", s.time)
                put("reminderEnabled", s.reminderEnabled)
                put("required", s.required)
                put("active", s.active)
                put("note", s.note)
            }})
        }}
        val logsObj = JSONObject()
        getAllLogs().forEach {{ (k, v) ->
            val a = JSONArray()
            v.forEach {{ a.put(it) }}
            logsObj.put(k, a)
        }}
        root.put("supplements", suppsArr)
        root.put("logs", logsObj)
        return root.toString(2)
    }}

    fun importBackupJson(jsonText: String): Boolean {{
        return try {{
            val root = JSONObject(jsonText)
            val suppsArr = root.getJSONArray("supplements")
            val parsedSupps = mutableListOf<Supplement>()
            for (i in 0 until suppsArr.length()) {{
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
            }}
            val parsedLogs = mutableMapOf<String, Set<String>>()
            val logsObj = root.optJSONObject("logs")
            if (logsObj != null) {{
                val keys = logsObj.keys()
                while (keys.hasNext()) {{
                    val k = keys.next()
                    val a = logsObj.getJSONArray(k)
                    val s = mutableSetOf<String>()
                    for (i in 0 until a.length()) s.add(a.getString(i))
                    parsedLogs[k] = s
                }}
            }}
            saveLogsInternal(parsedLogs)
            saveSupplements(parsedSupps)
            true
        }} catch (_: Exception) {{
            false
        }}
    }}

    fun resetToDefault() {{
        saveLogsInternal(emptyMap())
        saveSupplements(defaultSupplements())
    }}

    private fun notifySystemChanged(rescheduleAlarms: Boolean) {{
        if (rescheduleAlarms) {{
            ReminderScheduler.rescheduleAll(context)
        }}
        SupplementWidgetProvider.updateAllWidgets(context)
        context.sendBroadcast(Intent(ACTION_DATA_UPDATED).setPackage(context.packageName))
    }}
}}
'''

REMINDERS_KT = f'''package {APP_ID}

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
object ReminderScheduler {{
    const val CHANNEL_ID = "supptrack_reminders_channel"
    const val ACTION_TRIGGER_REMINDER = "{APP_ID}.ACTION_TRIGGER_REMINDER"
    const val ACTION_MARK_TIME_DONE = "{APP_ID}.ACTION_MARK_TIME_DONE"
    const val EXTRA_TIME = "extra_time"
    private const val PREFS_ALARMS = "supptrack_alarms_registry"
    private const val KEY_TIMES = "scheduled_times"

    fun ensureChannel(context: Context) {{
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Supplement-Erinnerungen",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {{
            description = "Tägliche Erinnerungen für deine veganen Supplemente"
            enableVibration(true)
        }}
        nm.createNotificationChannel(channel)
    }}

    fun rescheduleAll(context: Context) {{
        ensureChannel(context)
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val regPrefs = context.getSharedPreferences(PREFS_ALARMS, Context.MODE_PRIVATE)

        // Alte Alarme sauber abmelden
        val oldTimes = regPrefs.getStringSet(KEY_TIMES, emptySet()) ?: emptySet()
        oldTimes.forEach {{ timeStr ->
            val pi = buildTriggerPendingIntent(context, timeStr)
            alarmManager.cancel(pi)
        }}

        // Neue eindeutige Zeiten sammeln
        val repo = SupplementRepository(context)
        val newTimes = repo.getSupplements()
            .filter {{ it.active && it.reminderEnabled && it.time.matches(Regex("^\\\\d{{2}}:\\\\d{{2}}$")) }}
            .map {{ it.time }}
            .toSet()

        regPrefs.edit().putStringSet(KEY_TIMES, newTimes).apply()

        newTimes.forEach {{ timeStr ->
            scheduleForTime(context, timeStr, forceNextDay = false)
        }}
    }}

    fun scheduleForTime(context: Context, timeStr: String, forceNextDay: Boolean) {{
        val parts = timeStr.split(":")
        if (parts.size != 2) return
        val hour = parts[0].toIntOrNull() ?: return
        val minute = parts[1].toIntOrNull() ?: return

        val cal = Calendar.getInstance().apply {{
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (forceNextDay || timeInMillis <= System.currentTimeMillis() + 3000L) {{
                add(Calendar.DAY_OF_YEAR, 1)
            }}
        }}

        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = buildTriggerPendingIntent(context, timeStr)

        try {{
            val canExact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()
            if (canExact) {{
                alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
            }} else {{
                alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
            }}
        }} catch (_: SecurityException) {{
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
        }}
    }}

    private fun buildTriggerPendingIntent(context: Context, timeStr: String): PendingIntent {{
        val intent = Intent(context, ReminderReceiver::class.java).apply {{
            action = ACTION_TRIGGER_REMINDER
            putExtra(EXTRA_TIME, timeStr)
        }}
        return PendingIntent.getBroadcast(
            context,
            timeStr.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }}

    fun showNotification(context: Context, title: String, body: String, timeTag: String?, notifId: Int) {{
        ensureChannel(context)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {{
            return
        }}

        val openAppIntent = Intent(context, MainActivity::class.java).apply {{
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }}
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
        if (timeTag != null) {{
            val doneIntent = Intent(context, ReminderReceiver::class.java).apply {{
                action = ACTION_MARK_TIME_DONE
                putExtra(EXTRA_TIME, timeTag)
            }}
            val donePi = PendingIntent.getBroadcast(
                context,
                notifId + 9000,
                doneIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.addAction(R.drawable.ic_stat_leaf, "Alle abhaken ✓", donePi)
        }}

        NotificationManagerCompat.from(context).notify(notifId, builder.build())
    }}
}}

class ReminderReceiver : BroadcastReceiver() {{
    override fun onReceive(context: Context, intent: Intent) {{
        val timeStr = intent.getStringExtra(ReminderScheduler.EXTRA_TIME) ?: return
        val repo = SupplementRepository(context)
        val today = LocalDate.now()

        when (intent.action) {{
            ReminderScheduler.ACTION_TRIGGER_REMINDER -> {{
                // Sofort für morgen neu planen
                ReminderScheduler.scheduleForTime(context, timeStr, forceNextDay = true)

                val checkedToday = repo.getDayChecks(today)
                val dueSupps = repo.getSupplements().filter {{
                    it.active && it.reminderEnabled && it.time == timeStr && !checkedToday.contains(it.id)
                }}

                if (dueSupps.isNotEmpty()) {{
                    val body = dueSupps.joinToString("\\n") {{ "• ${{it.name}} (${{it.dose}})" }}
                    ReminderScheduler.showNotification(
                        context = context,
                        title = "⏰ Supplemente ($timeStr Uhr)",
                        body = body,
                        timeTag = timeStr,
                        notifId = timeStr.hashCode()
                    )
                }}
            }}

            ReminderScheduler.ACTION_MARK_TIME_DONE -> {{
                val matchingIds = repo.getSupplements()
                    .filter {{ it.active && it.reminderEnabled && it.time == timeStr }}
                    .map {{ it.id }}
                repo.setManyChecked(today, matchingIds, checked = true)
                NotificationManagerCompat.from(context).cancel(timeStr.hashCode())
            }}
        }}
    }}
}}

class BootReceiver : BroadcastReceiver() {{
    override fun onReceive(context: Context, intent: Intent) {{
        if (intent.action in listOf(
                Intent.ACTION_BOOT_COMPLETED,
                Intent.ACTION_TIME_CHANGED,
                Intent.ACTION_TIMEZONE_CHANGED
            )
        ) {{
            ReminderScheduler.rescheduleAll(context)
            SupplementWidgetProvider.updateAllWidgets(context)
        }}
    }}
}}
'''

WIDGET_PROVIDER_KT = f'''package {APP_ID}

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
class SupplementWidgetProvider : AppWidgetProvider() {{

    companion object {{
        const val ACTION_TOGGLE_SUPP = "{APP_ID}.ACTION_TOGGLE_SUPP"
        const val EXTRA_SUPP_ID = "extra_supp_id"

        fun updateAllWidgets(context: Context) {{
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, SupplementWidgetProvider::class.java)
            val ids = manager.getAppWidgetIds(component)
            ids.forEach {{ id ->
                updateSingleWidget(context, manager, id)
            }}
        }}

        private fun dotDrawableForPct(pct: Int): Int = when {{
            pct == 0 -> R.drawable.dot_gray
            pct < 40 -> R.drawable.dot_rose
            pct < 70 -> R.drawable.dot_amber
            pct < 100 -> R.drawable.dot_lime
            else -> R.drawable.dot_emerald
        }}

        fun updateSingleWidget(context: Context, manager: AppWidgetManager, widgetId: Int) {{
            val repo = SupplementRepository(context)
            val supps = repo.getSupplements()
            val logs = repo.getAllLogs()
            val today = LocalDate.now()
            val stats = repo.getDayStats(today, supps, logs)
            val streak = repo.calculateStreak(supps, logs)
            val todayChecks = logs[today.format(SupplementRepository.DATE_FMT)] ?: emptySet()

            val views = RemoteViews(context.packageName, R.layout.widget_supptrack)

            // Kopfzeile -> App öffnen
            val openIntent = Intent(context, MainActivity::class.java).apply {{
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }}
            val openPi = PendingIntent.getActivity(
                context,
                0,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(R.id.widget_header, openPi)

            views.setTextViewText(R.id.widget_subtitle, "SUPPTRACK · 🔥 $streak d SERIE")
            views.setTextViewText(R.id.widget_title, "${{stats.reqDone}}/${{stats.totalReq}} Pflicht erledigt")
            views.setTextViewText(R.id.widget_pct_badge, if (stats.pct == 100 && stats.totalReq > 0) "✓ 100%" else "${{stats.pct}}%")

            // Bis zu 4 offene aktive Supplemente direkt abhakbar machen
            val openSupps = supps
                .filter {{ it.active && !todayChecks.contains(it.id) }}
                .sortedWith(compareBy<Supplement> {{ !it.required }}.thenBy {{ it.slot.order }}.thenBy {{ it.time }})
                .take(4)

            val rowIds = listOf(R.id.widget_row_0, R.id.widget_row_1, R.id.widget_row_2, R.id.widget_row_3)

            if (openSupps.isEmpty()) {{
                views.setViewVisibility(R.id.widget_empty_msg, View.VISIBLE)
                rowIds.forEach {{ views.setViewVisibility(it, View.GONE) }}
            }} else {{
                views.setViewVisibility(R.id.widget_empty_msg, View.GONE)
                rowIds.forEachIndexed {{ index, rowViewId ->
                    if (index < openSupps.size) {{
                        val supp = openSupps[index]
                        views.setViewVisibility(rowViewId, View.VISIBLE)
                        views.setTextViewText(rowViewId, "○  ${{supp.name}} · ${{supp.dose}}")

                        val toggleIntent = Intent(context, SupplementWidgetProvider::class.java).apply {{
                            action = ACTION_TOGGLE_SUPP
                            putExtra(EXTRA_SUPP_ID, supp.id)
                        }}
                        val togglePi = PendingIntent.getBroadcast(
                            context,
                            500 + index,
                            toggleIntent,
                            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                        )
                        views.setOnClickPendingIntent(rowViewId, togglePi)
                    }} else {{
                        views.setViewVisibility(rowViewId, View.GONE)
                    }}
                }}
            }}

            // 7-Tage-Farbskala aktualisieren
            val barIds = listOf(
                R.id.day_bar_0, R.id.day_bar_1, R.id.day_bar_2,
                R.id.day_bar_3, R.id.day_bar_4, R.id.day_bar_5, R.id.day_bar_6
            )
            val lblIds = listOf(
                R.id.day_lbl_0, R.id.day_lbl_1, R.id.day_lbl_2,
                R.id.day_lbl_3, R.id.day_lbl_4, R.id.day_lbl_5, R.id.day_lbl_6
            )

            for (i in 0..6) {{
                val d = today.minusDays((6 - i).toLong())
                val st = repo.getDayStats(d, supps, logs)
                val shortWd = d.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.GERMAN).take(2)
                views.setImageViewResource(barIds[i], dotDrawableForPct(st.pct))
                views.setTextViewText(lblIds[i], shortWd)
            }}

            manager.updateAppWidget(widgetId, views)
        }}
    }}

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {{
        appWidgetIds.forEach {{ id ->
            updateSingleWidget(context, appWidgetManager, id)
        }}
    }}

    override fun onReceive(context: Context, intent: Intent) {{
        super.onReceive(context, intent)
        if (intent.action == ACTION_TOGGLE_SUPP) {{
            val suppId = intent.getStringExtra(EXTRA_SUPP_ID) ?: return
            val repo = SupplementRepository(context)
            repo.toggleCheck(LocalDate.now(), suppId)
        }}
    }}
}}
'''

UPDATE_MANAGER_KT = f'''package {APP_ID}

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

data class ReleaseInfo(
    val tagName: String,
    val title: String,
    val notes: String,
    val apkDownloadUrl: String,
    val isNewer: Boolean
)

/**
 * In-App-Updater: Prüft GitHub Releases oder einen Direkt-APK-Link,
 * lädt das signierte APK-Update herunter und startet den Android-Installer.
 */
object UpdateManager {{

    suspend fun checkGitHubRelease(repoPath: String): Result<ReleaseInfo> = withContext(Dispatchers.IO) {{
        runCatching {{
            val cleanRepo = repoPath.trim().removePrefix("https://github.com/").trim('/')
            require(cleanRepo.contains("/")) {{ "Bitte im Format benutzername/repository eingeben." }}

            val url = URL("https://api.github.com/repos/$cleanRepo/releases/latest")
            val conn = (url.openConnection() as HttpURLConnection).apply {{
                requestMethod = "GET"
                connectTimeout = 10_000
                readTimeout = 10_000
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "SuppTrack-Android/${{BuildConfig.VERSION_NAME}}")
            }}

            if (conn.responseCode != 200) {{
                throw IllegalStateException("GitHub API Antwort: HTTP ${{conn.responseCode}} (Repo öffentlich & Release vorhanden?)")
            }}

            val bodyText = conn.inputStream.bufferedReader().use {{ it.readText() }}
            val json = JSONObject(bodyText)
            val tag = json.optString("tag_name", "0.0.0")
            val name = json.optString("name", tag)
            val notes = json.optString("body", "Keine Änderungsnotizen hinterlegt.")
            val assets = json.optJSONArray("assets")

            var apkUrl = ""
            if (assets != null) {{
                for (i in 0 until assets.length()) {{
                    val a = assets.getJSONObject(i)
                    val dl = a.optString("browser_download_url", "")
                    if (dl.endsWith(".apk", ignoreCase = true)) {{
                        apkUrl = dl
                        break
                    }}
                }}
            }}
            require(apkUrl.isNotBlank()) {{ "Im neuesten Release wurde keine .apk-Datei gefunden." }}

            ReleaseInfo(
                tagName = tag,
                title = name,
                notes = notes,
                apkDownloadUrl = apkUrl,
                isNewer = isVersionNewer(tag, BuildConfig.VERSION_NAME)
            )
        }}
    }}

    suspend fun downloadApk(
        context: Context,
        downloadUrl: String,
        onProgress: (Float) -> Unit
    ): Result<File> = withContext(Dispatchers.IO) {{
        runCatching {{
            val updatesDir = File(context.cacheDir, "updates").apply {{ mkdirs() }}
            val targetFile = File(updatesDir, "supptrack-update.apk")

            val conn = (URL(downloadUrl).openConnection() as HttpURLConnection).apply {{
                instanceFollowRedirects = true
                connectTimeout = 15_000
                readTimeout = 30_000
                setRequestProperty("User-Agent", "SuppTrack-Android/${{BuildConfig.VERSION_NAME}}")
            }}

            if (conn.responseCode !in 200..299) {{
                throw IllegalStateException("Download fehlgeschlagen (HTTP ${{conn.responseCode}})")
            }}

            val totalBytes = conn.contentLengthLong
            conn.inputStream.use {{ input ->
                FileOutputStream(targetFile).use {{ output ->
                    val buffer = ByteArray(8192)
                    var downloaded = 0L
                    var read: Int
                    while (input.read(buffer).also {{ read = it }} != -1) {{
                        output.write(buffer, 0, read)
                        downloaded += read
                        if (totalBytes > 0) {{
                            onProgress((downloaded.toFloat() / totalBytes).coerceIn(0f, 1f))
                        }}
                    }}
                }}
            }}
            onProgress(1f)
            targetFile
        }}
    }}

    /**
     * Startet die Android-Systeminstallation für das heruntergeladene APK.
     * Gibt false zurück, falls der Nutzer erst "Apps aus dieser Quelle zulassen" aktivieren muss.
     */
    fun triggerApkInstall(context: Context, apkFile: File): Boolean {{
        if (!context.packageManager.canRequestPackageInstalls()) {{
            val settingsIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${{context.packageName}}")
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(settingsIntent)
            return false
        }}

        val uri = FileProvider.getUriForFile(
            context,
            "${{context.packageName}}.fileprovider",
            apkFile
        )
        val installIntent = Intent(Intent.ACTION_VIEW).apply {{
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }}
        context.startActivity(installIntent)
        return true
    }}

    private fun isVersionNewer(remoteTag: String, currentVersion: String): Boolean {{
        val remoteParts = remoteTag.trim().removePrefix("v").removePrefix("V").split(".").map {{ it.toIntOrNull() ?: 0 }}
        val localParts = currentVersion.trim().removePrefix("v").removePrefix("V").split(".").map {{ it.toIntOrNull() ?: 0 }}
        val maxLen = maxOf(remoteParts.size, localParts.size)
        for (i in 0 until maxLen) {{
            val r = remoteParts.getOrElse(i) {{ 0 }}
            val l = localParts.getOrElse(i) {{ 0 }}
            if (r > l) return true
            if (r < l) return false
        }}
        return false
    }}
}}
'''

MAIN_ACTIVITY_KT = f'''package {APP_ID}

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

class MainActivity : ComponentActivity() {{

    private val externalRefreshTick = mutableIntStateOf(0)

    private val dataUpdateReceiver = object : BroadcastReceiver() {{
        override fun onReceive(context: Context?, intent: Intent?) {{
            externalRefreshTick.intValue++
        }}
    }}

    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        ReminderScheduler.rescheduleAll(this)
        SupplementWidgetProvider.updateAllWidgets(this)

        ContextCompat.registerReceiver(
            this,
            dataUpdateReceiver,
            IntentFilter(SupplementRepository.ACTION_DATA_UPDATED),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )

        setContent {{
            SuppTrackRoot(externalRefreshTick = externalRefreshTick.intValue)
        }}
    }}

    override fun onResume() {{
        super.onResume()
        externalRefreshTick.intValue++
    }}

    override fun onDestroy() {{
        super.onDestroy()
        try {{
            unregisterReceiver(dataUpdateReceiver)
        }} catch (_: Exception) {{}}
    }}
}}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SuppTrackRoot(externalRefreshTick: Int) {{
    val context = LocalContext.current
    val repo = remember {{ SupplementRepository(context) }}
    val systemDark = isSystemInDarkTheme()

    var darkMode by remember {{ mutableStateOf(repo.isDarkMode(systemDark)) }}
    var selectedTab by remember {{ mutableIntStateOf(0) }}
    var supplements by remember {{ mutableStateOf(repo.getSupplements()) }}
    var logs by remember {{ mutableStateOf(repo.getAllLogs()) }}

    var activeDate by remember {{ mutableStateOf(LocalDate.now()) }}
    var calYearMonth by remember {{ mutableStateOf(YearMonth.now()) }}
    var calSelectedDate by remember {{ mutableStateOf(LocalDate.now()) }}

    var editingSupplement by remember {{ mutableStateOf<Supplement?>(null) }}
    var showEditDialog by remember {{ mutableStateOf(false) }}
    var deletingSupplement by remember {{ mutableStateOf<Supplement?>(null) }}

    val snackbarHostState = remember {{ SnackbarHostState() }}
    val scope = rememberCoroutineScope()

    fun reload() {{
        supplements = repo.getSupplements()
        logs = repo.getAllLogs()
    }}

    LaunchedEffect(externalRefreshTick) {{
        reload()
    }}

    val colorScheme = if (darkMode) {{
        darkColorScheme(
            primary = SageLight,
            onPrimary = Color(0xFF0A1F15),
            primaryContainer = SageDark,
            onPrimaryContainer = Color(0xFFD8F3DC),
            background = Color(0xFF111513),
            surface = Color(0xFF19201C),
            surfaceVariant = Color(0xFF232E28)
        )
    }} else {{
        lightColorScheme(
            primary = SagePrimary,
            onPrimary = Color.White,
            primaryContainer = Color(0xFFDFECE4),
            onPrimaryContainer = SageDark,
            background = Color(0xFFF6F7F4),
            surface = Color.White,
            surfaceVariant = Color(0xFFECEFE9)
        )
    }}

    MaterialTheme(colorScheme = colorScheme) {{
        Scaffold(
            snackbarHost = {{ SnackbarHost(snackbarHostState) }},
            topBar = {{
                TopAppBar(
                    title = {{
                        Column {{
                            Text("SuppTrack Vegan", fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
                            Text(
                                "Pixel Native · v${{BuildConfig.VERSION_NAME}}",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }}
                    }},
                    actions = {{
                        IconButton(onClick = {{
                            darkMode = !darkMode
                            repo.setDarkMode(darkMode)
                        }}) {{
                            Icon(
                                imageVector = if (darkMode) Icons.Default.LightMode else Icons.Default.DarkMode,
                                contentDescription = "Theme umschalten"
                            )
                        }}
                    }},
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background
                    )
                )
            }},
            bottomBar = {{
                NavigationBar {{
                    NavigationBarItem(
                        selected = selectedTab == 0,
                        onClick = {{ selectedTab = 0 }},
                        icon = {{ Icon(Icons.Default.CheckCircle, contentDescription = null) }},
                        label = {{ Text("Heute") }}
                    )
                    NavigationBarItem(
                        selected = selectedTab == 1,
                        onClick = {{ selectedTab = 1 }},
                        icon = {{ Icon(Icons.Default.DateRange, contentDescription = null) }},
                        label = {{ Text("Kalender") }}
                    )
                    NavigationBarItem(
                        selected = selectedTab == 2,
                        onClick = {{ selectedTab = 2 }},
                        icon = {{ Icon(Icons.Default.Notifications, contentDescription = null) }},
                        label = {{ Text("Wecker") }}
                    )
                    NavigationBarItem(
                        selected = selectedTab == 3,
                        onClick = {{ selectedTab = 3 }},
                        icon = {{ Icon(Icons.Default.SystemUpdate, contentDescription = null) }},
                        label = {{ Text("Updates") }}
                    )
                }}
            }}
        ) {{ padding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .background(MaterialTheme.colorScheme.background)
            ) {{
                when (selectedTab) {{
                    0 -> TodayTab(
                        date = activeDate,
                        supplements = supplements,
                        logs = logs,
                        repo = repo,
                        onDateChange = {{ activeDate = it }},
                        onToggle = {{ id ->
                            val checked = repo.toggleCheck(activeDate, id)
                            reload()
                            if (checked) {{
                                val st = repo.getDayStats(activeDate)
                                if (st.totalReq > 0 && st.pct == 100) {{
                                    scope.launch {{ snackbarHostState.showSnackbar("🎉 100 % Tagesziel erreicht!") }}
                                }}
                            }}
                        }},
                        onToggleSlotAll = {{ slot ->
                            val slotSupps = supplements.filter {{ it.active && it.slot == slot }}
                            val dayChecks = logs[activeDate.format(SupplementRepository.DATE_FMT)] ?: emptySet()
                            val allDone = slotSupps.all {{ dayChecks.contains(it.id) }}
                            repo.setManyChecked(activeDate, slotSupps.map {{ it.id }}, checked = !allDone)
                            reload()
                        }},
                        onAdd = {{
                            editingSupplement = null
                            showEditDialog = true
                        }},
                        onEdit = {{ supp ->
                            editingSupplement = supp
                            showEditDialog = true
                        }},
                        onDelete = {{ supp -> deletingSupplement = supp }}
                    )

                    1 -> CalendarTab(
                        yearMonth = calYearMonth,
                        selectedDate = calSelectedDate,
                        supplements = supplements,
                        logs = logs,
                        repo = repo,
                        onMonthChange = {{ calYearMonth = it }},
                        onSelectDate = {{ calSelectedDate = it }},
                        onToggleDaySupp = {{ date, id ->
                            repo.toggleCheck(date, id)
                            reload()
                        }},
                        onOpenInToday = {{ date ->
                            activeDate = date
                            selectedTab = 0
                        }}
                    )

                    2 -> RemindersTab(
                        supplements = supplements,
                        repo = repo,
                        onAdd = {{
                            editingSupplement = null
                            showEditDialog = true
                        }},
                        onEdit = {{ supp ->
                            editingSupplement = supp
                            showEditDialog = true
                        }},
                        onDelete = {{ supp -> deletingSupplement = supp }},
                        onUpdateSupp = {{ updated ->
                            repo.upsertSupplement(updated)
                            reload()
                        }},
                        onShowMessage = {{ msg ->
                            scope.launch {{ snackbarHostState.showSnackbar(msg) }}
                        }}
                    )

                    3 -> UpdatesAndBackupTab(
                        repo = repo,
                        onReload = {{ reload() }},
                        onShowMessage = {{ msg ->
                            scope.launch {{ snackbarHostState.showSnackbar(msg) }}
                        }}
                    )
                }}
            }}
        }}

        if (showEditDialog) {{
            SupplementEditDialog(
                initial = editingSupplement,
                onDismiss = {{ showEditDialog = false }},
                onSave = {{ saved ->
                    repo.upsertSupplement(saved)
                    reload()
                    showEditDialog = false
                    scope.launch {{ snackbarHostState.showSnackbar("„${{saved.name}}“ gespeichert ✓") }}
                }},
                onDelete = if (editingSupplement != null) {{
                    {{
                        showEditDialog = false
                        deletingSupplement = editingSupplement
                    }}
                }} else null
            )
        }}

        deletingSupplement?.let {{ target ->
            AlertDialog(
                onDismissRequest = {{ deletingSupplement = null }},
                title = {{ Text("„${{target.name}}“ entfernen?") }},
                text = {{ Text("Das Supplement wird dauerhaft aus deinem Plan und aus dem Verlauf entfernt.") }},
                confirmButton = {{
                    Button(
                        onClick = {{
                            repo.deleteSupplement(target.id)
                            reload()
                            deletingSupplement = null
                            scope.launch {{ snackbarHostState.showSnackbar("„${{target.name}}“ entfernt") }}
                        }},
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                    ) {{ Text("Entfernen") }}
                }},
                dismissButton = {{
                    TextButton(onClick = {{ deletingSupplement = null }}) {{ Text("Abbrechen") }}
                }}
            )
        }}
    }}
}}

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
) {{
    val today = LocalDate.now()
    val stats = repo.getDayStats(date, supplements, logs)
    val streak = repo.calculateStreak(supplements, logs)
    val checks = logs[date.format(SupplementRepository.DATE_FMT)] ?: emptySet()
    val activeSupps = supplements.filter {{ it.active }}
    val dateFmt = remember {{ DateTimeFormatter.ofPattern("EEE, d. MMM yyyy", Locale.GERMAN) }}

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {{
        // Datums-Zeile
        item {{
            Card(shape = RoundedCornerShape(20.dp)) {{
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {{
                    IconButton(onClick = {{ onDateChange(date.minusDays(1)) }}) {{
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Zurück")
                    }}
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {{
                        Text(
                            text = if (date == today) "Heute · ${{date.format(dateFmt)}}" else date.format(dateFmt),
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                        if (date != today) {{
                            TextButton(onClick = {{ onDateChange(today) }}, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)) {{
                                Text("Heute", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }}
                        }}
                    }}
                    IconButton(onClick = {{ onDateChange(date.plusDays(1)) }}) {{
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Vor")
                    }}
                }}
            }}
        }}

        // Fortschritts-Hero-Card
        item {{
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = SageDark, contentColor = Color.White)
            ) {{
                Row(
                    modifier = Modifier.fillMaxWidth().padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {{
                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {{
                        Text(
                            text = when {{
                                stats.totalReq == 0 -> "Keine Pflicht-Supplemente aktiv"
                                stats.pct == 100 -> "✅ Perfekt! Tagesziel erreicht"
                                stats.pct >= 50 -> "💪 Auf sehr gutem Kurs"
                                else -> "🎯 Tagesziel läuft"
                            }},
                            fontSize = 12.sp,
                            color = Color(0xFFD8F3DC),
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = "${{stats.reqDone}} / ${{stats.totalReq}} Pflicht",
                            fontSize = 24.sp,
                            fontWeight = FontWeight.ExtraBold
                        )
                        Text(
                            text = "🔥 Serie: $streak ${{if (streak == 1) "Tag" else "Tage"}}",
                            fontSize = 12.sp,
                            color = Color(0xFFB7E4C7)
                        )
                    }}

                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(72.dp)) {{
                        CircularProgressIndicator(
                            progress = {{ stats.pct / 100f }},
                            modifier = Modifier.fillMaxSize(),
                            strokeWidth = 7.dp,
                            color = if (stats.pct == 100) Color(0xFF4ADE80) else Color(0xFFFDE047),
                            trackColor = Color.White.copy(alpha = 0.2f)
                        )
                        Text("${{stats.pct}}%", fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
                    }}
                }}
            }}
        }}

        // Slots gruppiert
        DaySlot.entries.sortedBy {{ it.order }}.forEach {{ slot ->
            val itemsInSlot = activeSupps.filter {{ it.slot == slot }}
            if (itemsInSlot.isNotEmpty()) {{
                val allChecked = itemsInSlot.all {{ checks.contains(it.id) }}
                item(key = "header_${{slot.key}}") {{
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp, start = 4.dp, end = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {{
                        Text(
                            text = "${{slot.emoji}} ${{slot.label}}",
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = if (allChecked) "Alle aufheben" else "Alle abhaken",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.clickable {{ onToggleSlotAll(slot) }}.padding(4.dp)
                        )
                    }}
                }}

                items(itemsInSlot, key = {{ it.id }}) {{ supp ->
                    val isDone = checks.contains(supp.id)
                    Card(
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (isDone) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                            else MaterialTheme.colorScheme.surface
                        )
                    ) {{
                        Column(modifier = Modifier.fillMaxWidth()) {{
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {{ onToggle(supp.id) }}
                                    .padding(14.dp),
                                verticalAlignment = Alignment.Top,
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {{
                                Box(
                                    modifier = Modifier
                                        .size(26.dp)
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isDone) SagePrimary else Color.Transparent)
                                        .border(2.dp, if (isDone) SagePrimary else MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp)),
                                    contentAlignment = Alignment.Center
                                ) {{
                                    if (isDone) {{
                                        Icon(Icons.Default.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                                    }}
                                }}

                                Column(modifier = Modifier.weight(1f)) {{
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {{
                                        Text(
                                            text = supp.name,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 15.sp,
                                            textDecoration = if (isDone) TextDecoration.LineThrough else TextDecoration.None,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                            modifier = Modifier.weight(1f, fill = false)
                                        )
                                        if (!supp.required) {{
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
                                        }}
                                    }}
                                    Text(
                                        text = supp.dose,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                    if (supp.note.isNotBlank()) {{
                                        Text(
                                            text = supp.note,
                                            fontSize = 11.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.padding(top = 3.dp)
                                        )
                                    }}
                                }}
                            }}

                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))

                            Row(
                                modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {{
                                Text(
                                    text = if (supp.reminderEnabled) "⏰ ${{supp.time}} Uhr" else "Kein Wecker",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {{
                                    TextButton(
                                        onClick = {{ onEdit(supp) }},
                                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp)
                                    ) {{
                                        Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(14.dp))
                                        Spacer(Modifier.width(4.dp))
                                        Text("Anpassen", fontSize = 11.sp)
                                    }}
                                    IconButton(onClick = {{ onDelete(supp) }}, modifier = Modifier.size(32.dp)) {{
                                        Icon(Icons.Default.Delete, contentDescription = "Entfernen", tint = Color(0xFFDC2626), modifier = Modifier.size(16.dp))
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}

        item {{
            OutlinedButton(
                onClick = onAdd,
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                shape = RoundedCornerShape(18.dp)
            ) {{
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Neues Supplement hinzufügen", fontWeight = FontWeight.Bold)
            }}
        }}
    }}
}}

// ==============================================================================
// TAB 2: KALENDER MIT 5-STUFIGER FARBSKALA
// ==============================================================================
private fun heatmapBgColor(pct: Int, isFuture: Boolean, isDark: Boolean): Color = when {{
    isFuture -> Color.Transparent
    pct == 0 -> if (isDark) Color(0xFF232C27) else Color(0xFFECEFE9)
    pct < 40 -> if (isDark) Color(0xFF7F1D1D) else Color(0xFFFECDD3)
    pct < 70 -> if (isDark) Color(0xFF92400E) else Color(0xFFFDE68A)
    pct < 100 -> if (isDark) Color(0xFF3F6212) else Color(0xFFD9F99D)
    else -> Color(0xFF16A34A)
}}

private fun heatmapTextColor(pct: Int, isFuture: Boolean, isDark: Boolean): Color = when {{
    isFuture -> if (isDark) Color(0xFF4B5563) else Color(0xFFCBD5E1)
    pct == 100 -> Color.White
    isDark -> Color.White
    else -> Color(0xFF111827)
}}

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
) {{
    val today = LocalDate.now()
    val isDark = MaterialTheme.colorScheme.background.red < 0.2f
    val monthTitle = "${{yearMonth.month.getDisplayName(TextStyle.FULL, Locale.GERMAN)}} ${{yearMonth.year}}"
    val daysInMonth = yearMonth.lengthOfMonth()
    val firstWeekdayOffset = yearMonth.atDay(1).dayOfWeek.value - 1 // Mo=0..So=6

    var sumPct = 0
    var countedDays = 0
    var perfectDays = 0
    for (d in 1..daysInMonth) {{
        val date = yearMonth.atDay(d)
        if (!date.isAfter(today)) {{
            val st = repo.getDayStats(date, supplements, logs)
            sumPct += st.pct
            countedDays++
            if (st.totalReq > 0 && st.pct == 100) perfectDays++
        }}
    }}
    val avgPct = if (countedDays > 0) sumPct / countedDays else 0
    val streak = repo.calculateStreak(supplements, logs)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {{
        item {{
            Card(shape = RoundedCornerShape(24.dp)) {{
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {{
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {{
                        IconButton(onClick = {{ onMonthChange(yearMonth.minusMonths(1)) }}) {{
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Vormonat")
                        }}
                        Text(monthTitle, fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                        IconButton(onClick = {{ onMonthChange(yearMonth.plusMonths(1)) }}) {{
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Nächster Monat")
                        }}
                    }}

                    // 3 Monats-KPIs
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {{
                        KpiTile("Ø Quote", "$avgPct%", Modifier.weight(1f))
                        KpiTile("100%-Tage", "$perfectDays", Modifier.weight(1f))
                        KpiTile("Serie", "$streak d", Modifier.weight(1f))
                    }}

                    // Wochentage
                    Row(modifier = Modifier.fillMaxWidth()) {{
                        listOf("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So").forEach {{ wd ->
                            Text(
                                text = wd,
                                modifier = Modifier.weight(1f),
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }}
                    }}

                    // Monats-Grid (6 Zeilen max)
                    val totalCells = firstWeekdayOffset + daysInMonth
                    val rows = (totalCells + 6) / 7
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {{
                        for (row in 0 until rows) {{
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {{
                                for (col in 0 until 7) {{
                                    val cellIndex = row * 7 + col
                                    val dayNum = cellIndex - firstWeekdayOffset + 1
                                    if (dayNum in 1..daysInMonth) {{
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
                                                .clickable {{ onSelectDate(d) }},
                                            contentAlignment = Alignment.Center
                                        ) {{
                                            Column(horizontalAlignment = Alignment.CenterHorizontally) {{
                                                Text("$dayNum", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = fg)
                                                if (!isFuture) {{
                                                    Text(
                                                        text = if (st.pct == 100 && st.totalReq > 0) "✓" else if (st.pct > 0) "${{st.pct}}%" else "·",
                                                        fontSize = 8.sp,
                                                        fontWeight = FontWeight.Bold,
                                                        color = fg.copy(alpha = 0.85f)
                                                    )
                                                }}
                                            }}
                                        }}
                                    }} else {{
                                        Spacer(Modifier.weight(1f))
                                    }}
                                }}
                            }}
                        }}
                    }}

                    // Farbskala-Legende
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {{
                        LegendChip("0%", heatmapBgColor(0, false, isDark))
                        LegendChip("<40%", heatmapBgColor(25, false, isDark))
                        LegendChip("<70%", heatmapBgColor(55, false, isDark))
                        LegendChip("<100%", heatmapBgColor(85, false, isDark))
                        LegendChip("100%", heatmapBgColor(100, false, isDark))
                    }}
                }}
            }}
        }}

        // Einzeltag-Inspektor
        item {{
            val selStats = repo.getDayStats(selectedDate, supplements, logs)
            val selChecks = logs[selectedDate.format(SupplementRepository.DATE_FMT)] ?: emptySet()
            val activeSupps = supplements.filter {{ it.active }}
            val fmt = DateTimeFormatter.ofPattern("EEEE, d. MMMM yyyy", Locale.GERMAN)

            Card(shape = RoundedCornerShape(24.dp)) {{
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {{
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {{
                        Column(modifier = Modifier.weight(1f)) {{
                            Text("EINZELTAG-ANSICHT", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(selectedDate.format(fmt), fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
                        }}
                        Text(
                            "${{selStats.pct}}% (${{selStats.reqDone}}/${{selStats.totalReq}})",
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }}

                    activeSupps.forEach {{ s ->
                        val done = selChecks.contains(s.id)
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .background(
                                    if (done) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f)
                                    else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                                )
                                .clickable {{ onToggleDaySupp(selectedDate, s.id) }}
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {{
                            Column(modifier = Modifier.weight(1f)) {{
                                Text(s.name, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                Text(s.dose, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }}
                            Text(if (done) "✓ Erledigt" else "Offen", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = if (done) SagePrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                        }}
                    }}

                    FilledTonalButton(
                        onClick = {{ onOpenInToday(selectedDate) }},
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp)
                    ) {{
                        Text("Diesen Tag in „Heute“ öffnen →", fontWeight = FontWeight.Bold)
                    }}
                }}
            }}
        }}
    }}
}}

@Composable
private fun KpiTile(label: String, value: String, modifier: Modifier = Modifier) {{
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            .padding(vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {{
        Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Bold)
        Text(value, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
    }}
}}

@Composable
private fun LegendChip(label: String, color: Color) {{
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {{
        Box(modifier = Modifier.size(10.dp).clip(CircleShape).background(color))
        Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }}
}}

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
) {{
    val context = LocalContext.current
    var hasNotifPerm by remember {{
        mutableStateOf(
            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        )
    }}
    val alarmManager = remember {{ context.getSystemService(Context.ALARM_SERVICE) as AlarmManager }}
    val hasExactAlarm = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()

    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {{ granted ->
        hasNotifPerm = granted
        if (granted) {{
            ReminderScheduler.rescheduleAll(context)
            onShowMessage("🔔 Benachrichtigungen aktiviert!")
        }}
    }}

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {{
        item {{
            Card(shape = RoundedCornerShape(22.dp)) {{
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {{
                    Text("🔔 System-Wecker (Pixel)", fontWeight = FontWeight.ExtraBold, fontSize = 15.sp)
                    Text(
                        "Native Android-Alarme laufen zuverlässig im Hintergrund – auch nach einem Neustart. Jede Benachrichtigung enthält einen „Alle abhaken“-Button.",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {{
                        if (!hasNotifPerm && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {{
                            Button(
                                onClick = {{ permLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) }},
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(14.dp)
                            ) {{ Text("Erlauben") }}
                        }}
                        OutlinedButton(
                            onClick = {{
                                ReminderScheduler.showNotification(
                                    context,
                                    "🧪 SuppTrack Test-Wecker",
                                    "Deine nativen Pixel-Benachrichtigungen funktionieren einwandfrei!",
                                    null,
                                    99999
                                )
                                onShowMessage("Test-Benachrichtigung gesendet")
                            }},
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(14.dp)
                        ) {{ Text("Test-Alarm") }}
                    }}

                    if (!hasExactAlarm && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {{
                        FilledTonalButton(
                            onClick = {{
                                val i = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {{
                                    data = Uri.parse("package:${{context.packageName}}")
                                }}
                                context.startActivity(i)
                            }},
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(14.dp)
                        ) {{ Text("Exakte Alarme in Android freigeben") }}
                    }}
                }}
            }}
        }}

        item {{
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {{
                Text("💊 Dein Supplement-Stack", fontWeight = FontWeight.ExtraBold, fontSize = 15.sp)
                FilledTonalButton(onClick = onAdd, shape = RoundedCornerShape(12.dp)) {{
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Neu")
                }}
            }}
        }}

        items(supplements, key = {{ it.id }}) {{ supp ->
            Card(shape = RoundedCornerShape(20.dp)) {{
                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {{
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top
                    ) {{
                        Column(modifier = Modifier.weight(1f)) {{
                            Text(supp.name, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            Text("${{supp.slot.emoji}} ${{supp.slot.label}} · ${{supp.dose}}", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                            if (supp.note.isNotBlank()) {{
                                Text(supp.note, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }}
                        }}
                        Row {{
                            IconButton(onClick = {{ onEdit(supp) }}) {{
                                Icon(Icons.Default.Edit, contentDescription = "Anpassen")
                            }}
                            IconButton(onClick = {{ onDelete(supp) }}) {{
                                Icon(Icons.Default.Delete, contentDescription = "Entfernen", tint = Color(0xFFDC2626))
                            }}
                        }}
                    }}

                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {{
                        Row(verticalAlignment = Alignment.CenterVertically) {{
                            Checkbox(
                                checked = supp.active,
                                onCheckedChange = {{ onUpdateSupp(supp.copy(active = it)) }}
                            )
                            Text("Aktiv", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }}
                        Row(verticalAlignment = Alignment.CenterVertically) {{
                            Checkbox(
                                checked = supp.reminderEnabled,
                                enabled = supp.active,
                                onCheckedChange = {{ onUpdateSupp(supp.copy(reminderEnabled = it)) }}
                            )
                            Text("⏰ ${{supp.time}}", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        }}
                    }}
                }}
            }}
        }}
    }}
}}

// ==============================================================================
// TAB 4: IN-APP-UPDATES & BACKUP
// ==============================================================================
@Composable
fun UpdatesAndBackupTab(
    repo: SupplementRepository,
    onReload: () -> Unit,
    onShowMessage: (String) -> Unit
) {{
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()

    var githubRepo by remember {{ mutableStateOf(repo.getUpdateRepo()) }}
    var directUrl by remember {{ mutableStateOf(repo.getDirectApkUrl()) }}
    var checking by remember {{ mutableStateOf(false) }}
    var downloading by remember {{ mutableStateOf(false) }}
    var downloadProgress by remember {{ mutableFloatStateOf(0f) }}
    var releaseInfo by remember {{ mutableStateOf<ReleaseInfo?>(null) }}
    var statusMsg by remember {{ mutableStateOf("") }}
    var importText by remember {{ mutableStateOf("") }}
    var showImportDialog by remember {{ mutableStateOf(false) }}
    var showResetDialog by remember {{ mutableStateOf(false) }}

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {{
        // In-App Updater Card
        Card(shape = RoundedCornerShape(22.dp)) {{
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {{
                Text("🚀 Updates direkt installieren", fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                Text(
                    "Aktuelle Version: v${{BuildConfig.VERSION_NAME}} (Build ${{BuildConfig.VERSION_CODE}}). Hinterlege dein GitHub-Repo, um neue von der KI erzeugte Builds mit einem Tipp ohne Datenverlust zu installieren.",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                OutlinedTextField(
                    value = githubRepo,
                    onValueChange = {{
                        githubRepo = it
                        repo.setUpdateRepo(it)
                    }},
                    label = {{ Text("GitHub Repository (z. B. deinname/supptrack)") }},
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Button(
                    onClick = {{
                        checking = true
                        statusMsg = "Suche nach neuem Release..."
                        releaseInfo = null
                        scope.launch {{
                            val res = UpdateManager.checkGitHubRelease(githubRepo)
                            checking = false
                            res.onSuccess {{ info ->
                                releaseInfo = info
                                statusMsg = if (info.isNewer) "🎉 Neues Update verfügbar: ${{info.tagName}}"
                                else "✅ Du nutzt bereits die neueste Version (${{info.tagName}})."
                            }}.onFailure {{ err ->
                                statusMsg = "Fehler: ${{err.message}}"
                            }}
                        }}
                    }},
                    enabled = !checking && !downloading && githubRepo.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp)
                ) {{
                    Text(if (checking) "Prüfe..." else "Nach Update suchen")
                }}

                if (statusMsg.isNotBlank()) {{
                    Text(statusMsg, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
                }}

                releaseInfo?.let {{ info ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        shape = RoundedCornerShape(16.dp)
                    ) {{
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {{
                            Text("${{info.title}} (${{info.tagName}})", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            Text(info.notes, fontSize = 11.sp)
                            Button(
                                onClick = {{
                                    downloading = true
                                    downloadProgress = 0f
                                    scope.launch {{
                                        val dl = UpdateManager.downloadApk(context, info.apkDownloadUrl) {{ p ->
                                            downloadProgress = p
                                        }}
                                        downloading = false
                                        dl.onSuccess {{ apk ->
                                            val started = UpdateManager.triggerApkInstall(context, apk)
                                            if (!started) {{
                                                onShowMessage("Bitte einmalig „Aus dieser Quelle zulassen“ aktivieren und erneut tippen.")
                                            }}
                                        }}.onFailure {{ e ->
                                            onShowMessage("Download-Fehler: ${{e.message}}")
                                        }}
                                    }}
                                }},
                                enabled = !downloading,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp)
                            ) {{
                                Text(if (downloading) "Lade herunter (${{(downloadProgress * 100).toInt()}}%)..." else "Update herunterladen & installieren")
                            }}
                        }}
                    }}
                }}

                if (downloading) {{
                    LinearProgressIndicator(progress = {{ downloadProgress }}, modifier = Modifier.fillMaxWidth())
                }}

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                Text("Alternative: Direkt-Link zu einer .apk", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                OutlinedTextField(
                    value = directUrl,
                    onValueChange = {{
                        directUrl = it
                        repo.setDirectApkUrl(it)
                    }},
                    label = {{ Text("https://.../SuppTrack.apk") }},
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedButton(
                    onClick = {{
                        downloading = true
                        downloadProgress = 0f
                        scope.launch {{
                            val dl = UpdateManager.downloadApk(context, directUrl) {{ p -> downloadProgress = p }}
                            downloading = false
                            dl.onSuccess {{ apk ->
                                val started = UpdateManager.triggerApkInstall(context, apk)
                                if (!started) onShowMessage("Bitte einmalig App-Installation in Einstellungen erlauben.")
                            }}.onFailure {{ e -> onShowMessage("Fehler: ${{e.message}}") }}
                        }}
                    }},
                    enabled = !downloading && directUrl.startsWith("http"),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp)
                ) {{
                    Text("APK direkt laden & installieren")
                }}
            }}
        }}

        // Backup & Wiederherstellung
        Card(shape = RoundedCornerShape(22.dp)) {{
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {{
                Text("💾 Datensicherung (JSON)", fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
                Text(
                    "Kopiere deinen gesamten Kalender-Verlauf und Supplement-Plan als Text-Backup in die Zwischenablage.",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {{
                    Button(
                        onClick = {{
                            clipboard.setText(AnnotatedString(repo.exportBackupJson()))
                            onShowMessage("Backup in Zwischenablage kopiert ✓")
                        }},
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(14.dp)
                    ) {{ Text("Backup kopieren") }}

                    OutlinedButton(
                        onClick = {{
                            importText = clipboard.getText()?.text ?: ""
                            showImportDialog = true
                        }},
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(14.dp)
                    ) {{ Text("Backup laden") }}
                }}
                TextButton(
                    onClick = {{ showResetDialog = true }},
                    modifier = Modifier.fillMaxWidth()
                ) {{
                    Text("Auf Standard-Plan zurücksetzen", color = Color(0xFFDC2626))
                }}
            }}
        }}
    }}

    if (showImportDialog) {{
        AlertDialog(
            onDismissRequest = {{ showImportDialog = false }},
            title = {{ Text("JSON-Backup einfügen") }},
            text = {{
                OutlinedTextField(
                    value = importText,
                    onValueChange = {{ importText = it }},
                    label = {{ Text("Backup-JSON") }},
                    minLines = 4,
                    maxLines = 8,
                    modifier = Modifier.fillMaxWidth()
                )
            }},
            confirmButton = {{
                Button(onClick = {{
                    if (repo.importBackupJson(importText)) {{
                        onReload()
                        showImportDialog = false
                        onShowMessage("Backup erfolgreich wiederhergestellt ✓")
                    }} else {{
                        onShowMessage("Ungültiges JSON-Format")
                    }}
                }}) {{ Text("Wiederherstellen") }}
            }},
            dismissButton = {{
                TextButton(onClick = {{ showImportDialog = false }}) {{ Text("Abbrechen") }}
            }}
        )
    }}

    if (showResetDialog) {{
        AlertDialog(
            onDismissRequest = {{ showResetDialog = false }},
            title = {{ Text("Alles zurücksetzen?") }},
            text = {{ Text("Alle abgehakten Tage und eigenen Anpassungen werden gelöscht.") }},
            confirmButton = {{
                Button(
                    onClick = {{
                        repo.resetToDefault()
                        onReload()
                        showResetDialog = false
                        onShowMessage("Auf Standard-Plan zurückgesetzt")
                    }},
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                ) {{ Text("Zurücksetzen") }}
            }},
            dismissButton = {{
                TextButton(onClick = {{ showResetDialog = false }}) {{ Text("Abbrechen") }}
            }}
        )
    }}
}}

// ==============================================================================
// DIALOG: SUPPLEMENT HINZUFÜGEN / ANPASSEN
// ==============================================================================
@Composable
fun SupplementEditDialog(
    initial: Supplement?,
    onDismiss: () -> Unit,
    onSave: (Supplement) -> Unit,
    onDelete: (() -> Unit)?
) {{
    var name by remember {{ mutableStateOf(initial?.name ?: "") }}
    var dose by remember {{ mutableStateOf(initial?.dose ?: "") }}
    var slot by remember {{ mutableStateOf(initial?.slot ?: DaySlot.MEAL) }}
    var time by remember {{ mutableStateOf(initial?.time ?: "13:00") }}
    var note by remember {{ mutableStateOf(initial?.note ?: "") }}
    var required by remember {{ mutableStateOf(initial?.required ?: true) }}
    var reminderEnabled by remember {{ mutableStateOf(initial?.reminderEnabled ?: true) }}
    var timeError by remember {{ mutableStateOf(false) }}

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {{ Text(if (initial == null) "Neues Supplement" else "Supplement anpassen", fontWeight = FontWeight.ExtraBold) }},
        text = {{
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {{
                OutlinedTextField(
                    value = name,
                    onValueChange = {{ name = it }},
                    label = {{ Text("Supplementname") }},
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = dose,
                    onValueChange = {{ dose = it }},
                    label = {{ Text("Menge (z. B. 2.000 IE / 5 g)") }},
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = time,
                    onValueChange = {{
                        time = it
                        timeError = !it.matches(Regex("^([01]\\\\d|2[0-3]):[0-5]\\\\d$"))
                    }},
                    label = {{ Text("Erinnerungszeit (HH:mm)") }},
                    isError = timeError,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Text("Tageszeit", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {{
                    DaySlot.entries.forEach {{ option ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .background(
                                    if (slot == option) MaterialTheme.colorScheme.primaryContainer
                                    else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                                )
                                .clickable {{ slot = option }}
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {{
                            Text("${{option.emoji}} ${{option.label}}", fontSize = 13.sp, fontWeight = if (slot == option) FontWeight.Bold else FontWeight.Normal)
                        }}
                    }}
                }}

                OutlinedTextField(
                    value = note,
                    onValueChange = {{ note = it }},
                    label = {{ Text("Beschreibung") }},
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth()
                )

                Row(verticalAlignment = Alignment.CenterVertically) {{
                    Checkbox(checked = required, onCheckedChange = {{ required = it }})
                    Text("Zählt zur 100%-Tagesquote (Pflicht)", fontSize = 12.sp)
                }}
                Row(verticalAlignment = Alignment.CenterVertically) {{
                    Checkbox(checked = reminderEnabled, onCheckedChange = {{ reminderEnabled = it }})
                    Text("Wecker aktiv", fontSize = 12.sp)
                }}
            }}
        }},
        confirmButton = {{
            Button(
                onClick = {{
                    val cleanTime = if (time.matches(Regex("^([01]\\\\d|2[0-3]):[0-5]\\\\d$"))) time else "13:00"
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
                }},
                enabled = name.isNotBlank() && dose.isNotBlank() && !timeError
            ) {{ Text("Speichern") }}
        }},
        dismissButton = {{
            Row {{
                if (onDelete != null) {{
                    TextButton(onClick = onDelete) {{
                        Text("Entfernen", color = Color(0xFFDC2626))
                    }}
                }}
                TextButton(onClick = onDismiss) {{ Text("Abbrechen") }}
            }}
        }}
    )
}}
'''

# GitHub Actions Workflow: Baut & signiert APK automatisch bei jedem Push und erstellt ein GitHub Release!
GITHUB_WORKFLOW_YML = f'''name: Build & Release SuppTrack APK

on:
  push:
    branches: [ "main" ]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-apk:
    runs-on: ubuntu-latest

    steps:
      - name: Repository auschecken
        uses: actions/checkout@v4

      - name: Java 17 einrichten
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17

      - name: Gradle 8.9 einrichten
        uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: 8.9

      - name: Persistentes Release-Keystore wiederherstellen (falls als Secret hinterlegt)
        env:
          KEYSTORE_BASE64: ${{{{ secrets.KEYSTORE_BASE64 }}}}
        run: |
          if [ -n "$KEYSTORE_BASE64" ]; then
            mkdir -p keystore
            echo "$KEYSTORE_BASE64" | base64 -d > keystore/supptrack-release.jks
            echo "Release-Keystore aktiviert (In-Place-Updates behalten alle Daten!)."
          else
            echo "Hinweis: Kein KEYSTORE_BASE64 Secret gefunden – baue mit Debug-Signatur."
          fi

      - name: APK kompilieren
        env:
          KEYSTORE_FILE: ${{{{ github.workspace }}}}/keystore/supptrack-release.jks
          KEYSTORE_PASSWORD: ${{{{ secrets.KEYSTORE_PASSWORD }}}}
          KEY_ALIAS: ${{{{ secrets.KEY_ALIAS }}}}
          KEY_PASSWORD: ${{{{ secrets.KEY_PASSWORD }}}}
        run: gradle assembleRelease

      - name: Version aus build.gradle.kts auslesen
        id: version
        run: |
          VER=$(grep -oP 'versionName\\s*=\\s*"\\K[^"]+' app/build.gradle.kts)
          CODE=$(grep -oP 'versionCode\\s*=\\s*\\K[0-9]+' app/build.gradle.kts)
          echo "name=$VER" >> $GITHUB_OUTPUT
          echo "code=$CODE" >> $GITHUB_OUTPUT
          cp app/build/outputs/apk/release/app-release*.apk "SuppTrack-v${{VER}}.apk"

      - name: GitHub Release mit fertiger APK veröffentlichen
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{{{ steps.version.outputs.name }}}}
          name: SuppTrack Vegan v${{{{ steps.version.outputs.name }}}} (Build ${{{{ steps.version.outputs.code }}}})
          body: |
            Automatisch erstelltes Pixel-Update für **SuppTrack Vegan**.
            Öffne in der App den Tab **Updates → Nach Update suchen**, um direkt zu aktualisieren.
          files: SuppTrack-v*.apk
          make_latest: true
'''

GITIGNORE = r'''*.iml
.gradle
/local.properties
/.idea
.DS_Store
/build
/app/build
/captures
keystore/*.jks
'''


# ==============================================================================
# GENERATOR-FUNKTIONEN
# ==============================================================================

def write_file(base: Path, rel_path: str, content: str) -> None:
    """Schreibt eine Datei sicher inklusive fehlender Unterverzeichnisse."""
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def generate_project(output_dir: Path) -> None:
    """Erstellt oder aktualisiert das gesamte native Android-Projekt."""
    pkg_dir = "app/src/main/java/" + APP_ID.replace(".", "/")

    files = {
        ".gitignore": GITIGNORE,
        "settings.gradle.kts": SETTINGS_GRADLE,
        "build.gradle.kts": ROOT_BUILD_GRADLE,
        "gradle.properties": GRADLE_PROPERTIES,
        "gradle/wrapper/gradle-wrapper.properties": GRADLE_WRAPPER_PROPS,
        "app/build.gradle.kts": APP_BUILD_GRADLE,
        "app/proguard-rules.pro": PROGUARD_RULES,
        "app/src/main/AndroidManifest.xml": ANDROID_MANIFEST,
        "app/src/main/res/values/strings.xml": STRINGS_XML,
        "app/src/main/res/values/themes.xml": THEMES_XML,
        "app/src/main/res/values/colors.xml": COLORS_LIGHT_XML,
        "app/src/main/res/values-night/colors.xml": COLORS_NIGHT_XML,
        "app/src/main/res/xml/file_paths.xml": FILE_PATHS_XML,
        "app/src/main/res/xml/widget_supptrack_info.xml": WIDGET_INFO_XML,
        "app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml": IC_LAUNCHER_XML,
        "app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml": IC_LAUNCHER_XML,
        "app/src/main/res/drawable/ic_launcher_background.xml": IC_LAUNCHER_BG_XML,
        "app/src/main/res/drawable/ic_launcher_foreground.xml": IC_LAUNCHER_FG_XML,
        "app/src/main/res/drawable/ic_stat_leaf.xml": IC_STAT_LEAF_XML,
        "app/src/main/res/drawable/widget_bg.xml": WIDGET_BG_XML,
        "app/src/main/res/drawable/widget_item_bg.xml": WIDGET_ITEM_BG_XML,
        "app/src/main/res/drawable/widget_badge_bg.xml": WIDGET_BADGE_BG_XML,
        "app/src/main/res/drawable/dot_gray.xml": make_dot_drawable("#CBD5E1"),
        "app/src/main/res/drawable/dot_rose.xml": make_dot_drawable("#FB7185"),
        "app/src/main/res/drawable/dot_amber.xml": make_dot_drawable("#FBBF24"),
        "app/src/main/res/drawable/dot_lime.xml": make_dot_drawable("#84CC16"),
        "app/src/main/res/drawable/dot_emerald.xml": make_dot_drawable("#16A34A"),
        "app/src/main/res/layout/widget_supptrack.xml": WIDGET_LAYOUT_XML,
        f"{pkg_dir}/SupplementRepository.kt": MODELS_AND_REPO_KT,
        f"{pkg_dir}/Reminders.kt": REMINDERS_KT,
        f"{pkg_dir}/SupplementWidgetProvider.kt": WIDGET_PROVIDER_KT,
        f"{pkg_dir}/UpdateManager.kt": UPDATE_MANAGER_KT,
        f"{pkg_dir}/MainActivity.kt": MAIN_ACTIVITY_KT,
        ".github/workflows/release-apk.yml": GITHUB_WORKFLOW_YML,
    }

    for rel, content in files.items():
        write_file(output_dir, rel, content)

    print(f"✅ Natives Android-Projekt erstellt/aktualisiert in: {output_dir.resolve()}")
    print(f"   Version: v{APP_VERSION_NAME} (versionCode={APP_VERSION_CODE})")
    print()
    print("Nächste Schritte:")
    print("  Option A (Ohne Android Studio – automatische Updates über GitHub):")
    print("    1. Einmalig festen Signier-Schlüssel erzeugen: python3 build_supptrack_android.py --gen-keystore")
    print("    2. Ordner 'SuppTrackNative' als GitHub-Repository pushen & die 4 Secrets eintragen.")
    print("    3. GitHub baut automatisch 'SuppTrack-v1.0.0.apk' unter Releases -> auf Pixel 11 installieren.")
    print("    4. In der App unter Tab 'Updates' dein Repo eintragen -> künftige Updates mit 1 Klick installieren!")
    print()
    print("  Option B (Direkt mit Android Studio):")
    print("    Ordner 'SuppTrackNative' in Android Studio öffnen -> Pixel 11 anschließen -> Run ▶")


def generate_keystore(output_dir: Path) -> None:
    """Erstellt ein dauerhaftes Release-Keystore für nahtlose In-Place-Updates ohne Datenverlust."""
    ks_dir = output_dir / "keystore"
    ks_dir.mkdir(parents=True, exist_ok=True)
    ks_path = ks_dir / "supptrack-release.jks"

    if ks_path.exists():
        print(f"ℹ️ Keystore existiert bereits: {ks_path}")
    else:
        cmd = [
            "keytool", "-genkeypair", "-v",
            "-keystore", str(ks_path),
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
            "-alias", "supptrack",
            "-storepass", "supptrack123",
            "-keypass", "supptrack123",
            "-dname", "CN=SuppTrack Vegan, OU=Personal, O=SuppTrack, L=Saarbruecken, C=DE"
        ]
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Keystore erzeugt: {ks_path}")
        except FileNotFoundError:
            print("❌ 'keytool' nicht gefunden. Bitte JDK 17 (Java) installieren und erneut ausführen.")
            sys.exit(1)
        except subprocess.CalledProcessError as exc:
            print(f"❌ Fehler beim Erzeugen des Keystores: {exc}")
            sys.exit(1)

    b64 = base64.b64encode(ks_path.read_bytes()).decode("ascii")
    b64_file = ks_dir / "KEYSTORE_BASE64.txt"
    b64_file.write_text(b64, encoding="utf-8")

    print()
    print("Trage diese 4 Secrets in deinem GitHub-Repo ein (Settings → Secrets and variables → Actions):")
    print(f"  1. KEYSTORE_BASE64   → Inhalt aus Datei: {b64_file}")
    print("  2. KEYSTORE_PASSWORD → supptrack123")
    print("  3. KEY_ALIAS         → supptrack")
    print("  4. KEY_PASSWORD      → supptrack123")
    print("⚠️ Hinweis: Den Ordner 'keystore/' niemals öffentlich committen (steht bereits in .gitignore).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Erzeugt das native Android-Projekt für SuppTrack Vegan.")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR, help="Zielordner (Standard: ./SuppTrackNative)")
    parser.add_argument("--gen-keystore", action="store_true", help="Erstellt ein dauerhaftes Keystore für In-Place-Updates")
    args = parser.parse_args()

    try:
        generate_project(args.out)
        if args.gen_keystore:
            generate_keystore(args.out)
    except Exception as exc:
        print(f"❌ Unerwarteter Fehler: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()