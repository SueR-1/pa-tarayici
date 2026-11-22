#!/usr/bin/env python3
"""
tarayici.py — PA POI tarayıcısı (M3 FVG · M5 OB/Breaker/KYK/iç OB · M6 EQH/EQL · M7 seviyeler · M8 anlamlı iç OB
              · M9 likidite alımı) — Pine ile eşit (22.11.2026: renk şartı, geçiş kuralı, yeni L/H, M9, lik.✓)

Saatte bir çalışır (GitHub Actions). Coinler: piyasa değeri en yüksek 50 coin (stabil / sarılmış / stake hariç,
Binance'te USDT vadeli çifti olanlar). POI'ler 4H / 1G / 1W'de hesaplanır; kapanan 1H mumlarında:
  • POI'ye İLK GİRİŞ  (TV'deki ▲ AL / ▼ SAT ile aynı kural)
  • POI'ye YAKLAŞTI   (kutuya dokunmadan %YAKLAS içinde; kutu başına bir kez)
  • M6 EQH/EQL alındı (sweep) · M7 seviye sweep / ilk temas · M9 swing / range tepe-dip alındı
  • POI sinyalinde son LQ_WIN (vars. 10) TF mumunda aynı yönde M9 alımı → "lik.✓"
Her saat TÜM coinler tek mesajda (uzunsa bölünür). Bildirim: Telegram (TG_TOKEN + TG_CHAT) ve/veya ntfy (NTFY_TOPIC).

Ortam ayarları (isteğe bağlı):
  COINLER       virgüllü liste (ör. "BTC,ETH,SOL") → CoinGecko yerine bu liste
  COIN_SAYISI   vars. 50
  POI_TF        vars. "4H,1G,1W"  (1H eklemek için "1H,4H,1G,1W")
  YAKLAS_YUZDE  vars. 0.5
  LQ_WIN        vars. 10

Kullanım:
  python tarayici.py                 → canlı, yeni olayları gönder
  python tarayici.py --kuru          → gönderme, ekrana yaz (durum kaydedilmez)
  python tarayici.py --son 24        → son 24 saatin olaylarını ekrana yaz (gönderme)
  python tarayici.py --yerel A B     → yerel BTC CSV (onchain-btc/data) ile A–B tarih (YYYY-MM-DD) olayları
"""
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

from endeks import StabilSeri, endeks_bars
from moduller import M3, M5, M6, M7, M8, M9, fmt, zigzag2

KLASOR = os.path.dirname(os.path.abspath(__file__))
YAKLAS = float(os.environ.get("YAKLAS_YUZDE", "0.5"))
# POI sinyali (M3 / M5 / M8) için: aynı TF'de son kaç mumda aynı yönde M9 likidite alımı → "lik.✓" (Pine lqWin)
LQ_WIN = int(os.environ.get("LQ_WIN", "10"))
COIN_SAYISI = int(os.environ.get("COIN_SAYISI", "50"))
EK_COINLER = os.environ.get("EK_COINLER", "ATOM,OP,APT")         # her zaman taranacak ek coinler
ENDEKS = os.environ.get("ENDEKS", "1") != "0"                    # TOTAL / TOTAL2 / BTC.D / USDT.D
POI_TF = [x.strip() for x in os.environ.get("POI_TF", "4H,1G,1W").split(",") if x.strip()]
TFLER = [("1H", "1h", 60), ("4H", "4h", 240), ("1G", "1d", 1440), ("1W", "1w", 10080)]
ADET = {"1h": 2000, "4h": 1500, "1d": 1000, "1w": 500}         # çekilecek mum sayısı
DURUM = os.path.join(KLASOR, "durum.json")
COIN_YEDEK = os.path.join(KLASOR, "coinler.json")
CG_YEDEK = os.path.join(KLASOR, "cg_yedek.json")      # son başarılı CoinGecko verisi (CoinGecko hata verirse)
TR = dt.timezone(dt.timedelta(hours=3))
H1 = 3600 * 1000

