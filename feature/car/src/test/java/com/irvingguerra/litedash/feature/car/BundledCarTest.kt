package com.irvingguerra.litedash.feature.car

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class BundledCarTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun zip(vararg files: Pair<String, String>): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { z -> files.forEach { (n, t) -> z.putNextEntry(ZipEntry(n)); z.write(t.toByteArray()); z.closeEntry() } }
        return out.toByteArray()
    }

    private val info = """{"id":"prius-c-2014","nombre":"Prius c","marca":"Toyota","anio":2014,"gris":0.5,"giro":2}"""
    private val good get() = zip("auto.json" to info, "giro/00.webp" to "x", "giro/00-pintura.webp" to "x")

    @Test fun installsAFolderTheScannerAccepts() {
        val root = tmp.newFolder("cars")
        BundledCar.install({ ByteArrayInputStream(good) }, root, "prius-c-2014")
        assertTrue(File(root, "prius-c-2014/giro/00.webp").exists())
        // Sin huella: el catálogo nunca lo ofrece como modelo nuevo.
        assertFalse(File(root, "prius-c-2014/${CarFiles.PACKAGE_HASH}").exists())
        assertTrue(root.listFiles()!!.none { it.name.endsWith(CarFiles.STAGING_SUFFIX) })
    }

    @Test fun installedPackageIsReadAsACar() {
        val root = tmp.newFolder("cars")
        BundledCar.install({ ByteArrayInputStream(good) }, root, "prius-c-2014")
        val p = CarRepository.readPackage(File(root, "prius-c-2014"))!!
        assertEquals("prius-c-2014", p.id); assertEquals(2, p.spin); assertEquals("", p.sha256)
    }

    @Test fun theShippedPriusInstallsAndIsRead() {
        val asset = File("../../app/src/main/assets/prius-c-2014.zip")
        assertTrue("falta ${asset.canonicalPath}", asset.exists())
        val root = tmp.newFolder("cars")
        BundledCar.install({ asset.inputStream() }, root, "prius-c-2014")
        val p = CarRepository.readPackage(File(root, "prius-c-2014"))!!
        assertEquals("prius-c-2014", p.id); assertEquals(24, p.spin); assertEquals("Toyota", p.make)
        assertEquals("CC-BY-4.0", p.license)
        (0 until p.spin).forEach {
            assertTrue(File(p.folder, "giro/%02d.webp".format(it)).exists())
            assertTrue(File(p.folder, "giro/%02d-pintura.webp".format(it)).exists())
        }
    }

    @Test fun cutInstallLeavesNoCar() {
        val root = tmp.newFolder("cars")
        val cut = object : InputStream() {
            var n = 0
            val src = ByteArrayInputStream(good)
            override fun read(): Int = if (n++ > 120) throw java.io.IOException("cortado") else src.read()
        }
        runCatching { BundledCar.install({ cut }, root, "prius-c-2014") }.also { assertTrue(it.isFailure) }
        assertEquals(emptyList<String>(), root.list()!!.toList())
    }

    @Test fun zipWithoutInfoIsRejected() {
        val root = tmp.newFolder("cars")
        val r = runCatching { BundledCar.install({ ByteArrayInputStream(zip("giro/00.webp" to "x")) }, root, "prius-c-2014") }
        assertTrue(r.isFailure)
        assertEquals(emptyList<String>(), root.list()!!.toList())
    }

    @Test fun pathsOutsideTheFolderAreIgnored() {
        val root = tmp.newFolder("cars")
        BundledCar.install({ ByteArrayInputStream(zip("auto.json" to info, "../evil.txt" to "x")) }, root, "prius-c-2014")
        assertFalse(File(root, "evil.txt").exists())
    }

    private class Prefs(var seeded: Boolean = false, var chosen: String? = null) {
        var installs = 0
        fun run(ok: Boolean = true) = runBlocking {
            BundledCar.seed("prius", { seeded }, { seeded = true }, { chosen }, { chosen = it }) { installs++; ok }
        }
    }

    @Test fun freshInstallSelectsIt() = Prefs().let { it.run(); assertEquals("prius", it.chosen); assertTrue(it.seeded) }

    @Test fun existingChoiceIsKept() = Prefs(chosen = "toyota/rav4").let {
        it.run(); assertEquals("toyota/rav4", it.chosen); assertTrue(it.seeded)
    }

    @Test fun secondStartDoesNothing() = Prefs().let {
        it.run(); it.chosen = null; it.run()
        assertEquals(1, it.installs); assertEquals(null, it.chosen)
    }

    @Test fun failedInstallIsRetriedNextStart() = Prefs().let {
        it.run(ok = false)
        assertFalse(it.seeded); assertEquals(null, it.chosen)
        it.run(); assertEquals(2, it.installs); assertTrue(it.seeded)
    }
}
