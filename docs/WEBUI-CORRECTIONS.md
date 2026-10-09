# NVM WebUI — Koreksi Desain yang Dikunci

Status: keputusan desain disepakati; demo UI diperbarui secara terpisah dari implementasi backend/firmware.

## 1. Vending & Inventory

- Setiap vending machine memiliki tepat 5 posisi produk tetap, Product ID 1 sampai Product ID 5.
- Katalog tidak menyediakan tombol **Tambah produk**. Admin hanya memilih Product ID 1–5 lalu mengedit nama produk, harga, stok, dan kapasitas.
- Jangan tampilkan input slot atau servo pada WebUI. Pemetaan perangkat bersifat tetap: Product ID 1 → slot/servo 1, ... Product ID 5 → slot/servo 5.
- API dan firmware harus memvalidasi Product ID 1–5 untuk mesin yang dituju. Identitas slot/servo tidak boleh diedit terpisah dari Product ID.
- Setiap mesin memiliki katalog lima posisi sendiri; Product ID yang sama pada mesin berbeda bukan produk yang sama secara global.

## 2. Registrasi Member & NFC

Form tambah member berisi:
1. Nama lengkap.
2. Nomor NIK.
3. Dropdown pemilihan Cashier.
4. Tombol **Scan** di samping dropdown.

Alur pendaftaran credential:
1. Admin memilih cashier lalu menekan Scan.
2. Server membuat sesi enrollment dan mengirim perintah melalui API ke cashier yang dipilih.
3. Layar cashier menampilkan **“Silakan scan kartu”**.
4. Setelah UID NFC terbaca, cashier menampilkan **“Silakan masukkan PIN transaksi”**.
5. PIN transaksi divalidasi untuk mengikat credential NFC dengan member.
6. Server menyimpan UID/credential dan verifier PIN dengan aman, lalu menyelesaikan pendaftaran.

Sesi enrollment harus memiliki timeout, status, korelasi permintaan, dan audit event. UID kartu tidak boleh diketik manual dalam alur normal. PIN asli tidak boleh ditampilkan kembali atau disimpan sebagai teks biasa. Demo browser hanya mensimulasikan alur ini; implementasi nyata memerlukan API server dan dukungan firmware cashier.

## 3. Member ID otomatis

- Member ID tidak dapat diinput atau diedit manual oleh admin.
- Format tetap: `NTR-00001`, `NTR-00002`, dan seterusnya.
- `NTR` adalah prefix tetap; angka lima digit adalah nomor urut pendaftaran. Contoh member ke-1120: `NTR-01120`.
- Nomor dibuat di server/database secara atomik agar pendaftaran bersamaan tidak menghasilkan ID duplikat. Jangan mengandalkan penghitung browser atau jumlah baris UI.
- NIK harus divalidasi dan diberi batasan unik sesuai kebijakan data member.

## 4. Top-up saldo manual

- Di tabel Member Registry, sediakan tombol **+** di sisi saldo simpanan.
- Tombol membuka form top-up dengan nominal, referensi/keterangan, dan konfirmasi admin.
- Top-up nyata harus melalui Financial Core: validasi nominal dan otorisasi, posting kredit ke ledger dengan referensi unik/idempotency, memperbarui saldo secara transaksional, serta mencatat audit event.
- Jangan mengubah saldo secara langsung tanpa ledger. UI demo boleh menyimulasikan alur tetapi harus jelas berlabel DEMO.

## 5. Batas implementasi

Demo HTML tidak terhubung ke backend dan perangkat fisik. Perilaku di atas baru dianggap production-ready setelah API, database/migrasi, autentikasi/otorisasi, audit, dan firmware ESP32 Cashier/Vending mendukungnya. Cloudflare Tunnel bukan prasyarat untuk menguji enrollment NFC lokal secara offline.

## 6. Vending Device Registry & selector dinamis

- Tab **Vending & Inventory** harus memiliki dropdown mesin yang diisi dari daftar vending yang dikenali/terdaftar oleh server; bukan daftar Machine ID statis di HTML.
- Setiap entri mesin mengikat identitas perangkat yang stabil: device name/Machine ID, MAC address, kredensial perangkat terdaftar, status heartbeat/online-offline, dan metadata lokasi/nama tampilan.
- Contoh label lokasi yang ditampilkan admin: `Vending48cd1` → **Depan Natura**, mesin kedua → **Dalam Natura**, mesin ketiga → **Sekolahan**. Nama lokasi adalah metadata yang dapat diubah admin; jangan menganggap lokasi bisa disimpulkan dari MAC.
- Dropdown dan tabel registry menampilkan nama lokasi, device name/Machine ID, MAC, dan status. Mesin offline tetap terlihat agar admin dapat memilih dan memeriksa katalog/stok terakhir yang diketahui, dengan status offline yang jelas.
- Saat mesin dipilih, tabel katalog, stok, dan editor hanya menampilkan data milik mesin tersebut. Setiap mesin memiliki tepat lima Product ID (1–5); Product ID sama pada dua mesin tidak berbagi stok atau konfigurasi.
- MAC address membantu identifikasi, tetapi bukan autentikasi yang cukup karena dapat dipalsukan. Implementasi nyata wajib mengikat perangkat melalui enrollment/credential perangkat dan heartbeat terautentikasi.
- Pada demo GitHub Pages, daftar perangkat dan statusnya adalah data contoh statis di browser untuk memvalidasi UX. Deteksi/registrasi dinamis sebenarnya baru dibuat saat backend NVM diimplementasikan; jangan mengklaim demo melakukan auto-discovery jaringan nyata.
