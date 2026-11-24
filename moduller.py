"""
moduller.py — TradingView M3 … M10 Pine modüllerinin Python karşılığı.
21.11 ilk · 22.11 eşitleme · 25.11 EŞİTLEME: yeni M3 (2 temas, IFVG yok) · YENİ M4 range · M5 (KYK kuralı, çift yutan,
swing OB, ★ likidite, sinyal filtresi, gövde bölgesi; iç OB = M8 sınıfı → "M5 iç OB") · YENİ M10 OTE.

Her modül kendi zaman diliminin KAPANMIŞ mumlarını sırayla işler (Pine'daki request.security + [1]).
Bar listesi: B = dict(t=[açılış ms], o=[], h=[], l=[], c=[], v=[hacim]) ; mum i işlenir.
Kutu modülleri (M5, M8, M10) zones(tf) → 1H temas döngüsü · olay modülleri (M3, M4) olaylar(tf) · M6 / M9 sweeps(tf).
Modül ayarları TV varsayılanlarıyla aynıdır. ATR / volatilite yok.
"""


import math


def fmt(x):
    """Fiyat: BTC 68,722.6 · ETH 3,120.6 · PEPE 0.000012345 (≈5 anlamlı basamak, en az 1 ondalık)."""
    if x is None or x <= 0:
        return str(x)
    if x >= 1e12:
        return f"{x / 1e12:.3f}T"
    if x >= 1e9:
        return f"{x / 1e9:,.1f}B"
    d = max(1, 4 - int(math.floor(math.log10(x))))
    return f"{x:,.{d}f}"


# ════════════════════════════════════════════════════════════════
# SWING MOTORU (M2 / M3 / M5 / M6 ortak — pa_sinyal f_htf kuralları)
# ════════════════════════════════════════════════════════════════
class Swing:
    def __init__(self):
        self.t = 0
        self.sH = self.sL = None
        self.xH = self.xHb = self.xHl = None
        self.tConf = False
        self.pL = self.pLb = None
        self.swH = self.swHb = None
        self.xL = self.xLb = self.xLh = None
        self.bConf = False
        self.pH = self.pHb = None
        self.swL = self.swLb = None
        self.run = 0

    def init(self, d, i, h, l):
        """M2 f_init: d = 1 dipten yükseliş, −1 tepeden düşüş (Zig Zag 2 başlangıcı)."""
        if d == 1:
            self.t, self.sL = 1, l
            self.xH, self.xHb, self.xHl = h, i, l
            self.pL, self.pLb = l, i
            self.tConf = False
        else:
            self.t, self.sH = -1, h
            self.xL, self.xLb, self.xLh = l, i, h
            self.pH, self.pHb = h, i
            self.bConf = False

    def step(self, i, h, l, c):
        r = dict(bull=False, bear=False, kind=0, liq=False, lgP=None, lgB=None,
                 hp=None, hpB=None, lp=None, lpB=None)
        s = self
        if s.t == 0:
            s.t = 1
            s.sL = l
            s.xH, s.xHb, s.xHl = h, i, l
            s.pL, s.pLb = l, i
        elif s.t == 1:
            if not s.tConf:
                if h > s.xH:
                    s.xH, s.xHb, s.xHl = h, i, l
                    s.pL, s.pLb = l, i
                elif l < s.pL:
                    s.pL, s.pLb = l, i
                if c < s.xHl:
                    s.sH = s.xH
                    s.tConf = True
                    s.swH = None
                    r['hp'], r['hpB'] = s.xH, s.xHb
            else:
                if l < s.pL:
                    s.pL, s.pLb = l, i
                if s.sH is not None and h > s.sH and c <= s.sH and (s.swH is None or h > s.swH):
                    s.swH, s.swHb = h, i
            if s.tConf and s.sH is not None and c > s.sH:
                r.update(bull=True, kind=1, lgP=s.pL, lgB=s.pLb,
                         liq=(s.sL is not None and s.pL < s.sL), lp=s.pL, lpB=s.pLb)
                s.sL = s.pL
                s.xH, s.xHb, s.xHl = h, i, l
                s.pL, s.pLb = l, i
                s.tConf = False
                s.swH = None
            elif s.sL is not None and c < s.sL:
                useSw = s.swH is not None and s.swH > s.xH
                lgP = s.swH if useSw else s.xH
                lgB = s.swHb if useSw else s.xHb
                r.update(bear=True, kind=2, lgP=lgP, lgB=lgB, liq=useSw, hp=lgP, hpB=lgB)
                s.sH = lgP
                s.run += 1
                s.t = -1
                s.xL, s.xLb, s.xLh = l, i, h
                s.pH, s.pHb = h, i
                s.bConf = False
                s.swL = None
        else:
            if not s.bConf:
                if l < s.xL:
                    s.xL, s.xLb, s.xLh = l, i, h
                    s.pH, s.pHb = h, i
                elif h > s.pH:
                    s.pH, s.pHb = h, i
                if c > s.xLh:
                    s.sL = s.xL
                    s.bConf = True
                    s.swL = None
                    r['lp'], r['lpB'] = s.xL, s.xLb
            else:
                if h > s.pH:
                    s.pH, s.pHb = h, i
                if s.sL is not None and l < s.sL and c >= s.sL and (s.swL is None or l < s.swL):
                    s.swL, s.swLb = l, i
            if s.bConf and s.sL is not None and c < s.sL:
                r.update(bear=True, kind=1, lgP=s.pH, lgB=s.pHb,
                         liq=(s.sH is not None and s.pH > s.sH), hp=s.pH, hpB=s.pHb)
                s.sH = s.pH
                s.xL, s.xLb, s.xLh = l, i, h
                s.pH, s.pHb = h, i
                s.bConf = False
                s.swL = None
            elif s.sH is not None and c > s.sH:
                useSw = s.swL is not None and s.swL < s.xL
                lgP = s.swL if useSw else s.xL
                lgB = s.swLb if useSw else s.xLb
                r.update(bull=True, kind=2, lgP=lgP, lgB=lgB, liq=useSw, lp=lgP, lpB=lgB)
                s.sL = lgP
                s.run += 1
                s.t = 1
                s.xH, s.xHb, s.xHl = h, i, l
                s.pL, s.pLb = l, i
                s.tConf = False
                s.swH = None
        return r


def zigzag2(B, n, N=300):
    """M2 Zig Zag 2 ("Son N mumun uç noktası"): ilk n kapanmış mumda son N mumun en yüksek tepesi / en düşük
    dibi; daha ESKİ olan başlangıç (tepe eskiyse düşüş, dip eskiyse yükseliş); oradan swing kurallarıyla ileri.
    → (yön 1 / −1 / 0, başlangıç mum zamanı, başlangıç fiyatı)"""
    if n < 3:
        return 0, None, None
    H, L, C = B['h'], B['l'], B['c']
    hk = lk = n - 1
    for j in range(n - 1, max(n - N, 0) - 1, -1):
        if H[j] > H[hk]:
            hk = j
        if L[j] < L[lk]:
            lk = j
    j0 = min(hk, lk)
    d = -1 if hk < lk else 1
    if j0 >= n - 1:
        return d, B['t'][j0], H[j0] if d == -1 else L[j0]
    s = Swing()
    s.init(d, j0, H[j0], L[j0])
    for j in range(j0 + 1, n):
        s.step(j, H[j], L[j], C[j])
    return s.t, B['t'][j0], H[j0] if d == -1 else L[j0]


