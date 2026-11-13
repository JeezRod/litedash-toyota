package com.irvingguerra.litedash.feature.car

import java.io.File
import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * El auto que viene dentro de la app: se instala una sola vez, sin internet y sin catálogo.
 * Va aparte de [CarRepository] para poder probarlo sin Android.
 */
internal object BundledCar {
    /**
     * Descomprime el paquete de [open] en [root]/[folder]: primero en una carpeta temporal y luego se renombra,
     * como el catálogo, para que un corte nunca deje un auto a medias. No escribe huella (SHA-256): sin ella
     * y sin entrada en el catálogo, la app nunca lo ofrece como "modelo nuevo".
     */
    fun install(open: () -> InputStream, root: File, folder: String) {
        root.mkdirs()
        val target = File(root, folder)
        val staging = File(root, folder + CarFiles.STAGING_SUFFIX)
        try {
            staging.deleteRecursively()
            open().buffered().use { unzipTo(it, staging) }
            check(File(staging, CarFiles.PACKAGE_INFO).exists()) { "El paquete no trae ${CarFiles.PACKAGE_INFO}" }
            target.deleteRecursively()
            check(staging.renameTo(target)) { "No se pudo acomodar el auto" }
        } finally {
            staging.deleteRecursively()
        }
    }

    /**
     * Un solo intento por instalación de la app: si ya se hizo, nada (aunque el usuario lo haya borrado);
     * si no se pudo instalar, no se anota para reintentar al abrir. Solo toma el auto como el de la pantalla
     * si el usuario no eligió otro.
     */
    suspend fun seed(
        id: String,
        seeded: () -> Boolean,
        markSeeded: () -> Unit,
        chosen: () -> String?,
        choose: (String) -> Unit,
        install: suspend () -> Boolean,
    ) {
        if (seeded()) return
        if (!install()) return
        if (chosen() == null) choose(id)
        markSeeded()
    }
}

/** Descomprime [input] en [target]; ignora entradas con rutas fuera de la carpeta (zip con "../"). */
internal fun unzipTo(input: InputStream, target: File) {
    ZipInputStream(input).use { zip ->
        while (true) {
            val item = zip.nextEntry ?: break
            val file = File(target, item.name)
            if (!file.canonicalPath.startsWith(target.canonicalPath + File.separator)) continue
            if (item.isDirectory) file.mkdirs() else {
                file.parentFile?.mkdirs()
                file.outputStream().use { zip.copyTo(it) }
            }
        }
    }
}
