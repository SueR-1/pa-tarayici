"""
endeks.py — TOTAL / TOTAL2 / BTC.D / USDT.D mumlarını Binance + CoinGecko verisinden kurar (TradingView'siz).

Yöntem (yaklaşık; TV CRYPTOCAP değerleriyle birebir değil, yön / yapı aynı):
  BTC      = BTC fiyatı × dolaşımdaki arz (CoinGecko, bugünkü)
  ALT      = taranan diğer coinlerin (fiyat × arz) toplamı, ZİNCİRLEME endeks: her mumda sadece bir önceki
             mumda da verisi olan coinler kullanılır → yeni listelenen coin sıçrama yapmaz.
             Son değer, CoinGecko toplam piyasa değerinden (BTC + stabiller düşülerek) ölçeklenir →
             listede olmayan coinler de aynı oranda hareket etmiş sayılır.
  STABİL   = USDT ve USDC piyasa değeri geçmişi (CoinGecko: son 90 gün saatlik, 1 yıl günlük; daha eskisi
             ilk değer) + diğer stabiller (bugünkü değer, sabit).
  TOTAL    = BTC + ALT + STABİL        · TOTAL2 = TOTAL − BTC (TV ile aynı tanım)
  BTC.D    = BTC / TOTAL × 100         · USDT.D = USDT / TOTAL × 100
  Mum tepe / dip: toplamlarda coinlerin tepe / dip toplamı; dominanslarda olası en uç oranlar.
"""
import bisect


class StabilSeri:
    def __init__(self, seriler, diger_simdi):
        self.s = {k: sorted(v) for k, v in seriler.items()}
        self.zaman = {k: [x[0] for x in v] for k, v in self.s.items()}
        self.diger = diger_simdi

    def deger(self, ad, t):
        s = self.s.get(ad)
        if not s:
            return 0.0
        k = bisect.bisect_right(self.zaman[ad], t) - 1
        return s[max(k, 0)][1]

    def toplam(self, t):
        return sum(self.deger(k, t) for k in self.s) + self.diger


def endeks_bars(coin_bars, arz, btc_mcap, toplam_simdi, stabil):
    """
    coin_bars : {coin: {tf: bars}}  (BTC dahil)
    arz       : {coin: (dolaşımdaki arz, kat)}  kat = Binance sembol çarpanı (1000PEPE → 1000)
    btc_mcap  : CoinGecko BTC piyasa değeri (şimdi)
    toplam_simdi : CoinGecko toplam piyasa değeri (şimdi)
    stabil    : StabilSeri
    → {"TOTAL": {tf: bars}, "TOTAL2": …, "BTC.D": …, "USDT.D": …}
    """
    if "BTC" not in coin_bars or "BTC" not in arz:
        return {}
    out = {k: {} for k in ("TOTAL", "TOTAL2", "BTC.D", "USDT.D")}
    alts = [c for c in coin_bars if c != "BTC" and c in arz and arz[c][0]]
    for tf, BB in coin_bars["BTC"].items():
        T = BB['t']
        if len(T) < 10:
            continue
        sB = arz["BTC"][0]
        idx = {c: {t: k for k, t in enumerate(coin_bars[c][tf]['t'])} for c in alts if tf in coin_bars[c]}
        A = dict(o=[], h=[], l=[], c=[])
        V = None
        for n, t in enumerate(T):
            so = sh = sl = sc = scp = 0.0
            ilk = 0.0
            for c in alts:
                k = idx.get(c, {}).get(t)
                if k is None:
                    continue
                b = coin_bars[c][tf]
                m = arz[c][0] / arz[c][1]
                ilk += b['c'][k] * m
                if n > 0 and k > 0 and b['t'][k - 1] == T[n - 1]:
                    so += b['o'][k] * m
                    sh += b['h'][k] * m
                    sl += b['l'][k] * m
                    sc += b['c'][k] * m
                    scp += b['c'][k - 1] * m
            if V is None:
                if ilk <= 0:
                    A['o'].append(None)
                    A['h'].append(None)
                    A['l'].append(None)
                    A['c'].append(None)
                    continue
                V = ilk
                A['o'].append(V)
                A['h'].append(V)
                A['l'].append(V)
                A['c'].append(V)
                continue
            r = V / scp if scp > 0 else None
            if r is None:
                A['o'].append(V)
                A['h'].append(V)
                A['l'].append(V)
                A['c'].append(V)
                continue
            A['o'].append(so * r)
            A['h'].append(sh * r)
            A['l'].append(sl * r)
            A['c'].append(sc * r)
            V = sc * r
        if V is None:
            continue
        st_simdi = stabil.toplam(T[-1])
        f = max(toplam_simdi - btc_mcap - st_simdi, 0) / V
        TOT = dict(t=[], o=[], h=[], l=[], c=[])
        TO2 = dict(t=[], o=[], h=[], l=[], c=[])
        BD = dict(t=[], o=[], h=[], l=[], c=[])
        UD = dict(t=[], o=[], h=[], l=[], c=[])
        for n, t in enumerate(T):
            if A['c'][n] is None:
                continue
            st = stabil.toplam(t)
            ut = stabil.deger("USDT", t)
            bo, bh, bl, bc = (BB[x][n] * sB for x in "ohlc")
            ao, ah, al, ac = (A[x][n] * f for x in "ohlc")
            to, th, tl, tc = bo + ao + st, bh + ah + st, bl + al + st, bc + ac + st
            for D, v in ((TOT, (to, th, tl, tc)), (TO2, (ao + st, ah + st, al + st, ac + st))):
                D['t'].append(t)
                D['o'].append(v[0])
                D['h'].append(v[1])
                D['l'].append(v[2])
                D['c'].append(v[3])
            bdo, bdc = bo / to * 100, bc / tc * 100
            adayB = (bh / (bh + al + st) * 100, bl / (bl + ah + st) * 100)
            BD['t'].append(t)
            BD['o'].append(bdo)
            BD['c'].append(bdc)
            BD['h'].append(max(bdo, bdc, adayB[0]))
            BD['l'].append(min(bdo, bdc, adayB[1]))
            udo, udc = ut / to * 100, ut / tc * 100
            UD['t'].append(t)
            UD['o'].append(udo)
            UD['c'].append(udc)
            UD['h'].append(max(udo, udc, ut / tl * 100))
            UD['l'].append(min(udo, udc, ut / th * 100))
        out["TOTAL"][tf], out["TOTAL2"][tf], out["BTC.D"][tf], out["USDT.D"][tf] = TOT, TO2, BD, UD
    return {k: v for k, v in out.items() if "1H" in v and "1G" in v}