def _keep(lst, n, live=lambda z: True, nDead=None, side='d'):
    """Yön başına en yeni n kaydı tut (liste eskiden yeniye)."""
    cnt = {}
    out = []
    for z in reversed(lst):
        lv = live(z)
        k = (z[side], lv)
        cnt[k] = cnt.get(k, 0) + 1
        lim = n if lv else (nDead if nDead is not None else n)
        if cnt[k] <= lim:
            out.append(z)
    out.reverse()
    return out


# ════════════════════════════════════════════════════════════════
# M3 — FVG / IMB (24.11.2026 kural seti · pa-okul/03-kural/kural-02-fvg.md · IFVG YOK)
#  Sinyal kendi TF mumunda (Pine: grafik TF = FVG TF): önceki mum dışarıda (kenara eşit dahil) + bu mum değdi.
#  En fazla 2 temas · tek seferde fitil dahil geçiş → sinyal yok + sil · %51+ fitil dolumu → (giriş mumuysa önce
#  sinyal) sil · uzak kenar ötesi gövde kapanışı → sil · kutu ≥ fiyatın %0,1'i · 3 aynı renk · yön başına 5.
# ════════════════════════════════════════════════════════════════
class M3:
    ad = "M3"
    poi = True

    def __init__(self, B, keepN=5, minPct=0.1, usedPct=51, sigMax=2, thruOn=True, sameC=True):
        self.B = B
        self.keepN, self.minPct, self.usedPct, self.sigMax = keepN, minPct, usedPct, sigMax
        self.thruOn, self.sameC = thruOn, sameC
        self.Z = []
        self.sw = Swing()
        self.ev = []

    def step(self, i):
        B = self.B
        O, H, L, C, T = B['o'], B['h'], B['l'], B['c'], B['t']
        self.sw.step(i, H[i], L[i], C[i])
        tr = self.sw.t
        keep = []
        for z in self.Z:
            d, zt, zb = z['d'], z['top'], z['bot']
            fl = (zt - zb) * self.usedPct / 100
            kill = False
            touch = L[i] <= zt if d == 1 else H[i] >= zb
            out = i >= 1 and ((L[i - 1] >= zt) if d == 1 else (H[i - 1] <= zb))
            fil = (d == 1 and L[i] < zt - fl) or (d == -1 and H[i] > zb + fl)
            if touch and out and z['e'] != i - 1:
                thru = L[i] < zb if d == 1 else H[i] > zt
                if self.thruOn and thru:
                    kill = True                                   # tek seferde geçti → sinyal yok, sil
                else:
                    z['n'] += 1
                    z['e'] = i
                    ters = (d == 1 and tr == -1) or (d == -1 and tr == 1)
                    self.ev.append(dict(key=f"{z['s']}|{d}|{z['n']}", d=d, bi=i, top=zt, bot=zb,
                                        ad=f"M3 FVG{'+' if d == 1 else '-'}",
                                        tag=f" · {z['n']}. temas" + (f" (%{self.usedPct}+ doldu → kullanıldı)" if fil else "")
                                        + (" ⚠ trend tersi" if ters else "")))
                    if z['n'] >= self.sigMax:
                        kill = True
            if not kill and fil:
                kill = True
            if not kill and ((d == 1 and C[i] < zb) or (d == -1 and C[i] > zt)):
                kill = True
            if not kill:
                keep.append(z)
        self.Z = keep
        if i >= 2:
            allG = all(C[k] > O[k] for k in (i, i - 1, i - 2))
            allR = all(C[k] < O[k] for k in (i, i - 1, i - 2))
            mn = C[i] * self.minPct / 100
            if L[i] > H[i - 2] and L[i] - H[i - 2] >= mn and (not self.sameC or allG):
                self.Z.append(dict(top=L[i], bot=H[i - 2], d=1, s=T[i - 2], n=0, e=-1))
            if H[i] < L[i - 2] and L[i - 2] - H[i] >= mn and (not self.sameC or allR):
                self.Z.append(dict(top=L[i - 2], bot=H[i], d=-1, s=T[i - 2], n=0, e=-1))
        self.Z = _keep(self.Z, self.keepN)

    def olaylar(self, tf):
        ev, self.ev = self.ev, []
        for z in ev:
            z['key'] = f"M3|{tf}|{z['key']}"
            z['ad'] = f"{tf} {z['ad']}"
        return ev


def _zz_noktasi(obj, r, i):
    """Zig zag noktalarını birleştir (aynı türden daha uç → taşınır). obj: PH, PHb, PL, PLb, lastTyp."""
    if r['hp'] is not None:
        if obj.lastTyp == 1:
            if r['hp'] > obj.PH:
                obj.PH, obj.PHb = r['hp'], r['hpB']
        else:
            obj.PH, obj.PHb, obj.lastTyp = r['hp'], r['hpB'], 1
    if r['lp'] is not None:
        if obj.lastTyp == -1:
            if r['lp'] < obj.PL:
                obj.PL, obj.PLb = r['lp'], r['lpB']
        else:
            obj.PL, obj.PLb, obj.lastTyp = r['lp'], r['lpB'], -1