# stabil coinler (endekste STABİL kısmı) + sarılmış / stake edilmiş (BTC / ETH kopyası) tokenlar
STABIL = {
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "USDS", "PYUSD", "USDD", "FRAX", "USDP", "GUSD", "LUSD", "BUSD",
    "USD1", "RLUSD", "USDX", "USDY", "USDB", "USD0", "SUSDE", "SUSDS", "EURC", "EURS", "EURT",
    "BFUSD", "USDF", "USDG", "USDTB", "USR", "DEUSD", "CRVUSD", "GHO", "OUSG", "BUIDL", "USYC", "SYRUPUSDC",
}
HARIC = STABIL | {
    "XAUT", "PAXG",
    "WBTC", "CBBTC", "TBTC", "LBTC", "SOLVBTC", "BTCB", "WETH", "STETH", "WSTETH", "WEETH", "RETH", "CBETH",
    "METH", "EZETH", "RSETH", "OSETH", "SFRXETH", "BETH", "WBETH", "JITOSOL", "MSOL", "BNSOL", "JUPSOL", "STSOL",
    "WBNB", "WTRX", "WAVAX", "WMATIC", "WPOL", "STKAIA", "LSETH", "CMETH", "SAVAX", "WHYPE", "KHYPE", "STHYPE",
}


# ════════════════════════════════════════════════════════════════
# VERİ
# ════════════════════════════════════════════════════════════════
def _get(url, deneme=3):
    for k in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pa-tarayici/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (418, 429) and k < deneme - 1:
                time.sleep((25 if "coingecko" in url else 5) * (k + 1))
                continue
            raise


KAYNAKLAR = [("https://fapi.binance.com", "/fapi/v1", "Binance vadeli"),
             ("https://data-api.binance.vision", "/api/v3", "Binance spot"),
             ("https://api.binance.com", "/api/v3", "Binance spot")]


def kaynak_sec():
    """Erişilebilen ilk kaynak + oradaki USDT çiftleri."""
    hata = []
    for base, path, ad in KAYNAKLAR:
        try:
            info = _get(f"{base}{path}/exchangeInfo")
            syms = {s["symbol"] for s in info["symbols"]
                    if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"
                    and s.get("contractType", "PERPETUAL") == "PERPETUAL"}
            if syms:
                return (base, path, ad), syms
        except Exception as e:  # noqa: BLE001
            hata.append(f"{ad}: {e}")
    raise RuntimeError("Hiçbir veri kaynağına ulaşılamadı → " + " | ".join(hata))


CG = "https://api.coingecko.com/api/v3"


def _stabil_mi(s, px):
    return s in STABIL or ("USD" in s and 0.9 < (px or 0) < 1.1)


