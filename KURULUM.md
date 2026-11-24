# PA Tarayıcı — Kurulum (saatlik bildirim)

Bu klasör TradingView modüllerinin (M3 FVG, M4 Range, M5 OB / Breaker / KYK / çift yutan / iç OB, M6 EQH/EQL,
M7 seviyeler, M9 likidite, M10 OTE) Python karşılığıdır. GitHub her saat başı çalıştırır, yeni olayları **Telegram** ve
**ntfy** ile telefonuna gönderir. Bilgisayarının açık olması gerekmez.

**25.11.2026 GÜNCELLEME (TV modülleriyle eşitlendi):**
- **M3 FVG** yeni kurallar: bir FVG en fazla 2 temasta sinyal · tek mumda tamamen geçilirse sinyal yok · %51+ dolunca biter · IFVG yok.
  Sinyal FVG'nin kendi TF mumu kapanınca gelir.
- **M4 Range (YENİ):** kilitli range, 3 temas (uca değip EQ'ya ilerleme) = yatay range → RL/RH bölgesi teması,
  sapma (dışarıda kapanış → içeri dönüş), EQ'nun hacimli geçişi (× 1,5). İptal: log mesafe (RH 120 / RL 100 → 91,29 / 131,45).
- **M5 OB:** KYK kuralı (2 yutar 1, 3 yutar 2, 3 en büyük) · YENİ çift yutan OB · swing OB (önceki swing seviyesinde) ·
  ★ likidite alan OB (yutan mum eski swing'i aldı = GÜÇLÜ POI). Sinyal sadece ★ / swing / A kalite / KYK / çift yutan ve
  **gövde bölgesine** temasla. İç OB = eski M8 (filtreli) → mesajda "M5 iç OB".
- **M10 OTE (YENİ):** son zig zag bacağının 0,618–0,786 bölgesi; bacak başına tek sinyal. POI sinyali OTE içindeyse "OTE✓".
- **Endeks bloğu:** her coin sinyalinin altında TOTAL / TOTAL2 / BTC.D / USDT.D'nin 1H 4H 8H 12H 1G ZZ1+ZZ2 yönü,
  karar TF (sinyal TF'nin bir üstü: 4H→8H, 1G→1W) uyumu ✅ / ◐ / ❌, "Skor x / 4" ve endeksin kendi POI teyidi
  ("✓ USDT.D 8H POI'de SAT"). Sadece etiket — sinyal elenmez. AL için uyumlu: TOTAL ▲, TOTAL2 ▲, USDT.D ▼, BTC.D: BTC'de ▲ / altta ▼.

**Coinler:** piyasa değeri en yüksek **50 coin** (CoinGecko sırası, her çalıştırmada güncellenir).
Stabil coinler (USDT, USDC, DAI …) ve sarılmış / stake edilmiş tokenlar (WBTC, stETH …) hariç; sadece
Binance'te USDT vadeli çifti olanlar. Ek olarak her zaman **ATOM, OP, APT** taranır (`EK_COINLER`).
Her saat **tüm coinler tek mesajda** gelir (uzunsa bölünür). Tarama ~1–1,5 dk sürer.

**🧭 PİYASA YÖNÜ (TOTAL · TOTAL2 · BTC.D · USDT.D):** bunlar ayrı, öne çıkan bir mesajla gelir:
- Telegram'da coin mesajından ÖNCE, kalın başlık "🧭🧭 PİYASA YÖNÜ" + dört endeksin 4H / 1G / 1W yön tablosu (▲ / ▼).
- ntfy'de **yüksek öncelikli** (ayrı ses / banner), pusula simgeli, başlık "YON - piyasa yonu".
- Aynı POI bildirimleri + **yapı dönüşü**: "4H yapı DÜŞÜŞE ▼ döndü (MSS)".
- Veri TradingView'den değil: Binance fiyatları × CoinGecko dolaşımdaki arz + USDT/USDC geçmişi; bugünkü
  CoinGecko toplamına sabitlenir. Değerler TV'deki CRYPTOCAP'ten biraz farklı olabilir, yön ve yapı aynıdır.

**Bildirim türleri**
- 🟢 ▲ AL / 🔴 ▼ SAT: fiyat bir POI'ye **ilk kez** girdi (TV'deki sinyalle aynı kural). M6'da EQH/EQL
  likiditesi alındı (sweep). M7'de seviye sweep ya da ilk temas.
- 👀 YAKLAŞTI: fiyat kutuya dokunmadan %0,5 yaklaştı. Her kutu için bir kez gelir; 15m'de hazırlan.
- POI'ler **4H, 1G ve 1W**'de hesaplanır (1H kapalı — 50 coinde çok bildirim olur). Kontrol her saat kapanan **1H mumuyla** yapılır.

> Karar her zaman senin: bildirim sadece "bak" demek.

---

## 1) Telegram botu (5 dk)
1. Telegram'da **@BotFather**'ı aç → `/newbot` yaz → bota bir ad ve sonu `bot` ile biten bir kullanıcı adı ver.
2. BotFather sana bir **token** verir (`123456:ABC...` gibi). **Kimseyle paylaşma**, buraya ya da sohbete yazma.
3. Kendi botunu aç ve ona `merhaba` yaz.
4. Tarayıcıda şu adresi aç (TOKEN yerine kendi token'ını yaz):
   `https://api.telegram.org/botTOKEN/getUpdates`
   Çıkan yazıda `"chat":{"id":` sonrasındaki sayı senin **chat id**'ndir.

## 2) ntfy (telefon bildirimi, 2 dk)
1. Telefona **ntfy** uygulamasını kur (Play Store / App Store).
2. **+** → "Subscribe to topic" → kimsenin tahmin edemeyeceği bir ad yaz (örnek: `pa-tarama-k7x93qz`).
   Bu ad şifre gibidir: bilen herkes bildirimleri görebilir.

## 3) GitHub
1. github.com'da hesap aç (yoksa).
2. Sağ üst **+** → **New repository** → ad: `pa-tarayici` → **Public** seç → Create.
   (Public = sınırsız ücretsiz dakika. Kodu herkes görebilir ama token / chat id / ntfy adı gizli kalır.)
3. Bu klasörün (`TR uygulama/tarayici`) içindekileri depoya yükle. `.github` klasörü de gitmeli.
   En kolayı: depo sayfasında **"uploading an existing file"** → klasördeki her şeyi sürükle-bırak.
   (İstersen yüklemeyi Claude git ile yapar; sadece GitHub girişini sen yaparsın.)
4. Depoda **Settings → Secrets and variables → Actions → New repository secret** ile üç gizli değer ekle:
   | Ad | Değer |
   |---|---|
   | `TG_TOKEN` | BotFather'ın verdiği token |
   | `TG_CHAT` | chat id (sayı) |
   | `NTFY_TOPIC` | ntfy'de seçtiğin ad |
5. **Actions** sekmesi → "PA tarayici (saatlik)" → **Run workflow** ile bir kez elle çalıştır.
   Yeşil tik = çalışıyor. O saatte olay yoksa bildirim gelmez (normal).

## Notlar
- **Veri:** önce Binance vadeli (BTCUSDT.P, TV ile aynı). GitHub sunucuları ABD'de olduğu için Binance vadeli
  engellenirse Binance **spot** kullanılır; mesajın sonunda hangisi olduğu yazar. Spot fiyat vadeliden birkaç
  dolar farklı olabilir.
- **Gecikme:** GitHub zamanlanmış işleri bazen 5–20 dk geç başlatır. Kaçan saatler bir sonraki çalıştırmada
  (en fazla son 6 saat) gönderilir.
- **Ücret:** public depoda ücretsiz ve sınırsız.
- **60 gün kuralı:** depoda 60 gün hiç değişiklik olmazsa GitHub zamanlamayı durdurabilir; Actions sekmesinden
  yeniden açılır.
- **Bilgisayarda deneme:** `python tarayici.py --son 24` → son 24 saatin olayları (gönderilmez).
  `python tarayici.py --yerel 2026-02-28 2026-03-11` → yerel CSV ile geçmiş test.
- **Ayar** (Settings → Secrets and variables → Actions → **Variables** sekmesi; istersen):
  | Ad | Örnek | Anlamı |
  |---|---|---|
  | `COINLER` | `BTC,ETH,SOL` | 50 coin yerine sadece bunlar |
  | `COIN_SAYISI` | `30` | ilk kaç coin (vars. 50) |
  | `EK_COINLER` | `ATOM,OP,APT,INJ` | ilk 50'ye ek olarak hep taranacaklar (vars. `ATOM,OP,APT`) |
  | `ENDEKS` | `0` | piyasa yönü mesajını kapat (vars. açık) |
  | `POI_TF` | `1H,4H,1G,1W` | hangi TF'lerin POI'leri (vars. `4H,1G,1W`) |
  | `YAKLAS_YUZDE` | `0.3` | yaklaşma eşiği (vars. 0.5) |
  Modül ayarları TV varsayılanlarıyla aynı (`moduller.py`).
- **Kapsam dışı:** M1 (TV'de denenmedi), CME gap (CME verisi gerekir), M2 / M4 (sadece çizim; swing motoru M5'in içinde).