# ════════════════════════════════════════════════════════════════
# M4 — Range (24.11.2026 kural seti · pa-okul/03-kural/kural-03-range.md)
#  Kilitli range: zig zag son tepe = RH, son dip = RL; sadece İPTAL olunca yeni range (iptalden sonraki tepe + dip).
#  EQ = (RH + RL) / 2 · uç bölge = swing mumunun gövde–fitil arası · temas = bölgeye değip EQ'ya ilerleme
#  (swing noktaları da 1. temas) · toplam 3 temas = yatay (onaylı) · iptal (log): kapanış < RL·√(RL/RH) / > RH·√(RH/RL)
#  Sinyal (onaylı range): RL bölgesi teması + RL üstü kapanış ▲ / RH ▼ · sapma (dışarıda kapanış → içeri) · EQ hacimli
#  geçiş (hacim > son 20 ort. × 1,5). Kendi TF mumunda (Pine: grafik TF).
# ════════════════════════════════════════════════════════════════
class M4:
    ad = "M4"
    poi = True

    def __init__(self, B, needT=3, volLen=20, volMul=1.5):
        self.B = B
        self.needT, self.volLen, self.volMul = needT, volLen, volMul
        self.sw = Swing()
        self.PH = self.PL = self.PHb = self.PLb = None
        self.lastTyp = 0
        self.act = False
        self.cxB = None
        self.ev = []

    def _govde(self, j, ust):
        O, C = self.B['o'], self.B['c']
        return max(O[j], C[j]) if ust else min(O[j], C[j])

    def step(self, i):
        B = self.B
        O, H, L, C = B['o'], B['h'], B['l'], B['c']
        V = B.get('v')
        h, l, c = H[i], L[i], C[i]
        # Pine'daki gibi: bu mum, ÖNCEKİ muma kadar onaylanmış zig zag noktalarıyla değerlendirilir
        if not self.act and self.PH is not None and self.PL is not None and self.PH > self.PL \
                and (self.cxB is None or min(self.PHb, self.PLb) >= self.cxB):
            self.act = True
            self.rh, self.rl, self.hB, self.lB = self.PH, self.PL, self.PHb, self.PLb
            self.eq = (self.rh + self.rl) / 2
            self.hz = max(self._govde(self.hB, True), self.eq)
            self.lz = min(self._govde(self.lB, False), self.eq)
            self.cDn = self.rl * math.sqrt(self.rl / self.rh)
            self.cUp = self.rh * math.sqrt(self.rh / self.rl)
            self.outD = 0
            if self.hB < self.lB:
                rc = any(H[k] >= self.eq for k in range(self.lB + 1, i))
                self.nH, self.wH, self.nL, self.wL = 1, False, (1 if rc else 0), not rc
            else:
                rc = any(L[k] <= self.eq for k in range(self.hB + 1, i))
                self.nL, self.wL, self.nH, self.wH = 1, False, (1 if rc else 0), not rc
        if self.act:
            if c < self.cDn or c > self.cUp:
                self.act = False
                self.cxB = i
            else:
                if self.wL and h >= self.eq:
                    self.nL, self.wL = self.nL + 1, False
                if self.wH and l <= self.eq:
                    self.nH, self.wH = self.nH + 1, False
                cf = self.nH + self.nL >= self.needT
                tL = not self.wL and l <= self.lz
                tH = not self.wH and h >= self.hz
                if tL:
                    self.wL = True
                if tH:
                    self.wH = True
                if cf:
                    if tL and c >= self.rl:
                        self._ev(i, 1, "RL bölgesi teması", self.lz, self.rl)
                    if tH and c <= self.rh:
                        self._ev(i, -1, "RH bölgesi teması", self.rh, self.hz)
                    if self.outD == -1 and c >= self.rl:
                        self._ev(i, 1, "sapma: RL altı kapanış → içeri dönüş (lik. alındı)", self.lz, self.rl)
                    if self.outD == 1 and c <= self.rh:
                        self._ev(i, -1, "sapma: RH üstü kapanış → içeri dönüş (lik. alındı)", self.rh, self.hz)
                    if V and i > self.volLen:
                        va = sum(V[i - self.volLen:i]) / self.volLen
                        if va > 0 and V[i] > va * self.volMul:
                            if c > self.eq and C[i - 1] <= self.eq:
                                self._ev(i, 1, f"EQ hacimli geçiş ↑ · hacim ×{V[i] / va:.2f}", self.eq, self.eq)
                            if c < self.eq and C[i - 1] >= self.eq:
                                self._ev(i, -1, f"EQ hacimli geçiş ↓ · hacim ×{V[i] / va:.2f}", self.eq, self.eq)
                self.outD = -1 if c < self.rl else 1 if c > self.rh else 0
        r = self.sw.step(i, h, l, c)
        _zz_noktasi(self, r, i)

    def _ev(self, i, d, ne, top, bot):
        self.ev.append(dict(key=f"{self.hB}|{self.lB}|{i}|{d}|{ne[:6]}", d=d, bi=i, top=top, bot=bot,
                            ad=f"M4 range {ne}",
                            tag=f" · RH {fmt(self.rh)} / EQ {fmt(self.eq)} / RL {fmt(self.rl)} · {self.nH + self.nL} temas"))

    def olaylar(self, tf):
        ev, self.ev = self.ev, []
        for z in ev:
            z['key'] = f"M4|{tf}|{z['key']}"
            z['ad'] = f"{tf} {z['ad']}"
        return ev


# ════════════════════════════════════════════════════════════════
# M10 — OTE (0,618 – 0,786 · son zig zag bacağı) · 24.11.2026 · pa-okul/03-kural/kural-05-ote.md
#  Son nokta tepe → yükselen bacak → AL OTE · son nokta dip → SAT OTE. Bacak başına tek sinyal (ilk giriş, 1H temas
#  döngüsünde). İptal: bacak başlangıcının ötesinde gövde kapanışı. Yeni swing → yeni OTE.
# ════════════════════════════════════════════════════════════════
class M10:
    ad = "M10"
    poi = False

    def __init__(self, B, fA=0.618, fB=0.786, fM=0.705, thruOn=True):
        self.B = B
        self.fA, self.fB, self.fM, self.thruOn = fA, fB, fM, thruOn
        self.sw = Swing()
        self.PH = self.PL = self.PHb = self.PLb = None
        self.lastTyp = 0
        self.leg = None

    def step(self, i):
        B = self.B
        H, L, C, T = B['h'], B['l'], B['c'], B['t']
        r = self.sw.step(i, H[i], L[i], C[i])
        _zz_noktasi(self, r, i)
        if self.PH is None or self.PL is None or self.PH <= self.PL:
            return
        k = (self.PHb, self.PLb)
        if self.leg is None or self.leg['k'] != k:
            d = 1 if self.PHb > self.PLb else -1
            rg = self.PH - self.PL
            a = self.PH - rg * self.fA if d == 1 else self.PL + rg * self.fA
            b = self.PH - rg * self.fB if d == 1 else self.PL + rg * self.fB
            self.leg = dict(k=k, d=d, top=max(a, b), bot=min(a, b), mid=self.PH - rg * self.fM if d == 1 else self.PL + rg * self.fM,
                            org=self.PL if d == 1 else self.PH, H=self.PH, L=self.PL, t0=T[max(k)], dead=False)
        elif not self.leg['dead']:
            g = self.leg
            if (g['d'] == 1 and C[i] < g['org']) or (g['d'] == -1 and C[i] > g['org']):
                g['dead'] = True

    def zones(self, tf):
        g = self.leg
        if g is None or g['dead']:
            return []
        return [dict(key=f"M10|{tf}|{g['t0']}|{g['d']}", top=g['top'], bot=g['bot'], d=g['d'],
                     ad=f"{tf} M10 OTE {'AL' if g['d'] == 1 else 'SAT'}",
                     tag=f" · 0,705 {fmt(g['mid'])} · bacak {fmt(g['L'])} → {fmt(g['H'])}",
                     anySide=False, thru=self.thruOn, eqOut=True, poi=False)]


