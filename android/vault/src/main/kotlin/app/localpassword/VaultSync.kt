package app.localpassword

import java.io.IOException
import java.io.InputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Send the encrypted vault to another device on the same network.
 * The pairing code is checked before any bytes are sent. The passphrase is not
 * part of this exchange.
 */
object VaultSync {
    private val MAGIC = "LPS1".toByteArray(Charsets.US_ASCII)
    private const val CODE_LENGTH = 6
    const val UDP_PORT = 39221
    private const val MAX_VAULT_BYTES = 1_048_576
    private const val OFFER_SECONDS = 120
    private val random = SecureRandom()

    fun newPairingCode(): String {
        return buildString(CODE_LENGTH) {
            repeat(CODE_LENGTH) { append(random.nextInt(10)) }
        }
    }

    fun normalizeCode(code: String): String {
        val digits = code.filter { it.isDigit() }
        if (digits.length != CODE_LENGTH) {
            throw VaultException("The pairing code is 6 digits.")
        }
        return digits
    }

    fun lanAddresses(): List<String> {
        return try {
            DatagramSocket().use { probe ->
                probe.connect(InetAddress.getByName("192.0.2.1"), 9)
                val address = probe.localAddress?.hostAddress ?: ""
                if (address.isNotEmpty() && !address.startsWith("127.")) listOf(address) else emptyList()
            }
        } catch (_: IOException) {
            emptyList()
        }
    }

    class Offer(payload: ByteArray, code: String? = null) {
        val payload: ByteArray = payload.copyOf()
        val code: String = if (code == null) newPairingCode() else normalizeCode(code)
        @Volatile var port: Int = 0
        @Volatile var sent: Boolean = false
        @Volatile var error: String = ""
        val addresses: List<String> = lanAddresses()

        private val stop = AtomicBoolean(false)
        private var thread: Thread? = null
        private var tcp: ServerSocket? = null
        private var udp: DatagramSocket? = null

        init {
            val magic = if (payload.size >= 3) payload.copyOfRange(0, 3) else ByteArray(0)
            if (!magic.contentEquals("LPV".toByteArray(Charsets.US_ASCII)) || payload.size > MAX_VAULT_BYTES) {
                throw VaultException("The saved password file is damaged.")
            }
        }

        fun start() {
            thread = Thread(this::serve, "vault-offer").also {
                it.isDaemon = true
                it.start()
            }
            val deadline = System.nanoTime() + 2_000_000_000L
            while (port == 0 && error.isEmpty() && System.nanoTime() < deadline) {
                Thread.sleep(10)
            }
            if (port == 0 && error.isEmpty()) {
                error = "Could not offer the vault on this network."
            }
        }

        fun stop() {
            stop.set(true)
            try {
                tcp?.close()
            } catch (_: IOException) {
            }
            try {
                udp?.close()
            } catch (_: IOException) {
            }
            thread?.join(2_000)
        }

        fun where(): String {
            if (addresses.isNotEmpty()) {
                return addresses.joinToString(", ") { "$it:$port" }
            }
            if (port != 0) return "port $port"
            return ""
        }

        private fun serve() {
            val server = ServerSocket()
            try {
                server.reuseAddress = true
                server.bind(InetSocketAddress("0.0.0.0", 0))
                server.soTimeout = 200
                tcp = server
                port = server.localPort
                val beacon = DatagramSocket()
                beacon.broadcast = true
                udp = beacon
                val deadline = System.nanoTime() + OFFER_SECONDS * 1_000_000_000L
                var nextBeacon = 0L
                while (!stop.get() && System.nanoTime() < deadline && !sent) {
                    val now = System.nanoTime()
                    if (now >= nextBeacon) {
                        sendBeacon()
                        nextBeacon = now + 400_000_000L
                    }
                    try {
                        val connection = server.accept()
                        try {
                            handle(connection)
                        } finally {
                            connection.close()
                        }
                    } catch (_: SocketTimeoutException) {
                    } catch (_: IOException) {
                        if (!stop.get()) error = "Could not offer the vault on this network."
                        break
                    }
                }
            } catch (_: IOException) {
                if (!stop.get() && error.isEmpty()) {
                    error = "Could not offer the vault on this network."
                }
            } finally {
                try {
                    server.close()
                } catch (_: IOException) {
                }
                try {
                    udp?.close()
                } catch (_: IOException) {
                }
            }
        }

        private fun sendBeacon() {
            val socket = udp ?: return
            if (port == 0) return
            val packet = ByteArray(6)
            MAGIC.copyInto(packet)
            packet[4] = (port ushr 8).toByte()
            packet[5] = (port and 0xff).toByte()
            try {
                socket.send(DatagramPacket(packet, packet.size, InetAddress.getByName("255.255.255.255"), UDP_PORT))
            } catch (_: IOException) {
            }
        }

