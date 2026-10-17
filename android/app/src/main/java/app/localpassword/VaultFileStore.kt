package app.localpassword

import android.content.Context
import android.util.AtomicFile
import java.io.File
import java.io.IOException

/** Serializes access to the app-private encrypted vault and recovers an interrupted write. */
internal object VaultFileStore {
    private val lock = Any()

    fun file(context: Context): File = File(context.filesDir, VAULT_FILE_NAME)

    fun exists(context: Context): Boolean = synchronized(lock) {
        val file = file(context)
        file.isFile || File(file.path + BACKUP_SUFFIX).isFile
    }

    @Throws(VaultException::class)
    fun read(context: Context): ByteArray = synchronized(lock) {
        try {
            AtomicFile(file(context)).openRead().use { it.readBytes() }
        } catch (_: IOException) {
            throw VaultException("Could not read the saved vault file.")
        }
    }

    @Throws(VaultException::class)
    fun write(context: Context, bytes: ByteArray) = synchronized(lock) {
        val atomicFile = AtomicFile(file(context))
        var stream: java.io.FileOutputStream? = null
        try {
            stream = atomicFile.startWrite()
            stream.write(bytes)
            stream.fd.sync()
            atomicFile.finishWrite(stream)
            stream = null
            // Some platform versions log a failed rename rather than throwing.
            val stored = atomicFile.openRead().use { it.readBytes() }
            val matches = stored.contentEquals(bytes)
            stored.fill(0)
            if (!matches) throw IOException("Vault commit verification failed")
        } catch (_: IOException) {
            stream?.let(atomicFile::failWrite)
            throw VaultException("Could not confirm the vault was saved. Reopen the vault before making further changes.")
        }
    }

    private const val VAULT_FILE_NAME = "saved.vault"
    private const val BACKUP_SUFFIX = ".bak"
}