# ════════════════════════════════════════════════════════════════
# M5 — Order Block + Breaker + KYK/YKY + çift yutan + swing OB + ★ likidite (24.11.2026 · kural-04-ob.md)
#  İç yapı OB → M8 sınıfı (filtreli, eski M8; 24.11 M5'e taşındı, mesajda "M5 iç OB").
#  SİNYAL FİLTRESİ (kullanıcı 24.11): ★ likidite alan OB · swing OB + A kalite ana OB · KYK/YKY + çift yutan
#  (B kalite ana OB sinyal vermez). Sinyal GÖVDE bölgesine temasla (sigTop / sigBot); geçiş kuralı tüm kutuya göre.
# ════════════════════════════════════════════════════════════════
def _lqs(lv, lt, dd, o, h, l, c, tc):
    """★ likidite: yutan mum doğru renkte, fitili önceki swing dibini (dd 1) / tepesini (dd −1) geçti + içeride kapandı.
    lv / lt: seviye + onay mum no; sadece tc'den ÖNCE onaylananlar. → alınan seviye ya da None"""
    if not (c > o if dd == 1 else c < o):
        return None
    for v, t in zip(reversed(lv), reversed(lt)):
        if t < tc and ((l < v < c) if dd == 1 else (h > v > c)):
            return v
    return None


