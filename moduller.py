"""
moduller.py — TradingView M3 / M5 / M6 / M7 / M8 Pine modüllerinin Python karşılığı (21.11.2026).

Her modül kendi zaman diliminin KAPANMIŞ mumlarını sırayla işler (Pine'daki request.security + [1]).
Bar listesi: B = dict(t=[açılış ms], o=[], h=[], l=[], c=[]) ; mum i işlenir (Pine'da [1] = i, [2] = i-1 …).

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
# M3 — FVG / IMB + Inverse FVG (CME gap yok)
# ════════════════════════════════════════════════════════════════
class M3:
    ad = "M3"

    def __init__(self, B, keepN=5, invOn=True, usedPct=51, reactOn=True):
        self.B = B
        self.keepN, self.invOn, self.usedPct, self.reactOn = keepN, invOn, usedPct, reactOn
        self.Z = []
        self.sw = Swing()

    def step(self, i):
        B = self.B
        h, l, c = B['h'][i], B['l'][i], B['c'][i]
        self.sw.step(i, h, l, c)
        keep = []
        for z in self.Z:
            d, zt, zb = z['d'], z['top'], z['bot']
            if (d == 1 and c < zb) or (d == -1 and c > zt):
                if self.invOn and not z['inv']:
                    z.update(inv=True, d=-d, u=False, k=False)
                else:
                    continue
            elif not z['u']:
                fl = (zt - zb) * self.usedPct / 100
                if (d == 1 and l < zt - fl) or (d == -1 and h > zb + fl):
                    z['u'] = True
                else:
                    if (d == 1 and l <= zt) or (d == -1 and h >= zb):
                        z['k'] = True
                    if self.reactOn and z['k'] and ((d == 1 and c > zt) or (d == -1 and c < zb)):
                        z['u'] = True
            keep.append(z)
        self.Z = keep
        if i >= 2:
            h3, l3, t3 = B['h'][i - 2], B['l'][i - 2], B['t'][i - 2]
            if l > h3:
                self.Z.append(dict(top=l, bot=h3, d=1, inv=False, s=t3, u=False, k=False))
            if h < l3:
                self.Z.append(dict(top=l3, bot=h, d=-1, inv=False, s=t3, u=False, k=False))
        self.Z = _keep(self.Z, self.keepN, live=lambda z: not z['u'])

    def zones(self, tf):
        out = []
        tr = self.sw.t
        for z in self.Z:
            if z['u']:
                continue
            d = z['d']
            nm = f"{tf} M3 {'IFVG' if z['inv'] else 'FVG'}{'+' if d == 1 else '-'}"
            tag = " ⚠ trend tersi" if (d == 1 and tr == -1) or (d == -1 and tr == 1) else ""
            out.append(dict(key=f"M3|{tf}|{z['s']}|{d}|{'i' if z['inv'] else 'n'}", top=z['top'], bot=z['bot'],
                            d=d, ad=nm, tag=tag, anySide=True))
        return out


# ════════════════════════════════════════════════════════════════
# M5 — Order Block + Breaker + KYK/YKY kutusu + iç yapı OB
# ════════════════════════════════════════════════════════════════
class M5:
    ad = "M5"

    def __init__(self, B, keepN=5, brkOn=True, kykRef=10, kykMul=1.2, kykAvg=20, kykN=3, iobRef=5, iobN=3):
        self.B = B
        self.keepN, self.brkOn = keepN, brkOn
        self.kykRef, self.kykMul, self.kykAvg, self.kykN = kykRef, kykMul, kykAvg, kykN
        self.iobRef, self.iobN = iobRef, iobN
        self.R, self.P, self.Q, self.IP, self.IQ = [], [], [], [], []
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

        def tst(z):
            if l <= z['top'] and h >= z['bot'] and not (L[i - 1] <= z['top'] and H[i - 1] >= z['bot']):
                z['test'] += 1

        # ── KYK / YKY kutuları
        self.Q = [z for z in self.Q if not ((z['d'] == -1 and c > z['top']) or (z['d'] == 1 and c < z['bot']))]
        for z in self.Q:
            tst(z)
        if i >= 3 + self.kykRef and i >= self.kykAvg + 1:
            r1, g1 = C[i - 2] < O[i - 2], C[i - 2] > O[i - 2]
            r2, g2 = C[i - 1] < O[i - 1], C[i - 1] > O[i - 1]
            r3, g3 = C[i] < O[i], C[i] > O[i]
            yut = max(O[i], C[i]) >= max(O[i - 1], C[i - 1]) and min(O[i], C[i]) <= min(O[i - 1], C[i - 1])
            avgB = sum(abs(C[k] - O[k]) for k in range(i - self.kykAvg, i)) / self.kykAvg
            big = abs(C[i] - O[i]) >= avgB * self.kykMul
            if big and yut and ((r1 and g2 and r3) or (g1 and r2 and g3)):
                ref = min(L[i - 2 - self.kykRef:i - 2]) if r1 else max(H[i - 2 - self.kykRef:i - 2])
                self.P.append(dict(top=H[i - 2], bot=L[i - 2], d=-1 if r1 else 1, t0=T[i - 2], ref=ref))
                if len(self.P) > 10:
                    self.P.pop(0)
        keepP = []
        for p in self.P:
            kill = c > p['top'] if p['d'] == -1 else c < p['bot']
            okB = c < p['ref'] if p['d'] == -1 else c > p['ref']
            if kill or okB:
                if okB and not kill:
                    self.Q.append(dict(top=p['top'], bot=p['bot'], d=p['d'], t0=p['t0'], test=0))
                continue
            keepP.append(p)
        self.P = keepP
        self.Q = _keep(self.Q, self.kykN)

        # ── iç yapı OB
        self.IQ = [z for z in self.IQ if not ((z['d'] == -1 and c > z['top']) or (z['d'] == 1 and c < z['bot']))]
        for z in self.IQ:
            tst(z)
        keepP = []
        for p in self.IP:
            gone = h > p['top'] if p['d'] == -1 else l < p['bot']
            ok = c < p['ref'] if p['d'] == -1 else c > p['ref']
            if gone or ok:
                if ok and not gone:
                    self.IQ.append(dict(top=p['top'], bot=p['bot'], d=p['d'], t0=p['t0'], test=0))
                continue
            keepP.append(p)
        self.IP = keepP
        gC, rC = C[i] > O[i], C[i] < O[i]
        if (gC or rC) and i >= self.iobRef:
            rf = min(L[i - self.iobRef:i]) if gC else max(H[i - self.iobRef:i])
            self.IP.append(dict(top=h, bot=l, d=-1 if gC else 1, t0=T[i], ref=rf))
            if len(self.IP) > 40:
                self.IP.pop(0)
        self.IQ = _keep(self.IQ, self.iobN)

        # ── mevcut OB: kırılım (breaker / sil) + test
        keepR = []
        for z in self.R:
            d = z['d']
            if (d == 1 and c < z['bot']) or (d == -1 and c > z['top']):
                if self.brkOn and not z['brk']:
                    z.update(brk=True, d=-d, test=0)
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
            self.R.append(dict(top=top, bot=bot, d=dd, kind=r['kind'], liq=r['liq'], A=imb and okH, sw=isSw,
                               cln=cln, kyk=kyk, brk=False, test=0, t0=T[jl]))
        self.R = _keep(self.R, self.keepN)

    def zones(self, tf):
        out = []
        for z in self.R:
            d = z['d']
            if z['brk']:
                nm = f"{tf} M5 Breaker{'+' if d == 1 else '-'}"
            else:
                nm = f"{tf} M5 OB{'+' if d == 1 else '-'} {'A' if z['A'] else 'B'}"
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
            if z['test']:
                tag += f" test {z['test']}"
            out.append(dict(key=f"M5|{tf}|{z['t0']}|{d}|{1 if z['brk'] else 0}", top=z['top'], bot=z['bot'], d=d,
                            ad=nm, tag=tag, anySide=True))
        for z in self.Q:
            out.append(dict(key=f"M5K|{tf}|{z['t0']}|{z['d']}", top=z['top'], bot=z['bot'], d=z['d'],
                            ad=f"{tf} M5 {'YKY' if z['d'] == 1 else 'KYK'} kutusu", tag="", anySide=False))
        for z in self.IQ:
            out.append(dict(key=f"M5I|{tf}|{z['t0']}|{z['d']}", top=z['top'], bot=z['bot'], d=z['d'],
                            ad=f"{tf} M5 iç OB{'+' if z['d'] == 1 else '-'}", tag="", anySide=False))
        return out


# ════════════════════════════════════════════════════════════════
# M6 — EQH / EQL (sinyal = likidite alındı / sweep)
# ════════════════════════════════════════════════════════════════
class M6:
    ad = "M6"

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
    ad = "M8"

    def __init__(self, B, iobRef=5, iobExp=30, iobN=3, liqOn=True, liqW=5, liqS=5, fvgOn=True,
                 wideOn=False, wideN=10, llOn=False, llS=3):
        self.B = B
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
            if (z['d'] == -1 and c > z['top']) or (z['d'] == 1 and c < z['bot']):
                continue
            if l <= z['top'] and h >= z['bot'] and not (L[i - 1] <= z['top'] and H[i - 1] >= z['bot']):
                z['test'] += 1
            keep.append(z)
        self.Q = keep
        # bekleyenler
        keepP = []
        for p in self.P:
            pd = p['d']
            br = p['br'] or (c < p['ref'] if pd == -1 else c > p['ref'])
            fv = p['fv'] or (i - 2 >= p['bi'] and (h < L[i - 2] if pd == -1 else l > H[i - 2]))
            gone = (h > p['top'] if pd == -1 else l < p['bot']) or i - p['bi'] > self.iobExp
            ok = br and (fv or not self.fvgOn)
            if gone or ok:
                if ok and not gone:
                    self.Q.append(dict(top=p['top'], bot=p['bot'], d=pd, t0=p['t0'], test=0,
                                       lv=self.swHv if pd == -1 else self.swLv))
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
                self.P.append(dict(top=h, bot=l, d=dr, t0=T[i], ref=rf, bi=i, br=False, fv=False))
                if len(self.P) > 200:
                    self.P.pop(0)
        self.Q = _keep(self.Q, self.iobN)

    def zones(self, tf):
        tg = (" lik." if self.liqOn else "") + (" FVG" if self.fvgOn else "") + (" geniş" if self.wideOn else "")
        out = []
        for z in self.Q:
            t = tg + ((" HH" if z['d'] == 1 else " LL") if self.llOn else "")
            if z['test']:
                t += f" test {z['test']}"
            out.append(dict(key=f"M8|{tf}|{z['t0']}|{z['d']}", top=z['top'], bot=z['bot'], d=z['d'],
                            ad=f"{tf} M8 OB{'+' if z['d'] == 1 else '-'}", tag=t, anySide=False))
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