        private fun handle(connection: Socket) {
            connection.soTimeout = 5_000
            val data = readExact(connection.getInputStream(), 4 + CODE_LENGTH) ?: run {
                connection.getOutputStream().write("NO".toByteArray(Charsets.US_ASCII))
                return
            }
            if (!data.copyOfRange(0, 4).contentEquals(MAGIC)) {
                connection.getOutputStream().write("NO".toByteArray(Charsets.US_ASCII))
                return
            }
            val presented = data.copyOfRange(4, 4 + CODE_LENGTH)
            if (!MessageDigest.isEqual(presented, code.toByteArray(Charsets.US_ASCII))) {
                connection.getOutputStream().write("NO".toByteArray(Charsets.US_ASCII))
                return
            }
            val length = payload.size
            val header = byteArrayOf(
                (length ushr 24).toByte(),
                (length ushr 16).toByte(),
                (length ushr 8).toByte(),
                length.toByte(),
            )
            val output = connection.getOutputStream()
            output.write("OK".toByteArray(Charsets.US_ASCII))
            output.write(header)
            output.write(payload)
            output.flush()
            sent = true
        }
    }

    fun receiveVault(code: String, address: String? = null, timeoutMs: Long = 90_000): ByteArray {
        val pairing = normalizeCode(code)
        val deadline = System.nanoTime() + timeoutMs * 1_000_000L
        if (!address.isNullOrBlank()) {
            val (host, port) = splitAddress(address)
            return pull(host, port, pairing, deadline)
        }
        val udp = DatagramSocket(null)
        try {
            udp.reuseAddress = true
            udp.bind(InetSocketAddress(UDP_PORT))
        } catch (exc: IOException) {
            udp.close()
            throw VaultException("Could not listen for the other device.")
        }
        udp.soTimeout = 500
        try {
            val buffer = ByteArray(32)
            while (System.nanoTime() < deadline) {
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    udp.receive(packet)
                } catch (_: SocketTimeoutException) {
                    continue
                }
                if (packet.length < 6) continue
                val data = packet.data
                if (!data.copyOfRange(0, 4).contentEquals(MAGIC)) continue
                val port = ((data[4].toInt() and 0xff) shl 8) or (data[5].toInt() and 0xff)
                val host = packet.address?.hostAddress ?: continue
                return pull(host, port, pairing, deadline)
            }
        } finally {
            udp.close()
        }
        throw VaultException("No device is offering a vault.")
    }

    private fun pull(host: String, port: Int, code: String, deadline: Long): ByteArray {
        val remaining = ((deadline - System.nanoTime()) / 1_000_000L).coerceAtLeast(1_000)
        val connection = Socket()
        try {
            connection.connect(InetSocketAddress(host, port), remaining.coerceAtMost(5_000).toInt())
            connection.soTimeout = remaining.coerceAtMost(10_000).toInt()
            connection.getOutputStream().write(MAGIC + code.toByteArray(Charsets.US_ASCII))
            connection.getOutputStream().flush()
            val marker = readExact(connection.getInputStream(), 2)
            if (marker == null || !marker.contentEquals("OK".toByteArray(Charsets.US_ASCII))) {
                throw VaultException("That pairing code was refused.")
            }
            val lengthBytes = readExact(connection.getInputStream(), 4)
                ?: throw VaultException("The other device closed the connection.")
            val length = ((lengthBytes[0].toInt() and 0xff) shl 24) or
                ((lengthBytes[1].toInt() and 0xff) shl 16) or
                ((lengthBytes[2].toInt() and 0xff) shl 8) or
                (lengthBytes[3].toInt() and 0xff)
            if (length < 48 || length > MAX_VAULT_BYTES) {
                throw VaultException("The saved password file is damaged.")
            }
            val blob = readExact(connection.getInputStream(), length)
                ?: throw VaultException("The saved password file is damaged.")
            val magic = blob.copyOfRange(0, 3)
            if (!magic.contentEquals("LPV".toByteArray(Charsets.US_ASCII))) {
                throw VaultException("The saved password file is damaged.")
            }
            return blob
        } catch (exc: VaultException) {
            throw exc
        } catch (_: IOException) {
            throw VaultException("Could not reach the other device.")
        } finally {
            connection.close()
        }
    }

    private fun splitAddress(address: String): Pair<String, Int> {
        val text = address.trim()
        val split = text.lastIndexOf(':')
        if (split <= 0 || split == text.lastIndex) {
            throw VaultException("The other device's address needs a port, such as 192.168.1.20:12345.")
        }
        val host = text.substring(0, split)
        val port = text.substring(split + 1).toIntOrNull()
        if (host.isEmpty() || port == null || port < 1 || port > 65535) {
            throw VaultException("The other device's address needs a port, such as 192.168.1.20:12345.")
        }
        return host to port
    }

    private fun readExact(input: InputStream, size: Int): ByteArray? {
        val buffer = ByteArray(size)
        var offset = 0
        while (offset < size) {
            val count = try {
                input.read(buffer, offset, size - offset)
            } catch (_: SocketTimeoutException) {
                return null
            }
            if (count < 0) return null
            offset += count
        }
        return buffer
    }
}