class M5:
    ad = "M5"
    poi = True

    def __init__(self, B, keepN=5, brkOn=True, kykRef=10, kykN=3, cyN=3, swLook=10, thruOn=True,
                 sgLq=True, sgSwA=True, sgKC=True, sgB=False, bodyOn=True):
        self.B = B
        self.keepN, self.brkOn = keepN, brkOn
        self.kykRef, self.kykN, self.cyN, self.swLook = kykRef, kykN, cyN, swLook
        self.thruOn = thruOn
        self.sgLq, self.sgSwA, self.sgKC, self.sgB, self.bodyOn = sgLq, sgSwA, sgKC, sgB, bodyOn
        self.R, self.P, self.Q = [], [], []
        self.SW, self.SLv, self.SLt, self.SHv, self.SHt = [], [], [], [], []
        self.sw = Swing()
        self.PH = self.PL = None
        self.lastTyp = 0

    def step(self, i):
        B = self.B
        O, H, L, C, T = B['o'], B['h'], B['l'], B['c'], B['t']
        if i < 8:
            return
        h, l, c = H[i], L[i], C[i]
        r = self.sw.step(i, h, l, c)
        rH, rL = self.PH, self.PL
        # önceki swing noktaları (swing OB) + likidite seviyeleri (★)
        if r['hp'] is not None:
            self.SW.append(r['hp'])
            self.SHv.append(r['hp'])
            self.SHt.append(i)
        if r['lp'] is not None:
            self.SW.append(r['lp'])
            self.SLv.append(r['lp'])
            self.SLt.append(i)
        self.SW = self.SW[-(self.swLook + 2):]
        self.SHv, self.SHt = self.SHv[-self.swLook:], self.SHt[-self.swLook:]
        self.SLv, self.SLt = self.SLv[-self.swLook:], self.SLt[-self.swLook:]
        if r['hp'] is not None:
            if self.lastTyp == 1:
                if r['hp'] > self.PH:
                    self.PH = r['hp']
            else:
                self.PH, self.lastTyp = r['hp'], 1
        if r['lp'] is not None:
            if self.lastTyp == -1:
                if r['lp'] < self.PL:
                    self.PL = r['lp']
            else:
                self.PL, self.lastTyp = r['lp'], -1

        def lqs(dd, j):
            return _lqs(self.SLv, self.SLt, 1, O[j], H[j], L[j], C[j], j) if dd == 1 else \
                _lqs(self.SHv, self.SHt, -1, O[j], H[j], L[j], C[j], j)

        def tst(z):
            if l <= z['top'] and h >= z['bot'] and not (L[i - 1] <= z['top'] and H[i - 1] >= z['bot']):
                z['test'] += 1

        def thru(z):
            d = z['d']
            return self.thruOn and z['test'] == 0 and (
                (d == 1 and L[i - 1] > z['top'] and l < z['bot']) or (d == -1 and H[i - 1] < z['bot'] and h > z['top']))

        # ── KYK / YKY + çift yutan kutuları (onaylı): geçiş → ters rol (ters ise sil) · gövde kırılımı → sil · test
        keep = []
        for z in self.Q:
            th = thru(z)
            if th and not z['inv']:
                z.update(d=-z['d'], test=0, inv=True)
            elif th or (z['d'] == -1 and c > z['top']) or (z['d'] == 1 and c < z['bot']):
                continue
            else:
                tst(z)
            keep.append(z)
        self.Q = keep
        if i >= 4 + self.kykRef:
            # KYK / YKY (24.11): GÖVDEYE göre 2. mum 1.'yi, 3. mum 2.'yi yutar + 3. mum ilk ikisinden ayrı ayrı büyük
            r1, g1 = C[i - 2] < O[i - 2], C[i - 2] > O[i - 2]
            r2, g2 = C[i - 1] < O[i - 1], C[i - 1] > O[i - 1]
            r3, g3 = C[i] < O[i], C[i] > O[i]
            t1, b1 = max(O[i - 2], C[i - 2]), min(O[i - 2], C[i - 2])
            t2, b2 = max(O[i - 1], C[i - 1]), min(O[i - 1], C[i - 1])
            t3, b3 = max(O[i], C[i]), min(O[i], C[i])
            y21 = t2 >= t1 and b2 <= b1
            y32 = t3 >= t2 and b3 <= b2
            big = (t3 - b3) > (t1 - b1) and (t3 - b3) > (t2 - b2)
            if y21 and y32 and big and ((r1 and g2 and r3) or (g1 and r2 and g3)):
                ref = min(L[i - 2 - self.kykRef:i - 2]) if r1 else max(H[i - 2 - self.kykRef:i - 2])
                dd = -1 if r1 else 1
                self.P.append(dict(top=H[i - 2], bot=L[i - 2], d=dd, t0=T[i - 2], ref=ref, cy=False,
                                   lq=lqs(dd, i), bT=t1, bB=b1))
            # ÇİFT YUTAN (24.11): ≥2 ardışık aynı renk mum + ters mum hepsinin gövdesini yutar
            gY, rY = C[i] > O[i], C[i] < O[i]
            if gY or rY:
                k = i - 1
                mT = mB = bxT = bxB = None
                while k >= 0 and i - k <= 60 and (C[k] < O[k] if gY else C[k] > O[k]):
                    mT = max(O[k], C[k]) if mT is None else max(mT, O[k], C[k])
                    mB = min(O[k], C[k]) if mB is None else min(mB, O[k], C[k])
                    bxT = H[k] if bxT is None else max(bxT, H[k])
                    bxB = L[k] if bxB is None else min(bxB, L[k])
                    k -= 1
                f = k + 1
                if i - f >= 2 and f - self.kykRef >= 0 and max(O[i], C[i]) >= mT and min(O[i], C[i]) <= mB:
                    ref = max(H[f - self.kykRef:f]) if gY else min(L[f - self.kykRef:f])
                    dd = 1 if gY else -1
                    self.P.append(dict(top=bxT, bot=bxB, d=dd, t0=T[f], ref=ref, cy=True, lq=lqs(dd, i), bT=mT, bB=mB))
            self.P = self.P[-20:]
        keepP = []
        for p in self.P:
            kill = c > p['top'] if p['d'] == -1 else c < p['bot']
            okB = c < p['ref'] if p['d'] == -1 else c > p['ref']
            if kill or okB:
                if okB and not kill:
                    self.Q.append(dict(p, test=0, inv=False))
                continue
            keepP.append(p)
        self.P = keepP
        self.Q = _keep([z for z in self.Q if z['cy']], self.cyN) + _keep([z for z in self.Q if not z['cy']], self.kykN)

        # ── mevcut OB: geçiş (çalışmayan → ters rol) · kırılım (breaker / sil) · test
        keepR = []
        for z in self.R:
            d = z['d']
            if thru(z):
                if z['brk'] == 0:
                    z.update(brk=2, d=-d, test=0)
                else:
                    continue
            elif (d == 1 and c < z['bot']) or (d == -1 and c > z['top']):
                if self.brkOn and not z['brk']:
                    z.update(brk=1, d=-d, test=0)
                else:
                    continue
            else:
                tst(z)
            keepR.append(z)
        self.R = keepR

        # ── yeni OB
        for dd, mk in ((1, r['bull']), (-1, r['bear'])):
            if not mk or r['lgB'] is None:
                continue
            lgP, lgB = r['lgP'], r['lgB']
            dk = i - lgB
            if not (0 <= dk <= 290):
                continue
            ters = (lambda j: C[j] < O[j]) if dd == 1 else (lambda j: C[j] > O[j])
            best, bx = -1, None
            for k in range(max(dk - 2, 0), dk + 3):
                j = i - k
                if j < 0:
                    continue
                if ters(j) and (best < 0 or (L[j] < bx if dd == 1 else H[j] > bx)):
                    best, bx = k, (L[j] if dd == 1 else H[j])
            if best < 0:
                best = dk
            jo = i - best
            top, bot = H[jo], L[jo]
            bT, bB = max(O[jo], C[jo]), min(O[jo], C[jo])
            cnt, jl = 1, jo
            while cnt < 3 and jl - 1 >= 0 and (i - (jl - 1)) <= 295 and ters(jl - 1):
                jl -= 1
                cnt += 1
                top, bot = max(top, H[jl]), min(bot, L[jl])
                bT, bB = max(bT, O[jl], C[jl]), min(bB, O[jl], C[jl])
            isSw = bot <= lgP if dd == 1 else top >= lgP
            cln = False
            if cnt >= 2 and best >= 1:
                y = jo + 1
                cln = (C[y] > O[y] and C[y] > bT) if dd == 1 else (C[y] < O[y] and C[y] < bB)
            kyk = 0
            pv = jl - 1
            if best >= 1 and pv >= 0:
                y = jo + 1
                okK = (C[pv] > O[pv] and C[y] > O[y]) if dd == 1 else (C[pv] < O[pv] and C[y] < O[y])
                if okK:
                    kyk = dd
            imb = False
            for jj in range(1, max(best - 1, 1) + 1):
                m = i - jj + 1
                if m - 2 < 0:
                    break
                if (L[m] > H[m - 2]) if dd == 1 else (H[m] < L[m - 2]):
                    imb = True
                    break
            eq = None if rH is None or rL is None else (rH + rL) / 2
            mid = (top + bot) / 2
            okH = eq is not None and (mid <= eq if dd == 1 else mid >= eq)
            psw = next((v for v in reversed(self.SW) if v != lgP and bot <= v <= top), None)
            lq = lqs(dd, jo + 1) if jo + 1 <= i else None
            self.R.append(dict(top=top, bot=bot, d=dd, kind=r['kind'], liq=r['liq'], A=imb and okH, sw=isSw,
                               cln=cln, kyk=kyk, brk=0, test=0, t0=T[jl], bT=bT, bB=bB, psw=psw, lq=lq))
        self.R = _keep(self.R, self.keepN)

    def zones(self, tf):
        out = []
        for z in self.R:
            d = z['d']
            lk = z['brk'] == 0 and z['lq'] is not None
            swo = z['psw'] is not None
            if not ((self.sgLq and lk) or (self.sgSwA and (z['A'] or swo)) or (self.sgB and not z['A'])):
                continue
            if z['brk'] == 1:
                nm = f"M5 Breaker{'+' if d == 1 else '-'}"
            elif z['brk'] == 2:
                nm = f"M5 çalışmayan OB{'+' if d == 1 else '-'}"
            else:
                nm = f"M5 {'★ lik. ' if lk else ''}{'swing OB' if swo else 'OB'}{'+' if d == 1 else '-'} {'A' if z['A'] else 'B'}"
            tag = ""
            if z['cln']:
                tag += " ✓ temiz"
            if z['sw']:
                tag += " swing"
            tag += " MSS" if z['kind'] == 2 else " trend"
            if z['liq']:
                tag += " lik."
            if z['kyk']:
                tag += " YKY" if z['kyk'] == 1 else " KYK"
            if swo:
                tag += f" önceki swing {fmt(z['psw'])}"
            if lk:
                tag += f" · ★ GÜÇLÜ POI (2 onay: yutan mum {fmt(z['lq'])} likiditesini aldı)"
            if z['test']:
                tag += f" test {z['test']}"
            out.append(dict(key=f"M5|{tf}|{z['t0']}|{d}|{z['brk']}", top=z['top'], bot=z['bot'], d=d,
                            sigTop=z['bT'] if self.bodyOn else z['top'], sigBot=z['bB'] if self.bodyOn else z['bot'],
                            ad=f"{tf} {nm}", tag=tag, anySide=True, thru=self.thruOn))
        for z in self.Q:
            d, v = z['d'], z['inv']
            lk = not v and z['lq'] is not None
            if not (self.sgKC or (self.sgLq and lk)):
                continue
            d0 = -d if v else d
            nm = (f"çift yutan OB{'+' if d0 == 1 else '-'}" if z['cy'] else ('YKY' if d0 == 1 else 'KYK') + ("" if v else " kutusu")) \
                + (f" çalışmayan{'+' if d == 1 else '-'}" if v else "")
            tag = f" · ★ GÜÇLÜ POI (2 onay: yutan mum {fmt(z['lq'])} likiditesini aldı)" if lk else ""
            if z['test']:
                tag += f" test {z['test']}"
            out.append(dict(key=f"M5K|{tf}|{z['t0']}|{d}|{int(z['cy'])}", top=z['top'], bot=z['bot'], d=d,
                            sigTop=z['bT'] if self.bodyOn else z['top'], sigBot=z['bB'] if self.bodyOn else z['bot'],
                            ad=f"{tf} M5 {'★ lik. ' if lk else ''}{nm}", tag=tag, anySide=False, thru=self.thruOn))
        return out


