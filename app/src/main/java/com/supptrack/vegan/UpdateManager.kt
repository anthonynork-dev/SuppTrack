package com.supptrack.vegan

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
object UpdateManager {

    suspend fun checkGitHubRelease(repoPath: String): Result<ReleaseInfo> = withContext(Dispatchers.IO) {
        runCatching {
            val cleanRepo = repoPath.trim().removePrefix("https://github.com/").trim('/')
            require(cleanRepo.contains("/")) { "Bitte im Format benutzername/repository eingeben." }

            val url = URL("https://api.github.com/repos/$cleanRepo/releases/latest")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 10_000
                readTimeout = 10_000
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "SuppTrack-Android/${BuildConfig.VERSION_NAME}")
            }

            if (conn.responseCode != 200) {
                throw IllegalStateException("GitHub API Antwort: HTTP ${conn.responseCode} (Repo öffentlich & Release vorhanden?)")
            }

            val bodyText = conn.inputStream.bufferedReader().use { it.readText() }
            val json = JSONObject(bodyText)
            val tag = json.optString("tag_name", "0.0.0")
            val name = json.optString("name", tag)
            val notes = json.optString("body", "Keine Änderungsnotizen hinterlegt.")
            val assets = json.optJSONArray("assets")

            var apkUrl = ""
            if (assets != null) {
                for (i in 0 until assets.length()) {
                    val a = assets.getJSONObject(i)
                    val dl = a.optString("browser_download_url", "")
                    if (dl.endsWith(".apk", ignoreCase = true)) {
                        apkUrl = dl
                        break
                    }
                }
            }
            require(apkUrl.isNotBlank()) { "Im neuesten Release wurde keine .apk-Datei gefunden." }

            ReleaseInfo(
                tagName = tag,
                title = name,
                notes = notes,
                apkDownloadUrl = apkUrl,
                isNewer = isVersionNewer(tag, BuildConfig.VERSION_NAME)
            )
        }
    }

    suspend fun downloadApk(
        context: Context,
        downloadUrl: String,
        onProgress: (Float) -> Unit
    ): Result<File> = withContext(Dispatchers.IO) {
        runCatching {
            val updatesDir = File(context.cacheDir, "updates").apply { mkdirs() }
            val targetFile = File(updatesDir, "supptrack-update.apk")

            val conn = (URL(downloadUrl).openConnection() as HttpURLConnection).apply {
                instanceFollowRedirects = true
                connectTimeout = 15_000
                readTimeout = 30_000
                setRequestProperty("User-Agent", "SuppTrack-Android/${BuildConfig.VERSION_NAME}")
            }

            if (conn.responseCode !in 200..299) {
                throw IllegalStateException("Download fehlgeschlagen (HTTP ${conn.responseCode})")
            }

            val totalBytes = conn.contentLengthLong
            conn.inputStream.use { input ->
                FileOutputStream(targetFile).use { output ->
                    val buffer = ByteArray(8192)
                    var downloaded = 0L
                    var read: Int
                    while (input.read(buffer).also { read = it } != -1) {
                        output.write(buffer, 0, read)
                        downloaded += read
                        if (totalBytes > 0) {
                            onProgress((downloaded.toFloat() / totalBytes).coerceIn(0f, 1f))
                        }
                    }
                }
            }
            onProgress(1f)
            targetFile
        }
    }

    /**
     * Startet die Android-Systeminstallation für das heruntergeladene APK.
     * Gibt false zurück, falls der Nutzer erst "Apps aus dieser Quelle zulassen" aktivieren muss.
     */
    fun triggerApkInstall(context: Context, apkFile: File): Boolean {
        if (!context.packageManager.canRequestPackageInstalls()) {
            val settingsIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}")
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(settingsIntent)
            return false
        }

        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apkFile
        )
        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(installIntent)
        return true
    }

    private fun isVersionNewer(remoteTag: String, currentVersion: String): Boolean {
        val remoteParts = remoteTag.trim().removePrefix("v").removePrefix("V").split(".").map { it.toIntOrNull() ?: 0 }
        val localParts = currentVersion.trim().removePrefix("v").removePrefix("V").split(".").map { it.toIntOrNull() ?: 0 }
        val maxLen = maxOf(remoteParts.size, localParts.size)
        for (i in 0 until maxLen) {
            val r = remoteParts.getOrElse(i) { 0 }
            val l = localParts.getOrElse(i) { 0 }
            if (r > l) return true
            if (r < l) return false
        }
        return false
    }
}