def _cg_yedek_oku():
    try:
        with open(CG_YEDEK, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _cg_yedek_yaz(**kw):
    d = _cg_yedek_oku()
    d.update(kw)
    d["zaman"] = int(time.time() * 1000)
    with open(CG_YEDEK, "w", encoding="utf-8") as f:
        json.dump(d, f)


def cg_markets():
    """CoinGecko piyasa değeri sırası (ilk 500). Hata → yedek (cg_yedek.json) → []."""
    out = []
    try:
        for sayfa in (1, 2):
            q = urllib.parse.urlencode({"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": sayfa})
            out += _get(f"{CG}/coins/markets?{q}")
            time.sleep(2)
        keep = ("symbol", "current_price", "market_cap", "circulating_supply")
        _cg_yedek_yaz(piyasa=[{k: c.get(k) for k in keep} for c in out])
    except Exception as e:  # noqa: BLE001
        out = _cg_yedek_oku().get("piyasa", [])
        print(f"⚠ CoinGecko listesi alınamadı ({e}) → yedek: {len(out)} coin", file=sys.stderr)
    return out


def cg_global():
    """Toplam piyasa değeri + dominans yüzdeleri. Hata → yedek."""
    try:
        g = _get(f"{CG}/global")["data"]
        g = {"total": g["total_market_cap"]["usd"], "pct": g["market_cap_percentage"]}
        _cg_yedek_yaz(glob=g)
        return g
    except Exception as e:  # noqa: BLE001
        g = _cg_yedek_oku().get("glob")
        print(f"⚠ CoinGecko global alınamadı ({e}) → {'yedek' if g else 'yok'}", file=sys.stderr)
        return g


def coin_listesi(syms, piyasa):
    """[(coin, binance_sembol, kat, cg_fiyat|None)] — CoinGecko sırası (ilk COIN_SAYISI) + EK_COINLER."""
    elle = os.environ.get("COINLER", "").strip()
    fiyat = {}
    for c in piyasa:
        s = (c.get("symbol") or "").upper()
        fiyat.setdefault(s, c.get("current_price"))
    if elle:
        adaylar = [x.strip().upper() for x in elle.split(",") if x.strip()]
    elif piyasa:
        adaylar = []
        for c in piyasa:
            s = (c.get("symbol") or "").upper()
            if s in HARIC or s in adaylar or _stabil_mi(s, c.get("current_price")):
                continue
            adaylar.append(s)
    else:
        print("⚠ CoinGecko yok → coinler.json yedeği", file=sys.stderr)
        with open(COIN_YEDEK, encoding="utf-8") as f:
            adaylar = json.load(f)
    ek = [x.strip().upper() for x in EK_COINLER.split(",") if x.strip()]
    out, ekler = [], []

    def bul(s):
        for kat, sym in ((1, f"{s}USDT"), (1000, f"1000{s}USDT"), (1000000, f"1000000{s}USDT"), (1000000, f"1M{s}USDT")):
            if sym in syms:
                px = fiyat.get(s)
                return (s, sym, kat, px * kat if px else None)
        return None
    for s in adaylar:
        if len(out) >= COIN_SAYISI:
            break
        x = bul(s)
        if x:
            out.append(x)
    for s in ek:
        if s not in [x[0] for x in out]:
            x = bul(s)
            if x:
                ekler.append(x)
            else:
                print(f"⚠ ek coin {s}: Binance'te USDT çifti yok", file=sys.stderr)
    return out + ekler


def stabil_veri(piyasa):
    """USDT / USDC piyasa değeri geçmişi + diğer stabillerin bugünkü toplamı."""
    seriler = {}
    eski = _cg_yedek_oku().get("stabil", {})
    for ad, cid in (("USDT", "tether"), ("USDC", "usd-coin")):
        nokta = {int(t): v for t, v in eski.get(ad, [])}
        for gun in ("365", "90"):        # 90 gün saatlik, öncesi günlük
            try:
                r = _get(f"{CG}/coins/{cid}/market_chart?vs_currency=usd&days={gun}")
                for t, v in r.get("market_caps", []):
                    nokta[int(t)] = float(v)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ {ad} geçmişi alınamadı ({e}) → yedek", file=sys.stderr)
            time.sleep(2)
        seriler[ad] = sorted(nokta.items())
    _cg_yedek_yaz(stabil={k: [[t, v] for t, v in x] for k, x in seriler.items()})
    diger = 0.0
    for c in piyasa:
        s = (c.get("symbol") or "").upper()
        if s not in ("USDT", "USDC") and _stabil_mi(s, c.get("current_price")):
            diger += c.get("market_cap") or 0
    return StabilSeri(seriler, diger)


def veri_cek(kaynak, sym, interval, adet):
    base, path, _ = kaynak
    rows, end = [], None
    while len(rows) < adet:
        q = {"symbol": sym, "interval": interval, "limit": min(1000, adet - len(rows))}
        if end is not None:
            q["endTime"] = end
        part = _get(f"{base}{path}/klines?{urllib.parse.urlencode(q)}")
        if not part:
            break
        rows = part + rows
        end = part[0][0] - 1
        if len(part) < q["limit"]:
            break
    return rows


def bars_from_rows(rows, dur_ms, now_ms):
    """Sadece KAPANMIŞ mumlar."""
    B = dict(t=[], o=[], h=[], l=[], c=[])
    for r in rows:
        t = int(r[0])
        if t + dur_ms > now_ms:
            continue
        B['t'].append(t)
        B['o'].append(float(r[1]))
        B['h'].append(float(r[2]))
        B['l'].append(float(r[3]))
        B['c'].append(float(r[4]))
    return B


def coin_bars(kaynak, sym, dur, now):
    return {tf: bars_from_rows(veri_cek(kaynak, sym, iv, ADET[iv]), dur[tf], now) for tf, iv, _ in TFLER}


def yerel_bars():
    """onchain-btc/data/klines_1h.csv → 1H, 4H, 1G, 1W (BTC spot; test için)."""
    p = os.path.join(KLASOR, "..", "onchain-btc", "data", "klines_1h.csv")
    H = dict(t=[], o=[], h=[], l=[], c=[])
    with open(p, encoding="utf-8") as f:
        next(f)
        for ln in f:
            a = ln.strip().split(",")
            H['t'].append(int(a[0]))
            for k, v in zip("ohlc", a[1:5]):
                H[k].append(float(v))

    def agg(dur_ms, origin):
        A = dict(t=[], o=[], h=[], l=[], c=[])
        cur = None
        for k in range(len(H['t'])):
            b = (H['t'][k] - origin) // dur_ms * dur_ms + origin
            if b != cur:
                cur = b
                for x in "tohlc":
                    A[x].append(b if x == "t" else H[x][k])
            else:
                A['h'][-1] = max(A['h'][-1], H['h'][k])
                A['l'][-1] = min(A['l'][-1], H['l'][k])
                A['c'][-1] = H['c'][k]
        return A
    pazartesi = 4 * 86400000   # 1970-01-05 Pazartesi
    return {"1H": H, "4H": agg(4 * H1, 0), "1G": agg(24 * H1, 0), "1W": agg(7 * 24 * H1, pazartesi)}


# ════════════════════════════════════════════════════════════════
# DEĞERLENDİRME (tek coin)
# ════════════════════════════════════════════════════════════════
def tara(bars, dur, poi_tf=None, yon=False, trend=None):
    """1H geçmişini yürüt; olay: dict(t=1H mum açılışı, tur, yon, metin, fiyat[, uzak]).
    yon=True (endeksler): ayrıca her TF'de yapı dönüşü (MSS) olayı; trend dict'ine son yön yazılır."""
    poi_tf = poi_tf or POI_TF
    Hb = bars["1H"]
    mods = [[tf, B, [M3(B), M5(B), M6(B), M8(B), M9(B)], 0, dur[tf]] for tf, B in bars.items() if tf in poi_tf]
    m7 = M7(bars["1G"])
    touched, near, sent6 = set(), set(), set()
    # M9 son likidite alımı (TF mum no): {tf: {1: dip alındı, −1: tepe alındı}} → POI sinyaline "lik.✓" (son LQ_WIN mum)
    son_lq = {}
    olay = []
    onceki = {}

    def ekle(t0, tur, yon, metin, c, uzak=None):
        olay.append(dict(t=t0, tur=tur, yon=yon, metin=metin, fiyat=c, uzak=uzak))

    for n in range(1, len(Hb['t'])):
        t0 = Hb['t'][n]
        for m in mods:
            tf, B, ms, j, d = m
            while j < len(B['t']) and B['t'][j] + d <= t0:      # TF mumu kapandı → işle (Pine: [1])
                for x in ms:
                    x.step(j)
                j += 1
            m[3] = j
        h, l, c = Hb['h'][n], Hb['l'][n], Hb['c'][n]
        if yon:
            for tf, B, ms, j, d in mods:
                yt = ms[1].sw.t                                    # M5 swing motoru: 1 yükseliş · −1 düşüş
                if onceki.get(tf) in (1, -1) and yt != onceki[tf]:
                    ekle(t0, "yon", yt, f"{tf} Zig Zag 1 yapısı {'YÜKSELİŞE ▲' if yt == 1 else 'DÜŞÜŞE ▼'} döndü (MSS)", c)
                onceki[tf] = yt
        ph, pl = Hb['h'][n - 1], Hb['l'][n - 1]
        for tf, B, ms, j, d in mods:
            if j < 3:
                continue
            # M9 likidite alımı: kendi sinyali + son alım mumu (POI etiketi için)
            for z in ms[4].sweeps(tf):
                if z['key'] not in sent6:
                    sent6.add(z['key'])
                    son_lq.setdefault(tf, {})[z['d']] = z['bi']
                    ekle(t0, "sinyal", z['d'], z['ad'], c)
            for x in ms:
                if isinstance(x, M6):
                    for z in x.sweeps(tf):
                        if z['key'] not in sent6:
                            sent6.add(z['key'])
                            ekle(t0, "sinyal", z['d'], z['ad'] + _rng(z), c)
                if isinstance(x, M9):
                    continue
                for z in x.zones(tf):
                    top, bot, d0, key = z['top'], z['bot'], z['d'], z['key']
                    if not z.get('onlyNear') and l <= top and h >= bot and key not in touched:
                        fromUp, fromDn = pl > top, ph < bot
                        if fromUp or fromDn:
                            ok = (d0 == 1 and fromUp) or (d0 == -1 and fromDn)
                            if ok or z['anySide']:
                                touched.add(key)
                            # GEÇİŞ KURALI (22.11): giriş mumu karşı ucu da aştı (fitil yeter) → sinyal yok
                            if ok and z.get('thru') and (l < bot if d0 == 1 else h > top):
                                ok = False
                            if ok:
                                lq = son_lq.get(tf, {}).get(d0)
                                lqt = f" lik.✓ ({j - 1 - lq} mum önce)" if lq is not None and j - 1 - lq <= LQ_WIN else ""
                                ekle(t0, "sinyal", d0, z['ad'] + _rng(z) + z['tag'] + lqt, c)
                        continue
                    if key in touched or key in near:
                        continue
                    if d0 == 1 and top < l <= top * (1 + YAKLAS / 100):
                        near.add(key)
                        ekle(t0, "yakin", 1, z['ad'] + _rng(z) + z['tag'], c, (l - top) / top * 100)
                    elif d0 == -1 and bot * (1 - YAKLAS / 100) <= h < bot:
                        near.add(key)
                        ekle(t0, "yakin", -1, z['ad'] + _rng(z) + z['tag'], c, (bot - h) / bot * 100)
        s7 = m7.bar(Hb, n)
        if any(s[0] == 1 for s in s7) and any(s[0] == -1 for s in s7):
            ekle(t0, "sinyal", 0, "⚠ AL+SAT çelişki: " + " | ".join(s[1] for s in s7), c)
        else:
            for s in s7:
                ekle(t0, "sinyal", s[0], s[1], c)
        for s in m7.near(Hb, n, YAKLAS, near):
            ekle(t0, "yakin", s[0], s[1], c, s[3])
    if trend is not None:
        for tf, B, ms, j, d in mods:
            trend[tf] = dict(zz1=ms[1].sw.t, zz2=zigzag2(B, j))
    return olay


def _rng(z):
    return f" [{fmt(z['bot'])}–{fmt(z['top'])}]"


def _ts(t):
    return dt.datetime.fromtimestamp(t / 1000, TR).strftime("%d.%m.%Y %H:%M")


def _satir(o):
    if o['tur'] == "yon":
        return f"🧭 {o['metin']}"
    if o['tur'] == "sinyal":
        ic = {1: "🟢 ▲ AL", -1: "🔴 ▼ SAT"}.get(o['yon'], "⚪")
        return f"{ic} · {o['metin']}"
    ok = "↓ desteğe" if o['yon'] == 1 else "↑ dirence"
    return f"👀 YAKLAŞTI {ok} · {o['metin']} · %{o['uzak']:.2f} uzakta"


def _esc(x):
    return x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


ENDEKS_AD = ("TOTAL", "TOTAL2", "BTC.D", "USDT.D")


def _ok(d):
    return "▲" if d == 1 else "▼" if d == -1 else "–"


def _yon_tablosu(trendler, fiyat):
    """Her endeks: <b>TOTAL</b> 2.090T / 4H ZZ1 ▼ ZZ2 ▲ · 1G … (HTML). ZZ1 = baştan ileri, ZZ2 = son 300 mumun ucundan."""
    sat = ["<i>ZZ1 = Zig Zag 1 (baştan) · ZZ2 = Zig Zag 2 (son 300 mumun ucundan)</i>"]
    for ad in ENDEKS_AD:
        if ad not in trendler:
            continue
        tr = trendler[ad]
        px = fiyat.get(ad)
        parca = []
        for tf in POI_TF:
            x = tr.get(tf)
            if not x:
                continue
            z1, z2 = x['zz1'], x['zz2'][0]
            uyum = " ✅" if z1 == z2 and z1 != 0 else " ⚠️" if z1 and z2 else ""
            parca.append(f"{tf} ZZ1 {_ok(z1)} ZZ2 {_ok(z2)}{uyum}")
        sat.append(f"<b>{ad}</b> {_esc(fmt(px)) if px else ''}\n   " + " | ".join(parca))
    return "\n".join(sat)


def mesaj(olaylar, kaynak, sinir=3800, endeks=None):
    """olaylar: [(coin, olay)] → mum (saat) başına tek mesaj; coin başına grup; sinyaller önce. Uzunsa bölünür.
    endeks = (trendler, fiyatlar) → PİYASA YÖNÜ mesajı (HTML: kalın adlar + yön tablosu)."""
    by = {}
    for coin, o in olaylar:
        by.setdefault(o['t'], {}).setdefault(coin, []).append(o)
    out = []
    sira = {"yon": 0, "sinyal": 1, "yakin": 2}
    for t in sorted(by):
        if endeks:
            bas = f"🧭🧭 <b>PİYASA YÖNÜ</b> · {_ts(t)}–{_ts(t + H1)[-5:]} TR\n{_yon_tablosu(*endeks)}"
        else:
            bas = f"🕐 {_ts(t)}–{_ts(t + H1)[-5:]} TR · {len(by[t])} coin"
        bloklar = []
        coinler = sorted(by[t].items(), key=lambda kv: -sum(o['tur'] != "yakin" for o in kv[1]))
        for coin, os_ in coinler:
            os_ = sorted(os_, key=lambda o: sira[o['tur']])
            if endeks:
                bloklar.append("\n".join([f"\n<b>🧭 {coin}</b> · {_esc(fmt(os_[0]['fiyat']))}"] + [_esc(_satir(o)) for o in os_]))
            else:
                bloklar.append("\n".join([f"\n{coin} · {fmt(os_[0]['fiyat'])}"] + [_satir(o) for o in os_]))
        if endeks:
            son = "\n<i>(endeksler Binance + CoinGecko verisinden hesaplanır; TV değerlerinden biraz farklı olabilir)</i>"
        else:
            son = f"\n(veri: {kaynak} · POI TF: {', '.join(POI_TF)} · karar 15m'de SENİN)"
        cur = bas
        for b in bloklar:
            if len(cur) + len(b) + len(son) > sinir:
                out.append(cur + son)
                cur = bas + " (devam)"
            cur += "\n" + b
        out.append(cur + son)
    return out


# ════════════════════════════════════════════════════════════════
# BİLDİRİM
# ════════════════════════════════════════════════════════════════
def telegram(text, html=False):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not tok or not chat:
        return False
    q = {"chat_id": chat, "text": text}
    if html:
        q["parse_mode"] = "HTML"
    data = urllib.parse.urlencode(q).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=20)
    return True