# ════════════════════════════════════════════════════════════════
# M6 — EQH / EQL (sinyal = likidite alındı / sweep)
# ════════════════════════════════════════════════════════════════
class M6:
    ad = "M6"
    poi = False

    def __init__(self, B, nSw=10, keepN=5, keepD=3):
        self.B = B
        self.nSw, self.keepN, self.keepD = nSw, keepN, keepD
        self.Z, self.q = [], []
        self.sw = Swing()
        self.PH = self.PL = None
        self.lastTyp = 0

    def step(self, i):
        B = self.B
        O, H, L, C, T = B['o'], B['h'], B['l'], B['c'], B['t']
        if i < 8:
            return
        h, l, c, tt = H[i], L[i], C[i], T[i]
        for z in self.Z:
            st = z['st']
            if st < 2:
                if z['side'] == 1:
                    if c > z['top']:
                        z['st'], z['ts'] = 2, tt
                    elif st == 0 and h > z['top']:
                        z['st'], z['ts'] = 1, tt
                else:
                    if c < z['bot']:
                        z['st'], z['ts'] = 2, tt
                    elif st == 0 and l < z['bot']:
                        z['st'], z['ts'] = 1, tt
        r = self.sw.step(i, h, l, c)
        for sd, np_, npb in ((1, r['hp'], r['hpB']), (-1, r['lp'], r['lpB'])):
            if np_ is None:
                continue
            isNew = isRep = False
            if sd == 1:
                if self.lastTyp == 1:
                    if np_ > self.PH:
                        self.PH, isRep = np_, True
                else:
                    self.PH, self.lastTyp, isNew = np_, 1, True
            else:
                if self.lastTyp == -1:
                    if np_ < self.PL:
                        self.PL, isRep = np_, True
                else:
                    self.PL, self.lastTyp, isNew = np_, -1, True
            of = i - npb + 1
            if not ((isNew or isRep) and 1 <= of <= 450):
                continue
            bp = np_
            bw = max(O[npb], C[npb]) if sd == 1 else min(O[npb], C[npb])
            bT = T[npb]
            iB = -1
            if isRep:
                for j in range(len(self.q) - 1, -1, -1):
                    if self.q[j]['sd'] == sd:
                        iB = j
                        break
            if iB < 0:
                self.q.append(dict(sd=sd, p=bp, w=bw, b=npb, t=bT, z=False))
                iB = len(self.q) - 1
            else:
                self.q[iB].update(p=bp, w=bw, b=npb, t=bT, z=False)
            post = None
            if of > 1:
                seg = H[npb + 1:i + 1] if sd == 1 else L[npb + 1:i + 1]
                post = max(seg) if sd == 1 else min(seg)
            done = False
            for z in reversed(self.Z):
                if z['side'] == sd and z['st'] == 0 and z['t1'] < bT:
                    top, bot = z['top'], z['bot']
                    ov = (bw <= top and bot <= bp <= top) if sd == 1 else (bw >= bot and bot <= bp <= top)
                    pOk = post is None or (post <= top if sd == 1 else post >= bot)
                    if ov and pOk:
                        if not (bp < z['last'] if sd == 1 else bp > z['last']):
                            z['mono'] = 0
                        z['cnt'] += 1
                        z['last'] = bp
                        z['t1'] = bT
                        self.q[iB]['z'] = True
                        done = True
                        break
            if not done:
                ext = None
                cur = of + 1
                cntS = 0
                for j in range(len(self.q) - 1, -1, -1):
                    qj = self.q[j]
                    if qj['sd'] != sd or j == iB:
                        continue
                    cntS += 1
                    if cntS > self.nSw:
                        break
                    ofA = i - qj['b'] + 1
                    if ofA > 450:
                        break
                    if ofA <= of:
                        continue
                    while cur < ofA:
                        bar = i - cur + 1
                        v = H[bar] if sd == 1 else L[bar]
                        ext = v if ext is None else (max(ext, v) if sd == 1 else min(ext, v))
                        cur += 1
                    if not qj['z']:
                        aP, aW = qj['p'], qj['w']
                        ov = (aW <= bp and bw <= aP) if sd == 1 else (aP <= bw and bp <= aW)
                        clean = ext is None or (ext <= aP if sd == 1 else ext >= aP)
                        if ov and clean:
                            top = max(aP, bp) if sd == 1 else min(aW, bw)
                            bot = max(aW, bw) if sd == 1 else min(aP, bp)
                            pOk = post is None or (post <= top if sd == 1 else post >= bot)
                            if pOk:
                                self.Z.append(dict(top=top, bot=bot, side=sd, st=0, cnt=2,
                                                   mono=1 if (bp < aP if sd == 1 else bp > aP) else 0,
                                                   last=bp, t0=qj['t'], t1=bT, ts=None))
                                qj['z'] = True
                                self.q[iB]['z'] = True
                            break
            if sum(1 for x in self.q if x['sd'] == sd) > self.nSw + 1:
                for j, x in enumerate(self.q):
                    if x['sd'] == sd:
                        self.q.pop(j)
                        break
        self.Z = _keep(self.Z, self.keepN, live=lambda z: z['st'] == 0, nDead=self.keepD, side='side')

    def _nm(self, tf, z):
        lad = z['cnt'] >= 3 and z['mono'] == 1
        return f"{tf} M6 {'EQH' if z['side'] == 1 else 'EQL'} ×{z['cnt']}" + (" · merdiven · düşük önem" if lad else "")

    def sweeps(self, tf):
        """st == 1 olan (alındı) EQH/EQL'ler — sinyal anahtarı ile."""
        return [dict(key=f"M6|{tf}|{z['t0']}|{z['side']}", d=-z['side'], top=z['top'], bot=z['bot'],
                     ad=self._nm(tf, z) + " alındı (sweep)", tag="") for z in self.Z if z['st'] == 1]

    def zones(self, tf):
        """Aktif EQH/EQL — sadece YAKLAŞMA bildirimi için (giriş sinyali yok; sinyal sweep)."""
        return [dict(key=f"M6|{tf}|{z['t0']}|{z['side']}", top=z['top'], bot=z['bot'], d=-z['side'],
                     ad=self._nm(tf, z), tag="", anySide=False, onlyNear=True) for z in self.Z if z['st'] == 0]


# ════════════════════════════════════════════════════════════════
# M8 — Anlamlı iç yapı OB (likidite + FVG)
# ════════════════════════════════════════════════════════════════
class M8:
    """Filtreli iç yapı OB (eski M8) — 24.11 M5'e taşındı; mesajda 'M5 iç OB'."""
    ad = "M8"
    poi = True

    def __init__(self, B, iobRef=5, iobExp=30, iobN=3, liqOn=True, liqW=5, liqS=5, fvgOn=True,
                 wideOn=False, wideN=10, llOn=False, llS=3, newOn=True, thruOn=True):
        self.B = B
        self.newOn, self.thruOn = newOn, thruOn
        self.iobRef, self.iobExp, self.iobN = iobRef, iobExp, iobN
        self.liqOn, self.liqW, self.liqS, self.fvgOn = liqOn, liqW, liqS, fvgOn
        self.wideOn, self.wideN, self.llOn, self.llS = wideOn, wideN, llOn, llS
        self.P, self.Q, self.LH, self.LL = [], [], [], []
        self.swHb = self.swLb = self.swHv = self.swLv = None
        self.fL = self.fH = None
        self.need = max(max(iobRef, wideN), 2 * max(liqS, llS)) + 4

    def step(self, i):
        B = self.B
        O, H, L, C, T = B['o'], B['h'], B['l'], B['c'], B['t']
        if i < self.need:
            return
        h, l, c = H[i], L[i], C[i]
        # eski swing (likidite): pivot = i - liqS
        pv = i - self.liqS
        if all(H[pv] > H[pv - q] and H[pv] >= H[pv + q] for q in range(1, self.liqS + 1)):
            self.LH.append(H[pv])
        if all(L[pv] < L[pv - q] and L[pv] <= L[pv + q] for q in range(1, self.liqS + 1)):
            self.LL.append(L[pv])
        # Pine sondan başa siler → son yazılan (en eski) süpürülen değer swHv olur
        if any(h > v for v in self.LH):
            sw = [v for v in self.LH if h > v]
            self.swHb, self.swHv = i, sw[0]
            self.LH = [v for v in self.LH if not h > v]
        if any(l < v for v in self.LL):
            sw = [v for v in self.LL if l < v]
            self.swLb, self.swLv = i, sw[0]
            self.LL = [v for v in self.LL if not l < v]
        self.LH, self.LL = self.LH[-100:], self.LL[-100:]
        pf = i - self.llS
        if all(H[pf] > H[pf - q] and H[pf] >= H[pf + q] for q in range(1, self.llS + 1)):
            self.fH = H[pf]
        if all(L[pf] < L[pf - q] and L[pf] <= L[pf + q] for q in range(1, self.llS + 1)):
            self.fL = L[pf]
        # onaylılar
        keep = []
        for z in self.Q:
            d, zt, zb = z['d'], z['top'], z['bot']
            tch = l <= zt and h >= zb
            if not z['rdy']:
                # 5 YENİ L / H (22.11): önce temas → düşer; dokunmadan uç geçildi → hazır
                if tch:
                    continue
                if (d == -1 and l < z['ex']) or (d == 1 and h > z['ex']):
                    z['rdy'] = True
                keep.append(z)
                continue
            # GEÇİŞ KURALI (22.11): ilk giriş mumu karşı ucu da aştı → çalışmayan, ters rol (ters ise sil)
            th = self.thruOn and z['test'] == 0 and (
                (d == 1 and L[i - 1] > zt and l < zb) or (d == -1 and H[i - 1] < zb and h > zt))
            if th and not z['inv']:
                z.update(d=-d, test=0, inv=True)
            elif th or (d == -1 and c > zt) or (d == 1 and c < zb):
                continue
            elif tch and not (L[i - 1] <= zt and H[i - 1] >= zb):
                z['test'] += 1
            keep.append(z)
        self.Q = keep
        # bekleyenler
        keepP = []
        for p in self.P:
            pd = p['d']
            p['ex'] = min(p['ex'], l) if pd == -1 else max(p['ex'], h)
            br = p['br'] or (c < p['ref'] if pd == -1 else c > p['ref'])
            fv = p['fv'] or (i - 2 >= p['bi'] and (h < L[i - 2] if pd == -1 else l > H[i - 2]))
            gone = (h > p['top'] if pd == -1 else l < p['bot']) or i - p['bi'] > self.iobExp
            ok = br and (fv or not self.fvgOn)
            if gone or ok:
                if ok and not gone:
                    self.Q.append(dict(top=p['top'], bot=p['bot'], d=pd, t0=p['t0'], test=0,
                                       lv=self.swHv if pd == -1 else self.swLv,
                                       inv=False, ex=p['ex'], rdy=not self.newOn, bT=p['bT'], bB=p['bB']))
                continue
            p['br'], p['fv'] = br, fv
            keepP.append(p)
        self.P = keepP
        gC, rC = C[i] > O[i], C[i] < O[i]
        if gC or rC:
            dr = -1 if gC else 1
            lq = (self.swHb is not None and i - self.swHb <= self.liqW) if dr == -1 else \
                 (self.swLb is not None and i - self.swLb <= self.liqW)
            if lq or not self.liqOn:
                nR = self.wideN if self.wideOn else self.iobRef
                rf = min(L[i - nR:i]) if gC else max(H[i - nR:i])
                if self.llOn:
                    if gC and self.fL is not None:
                        rf = min(rf, self.fL)
                    if rC and self.fH is not None:
                        rf = max(rf, self.fH)
                self.P.append(dict(top=h, bot=l, d=dr, t0=T[i], ref=rf, bi=i, br=False, fv=False,
                                   ex=l if gC else h, bT=max(O[i], C[i]), bB=min(O[i], C[i])))
                if len(self.P) > 200:
                    self.P.pop(0)
        self.Q = _keep(self.Q, self.iobN, live=lambda z: z['rdy'])

    def zones(self, tf):
        tg = (" lik." if self.liqOn else "") + (" FVG" if self.fvgOn else "") + (" geniş" if self.wideOn else "")
        out = []
        for z in self.Q:
            if not z['rdy']:
                continue
            t = tg + ((" HH" if z['d'] == 1 else " LL") if self.llOn else "") + (" yeni L/H" if self.newOn else "")
            if z['test']:
                t += f" test {z['test']}"
            nm = ("M5 çalışmayan iç OB" if z['inv'] else "M5 iç OB") + ('+' if z['d'] == 1 else '-')
            out.append(dict(key=f"M8|{tf}|{z['t0']}|{z['d']}", top=z['top'], bot=z['bot'], d=z['d'],
                            sigTop=z['bT'], sigBot=z['bB'],
                            ad=f"{tf} {nm}", tag=t, anySide=False, thru=self.thruOn))
        return out