def ntfy(text, onemli=False):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return False
    if onemli:     # piyasa yönü: yüksek öncelik (ayrı ses / banner), pusula simgesi
        hd = {"Title": "YON - piyasa yonu (TOTAL / BTC.D / USDT.D)", "Tags": "compass,rotating_light", "Priority": "high"}
        for x, y in (("<b>", ""), ("</b>", ""), ("<i>", ""), ("</i>", ""), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
            text = text.replace(x, y)
    else:
        hd = {"Title": "PA tarayici", "Tags": "chart_with_upwards_trend"}
    req = urllib.request.Request(f"https://ntfy.sh/{urllib.parse.quote(topic)}", data=text.encode("utf-8"), headers=hd)
    urllib.request.urlopen(req, timeout=20)
    return True


def gonder(metinler, onemli=False):
    for m in metinler:
        kanallar = []
        for ad, fn in (("Telegram", lambda x: telegram(x, html=onemli)), ("ntfy", lambda x: ntfy(x, onemli))):
            try:
                if fn(m):
                    kanallar.append(ad)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ {ad} hatası: {e}", file=sys.stderr)
        print(("✓ gönderildi: " + ", ".join(kanallar)) if kanallar else "⚠ hiçbir kanal tanımlı değil (TG_TOKEN/TG_CHAT, NTFY_TOPIC)")
        time.sleep(1)


# ════════════════════════════════════════════════════════════════
# ANA
# ════════════════════════════════════════════════════════════════
def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    now = int(time.time() * 1000)
    dur = {tf: m * 60000 for tf, _, m in TFLER}
    mod = argv[0] if argv else ""

    if mod == "--yerel":
        bars = yerel_bars()
        a = int(dt.datetime.fromisoformat(argv[1]).replace(tzinfo=TR).timestamp() * 1000)
        b = int(dt.datetime.fromisoformat(argv[2]).replace(tzinfo=TR).timestamp() * 1000)
        ol = [("BTC", o) for o in tara(bars, dur) if a <= o['t'] < b]
        print("\n\n".join(mesaj(ol, "yerel BTC spot CSV")) or "olay yok")
        return

    t_bas = time.time()
    kaynak, syms = kaynak_sec()
    piyasa = cg_markets()
    coinler = coin_listesi(syms, piyasa)
    if ENDEKS and "BTC" not in [c[0] for c in coinler]:
        coinler = [("BTC", "BTCUSDT", 1, None)] + coinler
    if not os.environ.get("COINLER") and piyasa:
        with open(COIN_YEDEK, "w", encoding="utf-8") as f:     # sonraki CoinGecko hatası için yedek
            json.dump([c[0] for c in coinler], f)
    print(f"Kaynak: {kaynak[2]} · {len(coinler)} coin: {', '.join(c[0] for c in coinler)}")

    tum, son, hata, tum_bars, katlar = [], None, [], {}, {}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        isler = {ex.submit(coin_bars, kaynak, sym, dur, now): (coin, sym, kat, px) for coin, sym, kat, px in coinler}
        for fut in cf.as_completed(isler):
            coin, sym, kat, px = isler[fut]
            try:
                bars = fut.result()
                if len(bars["1H"]['t']) < 50:
                    continue
                if px and abs(bars["1H"]['c'][-1] / px - 1) > 0.25:     # aynı kısaltma, farklı coin
                    hata.append(f"{coin}: fiyat uyuşmuyor (CoinGecko {fmt(px)} / {sym} {fmt(bars['1H']['c'][-1])})")
                    continue
                son = max(son or 0, bars["1H"]['t'][-1])
                tum_bars[coin], katlar[coin] = bars, kat
                for o in tara(bars, dur):
                    tum.append((coin, o))
            except Exception as e:  # noqa: BLE001
                hata.append(f"{coin}: {e}")
    if hata:
        print("⚠ atlanan coinler: " + " | ".join(hata), file=sys.stderr)
    if son is None:
        raise RuntimeError("Hiç coin taranamadı")

    # ── piyasa yönü: TOTAL / TOTAL2 / BTC.D / USDT.D
    yon_ol, trendler, efiyat = [], {}, {}
    if ENDEKS and piyasa:
        try:
            gl = cg_global()
            if not gl:
                raise RuntimeError("CoinGecko toplam piyasa değeri yok")
            toplam = gl["total"]
            arz, btc_mcap = {}, None
            for c in piyasa:
                sb = (c.get("symbol") or "").upper()
                if sb in tum_bars and sb not in arz and c.get("circulating_supply"):
                    arz[sb] = (c["circulating_supply"], katlar[sb])
                    if sb == "BTC":
                        btc_mcap = c.get("market_cap")
            stb = stabil_veri(piyasa)
            if btc_mcap:
                arz["BTC"] = (btc_mcap / tum_bars["BTC"]["1H"]['c'][-1], 1)     # CoinGecko BTC değeriyle tutarlı
                eb = endeks_bars(tum_bars, arz, btc_mcap, toplam, stb)
                for ad in ENDEKS_AD:
                    if ad in eb:
                        tr = {}
                        for o in tara(eb[ad], dur, yon=True, trend=tr):
                            yon_ol.append((ad, o))
                        trendler[ad] = tr
                        efiyat[ad] = eb[ad]["1H"]['c'][-1]
                cgp = gl["pct"]
                print("Endeks (şimdi): " + " · ".join(f"{a} {fmt(efiyat[a])}" for a in efiyat)
                      + f" | CoinGecko: toplam {fmt(toplam)} · BTC.D {cgp['btc']:.2f} · USDT.D {cgp.get('usdt', 0):.2f}")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ endeksler hesaplanamadı: {e}", file=sys.stderr)

    if mod == "--son":
        saat = int(argv[1]) if len(argv) > 1 else 24
        sy = [x for x in yon_ol if x[1]['t'] > son - saat * H1]
        sec = [x for x in tum if x[1]['t'] > son - saat * H1]
        print("\n\n".join(mesaj(sy, kaynak[2], endeks=(trendler, efiyat)) + mesaj(sec, kaynak[2])) or "olay yok")
        print(f"\n[{len(sy)} endeks + {len(sec)} coin olayı · {time.time() - t_bas:.0f} sn]")
        return

    durum = {}
    if os.path.exists(DURUM):
        with open(DURUM, encoding="utf-8") as f:
            durum = json.load(f)
    bas = max(durum.get("son_mum", son - H1), son - 6 * H1)    # en fazla son 6 saat (kaçan çalıştırmalar)
    yeni_y = [x for x in yon_ol if bas < x[1]['t'] <= son]
    yeni = [x for x in tum if bas < x[1]['t'] <= son]
    m_y = mesaj(yeni_y, kaynak[2], endeks=(trendler, efiyat))
    m_c = mesaj(yeni, kaynak[2])
    print(f"Son kapanan 1H mumu: {_ts(son)}–{_ts(son + H1)[-5:]} TR · yeni: {len(yeni_y)} endeks + {len(yeni)} coin olayı · {time.time() - t_bas:.0f} sn")
    if m_y or m_c:
        print("\n\n".join(m_y + m_c))
        if mod != "--kuru":
            gonder(m_y, onemli=True)
            gonder(m_c)
    if mod != "--kuru":
        with open(DURUM, "w", encoding="utf-8") as f:
            json.dump({"son_mum": son, "zaman": _ts(now)}, f)


if __name__ == "__main__":
    main(sys.argv[1:])