# ════════════════════════════════════════════════════════════════
# M9 — Likidite alımı (swing + range tepe / dip) · 22.11.2026
#  Zig zag noktaları = seviye; fitil öteye + içeride kapanış = alındı (sinyal), gövde öteye = kırıldı.
# ════════════════════════════════════════════════════════════════
class M9:
    ad = "M9"
    poi = False

    def __init__(self, B, keepN=5, keepD=3):
        self.B = B
        self.keepN, self.keepD = keepN, keepD
        self.Z = []
        self.sw = Swing()
        self.PH = self.PL = None
        self.lastTyp = 0

    def step(self, i):
        B = self.B
        H, L, C, T = B['h'], B['l'], B['c'], B['t']
        h, l, c = H[i], L[i], C[i]
        # 1) aktif seviyeler: alındı / kırıldı
        for z in self.Z:
            if z['st'] == 0:
                sd, lv = z['sd'], z['lv']
                if (h > lv) if sd == 1 else (l < lv):
                    brk = (c > lv) if sd == 1 else (c < lv)
                    z.update(st=2 if brk else 1, ts=T[i], bi=i, wx=h if sd == 1 else l,
                             rng=(sd == 1 and lv == self.PH) or (sd == -1 and lv == self.PL))
        # 2) swing motoru  3) yeni zig zag noktası (aynı türden daha uç → aktif seviye taşınır)
        r = self.sw.step(i, h, l, c)
        for sd, np_, npb in ((1, r['hp'], r['hpB']), (-1, r['lp'], r['lpB'])):
            if np_ is None:
                continue
            same = self.lastTyp == sd
            more = same and (np_ > self.PH if sd == 1 else np_ < self.PL)
            if same and not more:
                continue
            old = self.PH if sd == 1 else self.PL
            moved = False
            if more:
                for z in reversed(self.Z):
                    if z['sd'] == sd and z['lv'] == old and z['st'] == 0:
                        z.update(lv=np_, t0=T[npb])
                        moved = True
                        break
            if not moved:
                self.Z.append(dict(lv=np_, sd=sd, t0=T[npb], st=0, ts=None, bi=None, wx=None, rng=False))
            if sd == 1:
                self.PH = np_
            else:
                self.PL = np_
            self.lastTyp = sd
        self.Z = _keep(self.Z, self.keepN, live=lambda z: z['st'] == 0, nDead=self.keepD, side='sd')

    def sweeps(self, tf):
        """Alınan (st == 1) seviyeler: tepe alındı → SAT (−1) · dip alındı → AL (1)."""
        out = []
        for z in self.Z:
            if z['st'] != 1:
                continue
            tp = z['sd'] == 1
            nm = f"{tf} M9 swing {'tepe' if tp else 'dip'} {fmt(z['lv'])}" + \
                 ((" · range RH" if tp else " · range RL") if z['rng'] else "")
            out.append(dict(key=f"M9|{tf}|{z['t0']}|{z['sd']}", d=-z['sd'], bi=z['bi'],
                            ad=nm + f" alındı · fitil {fmt(z['wx'])}", tag=""))
        return out


# ════════════════════════════════════════════════════════════════
# M7 — Kurumsal seviyeler (W / M / Y açılış + PWH / PWL) — günlük mumlardan
# ════════════════════════════════════════════════════════════════
DAY = 86400000


class M7:
    """Seviyeleri günlük mumlardan kurar; sinyal 1H mumlarında (Pine'da grafik mumu)."""

    def __init__(self, D, wOn=True, woOn=True, mOn=True, yOn=True, depN=4):
        import datetime as _dt
        self.dt = _dt
        self.D = {t: k for k, t in enumerate(D['t'])}
        self.Db = D
        self.wOn, self.woOn, self.mOn, self.yOn, self.depN = wOn, woOn, mOn, yOn, depN
        self.st = {}

    def _open(self, ts):
        k = self.D.get(ts)
        return None if k is None else self.Db['o'][k]

    def levels(self, t):
        """1H mumu açılış zamanı t (ms) için seviye listesi: (ad, fiyat, dönem başı, grup, tür)."""
        d = self.dt.datetime.fromtimestamp(t / 1000, self.dt.timezone.utc)
        day0 = self.dt.datetime(d.year, d.month, d.day, tzinfo=self.dt.timezone.utc)
        wk0 = day0 - self.dt.timedelta(days=d.weekday())
        mo0 = self.dt.datetime(d.year, d.month, 1, tzinfo=self.dt.timezone.utc)
        yr0 = self.dt.datetime(d.year, 1, 1, tzinfo=self.dt.timezone.utc)
        ms = lambda x: int(x.timestamp() * 1000)
        lv = []

        def add(nm, p, ts, kd):
            if p is None:
                return
            for x in lv:
                if x[1] == p:
                    x[0] += " = " + nm
                    return
            lv.append([nm, p, ts, kd])

        if self.yOn:
            add("Y açılış", self._open(ms(yr0)), ms(yr0), 0)
        if self.mOn:
            add("M açılış", self._open(ms(mo0)), ms(mo0), 0)
        if self.woOn:
            add("W açılış", self._open(ms(wk0)), ms(wk0), 0)
        if self.wOn:
            pw = [self.D.get(ms(wk0) - DAY * k) for k in range(1, 8)]
            if all(k is not None for k in pw):
                add("PWH", max(self.Db['h'][k] for k in pw), ms(wk0), 1)
                add("PWL", min(self.Db['l'][k] for k in pw), ms(wk0), -1)
        return lv

    def bar(self, Hb, n):
        """1H mumu n için sinyaller: [(yön, metin, anahtar)]. Hb = 1H bar sözlüğü."""
        t, h, l, c = Hb['t'][n], Hb['h'][n], Hb['l'][n], Hb['c'][n]
        out = []
        for nm, p, ts, kd in self.levels(t):
            key = f"M7|{ts}|{p}|{kd}"
            if key in self.st or t < ts:
                continue
            txt = f"M7 {nm} {fmt(p)}"
            if kd == 1 and h > p:
                if c < p:
                    self.st[key] = 1
                    out.append((-1, txt + " · sweep", key))
                else:
                    self.st[key] = 2
            elif kd == -1 and l < p:
                if c > p:
                    self.st[key] = 1
                    out.append((1, txt + " · sweep", key))
                else:
                    self.st[key] = 2
            elif kd == 0 and l <= p <= h:
                armed = n - self.depN >= 0 and Hb['t'][n - self.depN] >= ts
                if armed:
                    for k in range(1, self.depN + 1):
                        if Hb['l'][n - k] <= p <= Hb['h'][n - k]:
                            armed = False
                            break
                if armed:
                    self.st[key] = 1
                    out.append((1 if Hb['c'][n - 1] > p else -1, txt + " · ilk temas", key))
        return out

    def near(self, Hb, n, pct, seen):
        """Seviyeye yaklaşma (dokunmadan %pct içinde) — dönem başına bir kez."""
        t, h, l = Hb['t'][n], Hb['h'][n], Hb['l'][n]
        out = []
        for nm, p, ts, kd in self.levels(t):
            key = f"M7|{ts}|{p}|{kd}"
            if key in self.st or key in seen or t < ts:
                continue
            if l > p and l <= p * (1 + pct / 100):
                seen.add(key)
                out.append((1, f"M7 {nm} {fmt(p)}", key, (l - p) / p * 100))
            elif h < p and h >= p * (1 - pct / 100):
                seen.add(key)
                out.append((-1, f"M7 {nm} {fmt(p)}", key, (p - h) / p * 100))
        return out
