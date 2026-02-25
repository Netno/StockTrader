"""
Stock scanner: discovery + rotation.

Discovery mode (positions < MAX_POSITIONS):
  Scans the full universe every morning to find the best trading candidates.
  Replaces the watchlist with top ~15 stocks so the trading loop has a broad
  pool to generate buy signals from.

Rotation mode (positions >= MAX_POSITIONS):
  After market close, scans for stronger candidates and rotates out the
  weakest watchlist stock if the improvement is significant.
"""
import logging
from datetime import datetime, timezone
from data.yahoo_client import get_price_history, get_index_history
from analysis.indicators import calculate_indicators, calculate_relative_strength, calculate_market_regime
from analysis.decision_engine import score_buy_signal
from db.supabase_client import get_client, get_watchlist, bulk_update_watchlist
from notifications import ntfy

logger = logging.getLogger(__name__)

# Broad universe of Swedish stocks to evaluate
# Covers all Nasdaq Stockholm Large Cap + Mid Cap (~150 aktier).
# The liquidity filter (MIN_DAILY_TURNOVER_SEK) automatically removes
# any stock that doesn't meet the turnover threshold.
STOCK_UNIVERSE = {
    # ── Large Cap ──────────────────────────────────────────────
    "AAK":      "AAK",
    "ABB":      "ABB",
    "AFRY":     "AFRY",
    "ALFA":     "Alfa Laval",
    "ALIV SDB": "Autoliv SDB",
    "ASSA B":   "Assa Abloy B",
    "ATCO A":   "Atlas Copco A",
    "ATCO B":   "Atlas Copco B",
    "AZN":      "AstraZeneca",
    "AXFO":     "Axfood",
    "BALD B":   "Balder B",
    "BILL":     "Billerud",
    "BOL":      "Boliden",
    "CAST":     "Castellum",
    "DOME":     "Dometic",
    "EKTA B":   "Elekta B",
    "ELUX B":   "Electrolux B",
    "EMBRAC B": "Embracer Group B",
    "EPRO A":   "Epiroc A",
    "EPRO B":   "Epiroc B",
    "EQT":      "EQT",
    "ERIC B":   "Ericsson B",
    "ESSITY B": "Essity B",
    "EVO":      "Evolution",
    "GETI B":   "Getinge B",
    "HEXA B":   "Hexagon B",
    "HM B":     "H&M B",
    "HOLMEN B": "Holmen B",
    "HPOL B":   "Hexpol B",
    "HUSQ B":   "Husqvarna B",
    "INDU C":   "Industrivärden C",
    "INDT":     "Indutrade",
    "INVE B":   "Investor B",
    "INTRUM":   "Intrum",
    "KINV B":   "Kinnevik B",
    "LAGR B":   "Lagercrantz Group B",
    "LATO B":   "Latour B",
    "LIFCO B":  "Lifco B",
    "LOOMIS":   "Loomis",
    "LUND B":   "Lundbergföretagen B",
    "MTRS":     "Munters Group",
    "NDA SE":   "Nordea",
    "NIBE B":   "NIBE B",
    "SAAB B":   "Saab B",
    "SAND":     "Sandvik",
    "SBB B":    "Samhällsbyggnadsbolaget B",
    "SCA B":    "SCA B",
    "SEB A":    "SEB A",
    "SECU B":   "Securitas B",
    "SECT B":   "Sectra B",
    "SHB A":    "Handelsbanken A",
    "SINCH":    "Sinch",
    "SKF B":    "SKF B",
    "SOBI":     "Swedish Orphan Biovitrum",
    "SSAB A":   "SSAB A",
    "SSAB B":   "SSAB B",
    "STE R":    "Stora Enso R",
    "SWEC B":   "Sweco B",
    "SWED A":   "Swedbank A",
    "TELE2 B":  "Tele2 B",
    "TELIA":    "Telia",
    "TIGO SDB": "Millicom SDB",
    "TREL B":   "Trelleborg B",
    "VOLCAR B": "Volvo Cars B",
    "VOLV A":   "Volvo A",
    "VOLV B":   "Volvo B",
    # ── Mid Cap ────────────────────────────────────────────────
    "ACAD":     "Academedia",
    "ADDT B":   "AddTech B",
    "AMBEA":    "Ambea",
    "ARJO B":   "Arjo B",
    "ATRLJ B":  "Atrium Ljungberg B",
    "BETS B":   "Betsson B",
    "BIOG B":   "BioGaia B",
    "BONAV B":  "Bonava B",
    "BOOZT":    "Boozt",
    "BRAV":     "Bravida Holding",
    "BUFAB":    "Bufab",
    "BURE":     "Bure Equity",
    "CAMX":     "Camurus",
    "CATE":     "Catena",
    "CIBUS":    "Cibus Nordic Real Estate",
    "CINT":     "Cint Group",
    "CLAS B":   "Clas Ohlson B",
    "COOR":     "Coor Service Management",
    "CTM":      "CellaVision",
    "DIOS":     "Dios Fastigheter",
    "ELAN B":   "Elanders B",
    "FABG":     "Fabege",
    "GREP":     "Gränges",
    "HEBA B":   "HEBA Fastigheter B",
    "HMS":      "HMS Networks",
    "HTRO":     "Hexatronic",
    "HUFV A":   "Hufvudstaden A",
    "JM":       "JM",
    "KABE B":   "KABE B",
    "KNOW":     "Knowit",
    "LIME":     "Lime Technologies",
    "MEKO":     "Meko",
    "MEDIO B":  "Medicover B",
    "MYCR":     "Mycronic",
    "NCAB":     "NCAB Group",
    "NEWA B":   "New Wave Group B",
    "NOLA B":   "Nolato B",
    "NOTE":     "NOTE",
    "NP3":      "NP3 Fastigheter",
    "NYFOSA":   "Nyfosa",
    "OEM B":    "OEM International B",
    "PEAB B":   "Peab B",
    "PLAZ B":   "Platzer Fastigheter B",
    "PNDX B":   "Pandox B",
    "RATO B":   "Ratos B",
    "RESURS":   "Resurs Holding",
    "RVRC":     "Revolution Race",
    "SAGAX B":  "Sagax B",
    "SAVE":     "Nordnet",
    "SDIP B":   "Sdiptech B",
    "SYSR":     "Synsam Group",
    "THULE":    "Thule Group",
    "TOBS B":   "Tobii B",
    "TROAX":    "Troax Group",
    "VBG B":    "VBG Group B",
    "WALL B":   "Wallenstam B",
    "WIHL":     "Wihlborgs Fastigheter",
    "XVIVO":    "XVIVO Perfusion",
}

AVANZA_URLS = {
    # ── Large Cap ──────────────────────────────────────────────
    "AAK":      "https://www.avanza.se/aktier/om-aktien.html/26268/aak",
    "ABB":      "https://www.avanza.se/aktier/om-aktien.html/5447/abb",
    "AFRY":     "https://www.avanza.se/aktier/om-aktien.html/5765/afry",
    "ALFA":     "https://www.avanza.se/aktier/om-aktien.html/5580/alfa-laval",
    "ALIV SDB": "https://www.avanza.se/aktier/om-aktien.html/5236/autoliv-sdb",
    "ASSA B":   "https://www.avanza.se/aktier/om-aktien.html/5271/assa-abloy-b",
    "ATCO A":   "https://www.avanza.se/aktier/om-aktien.html/5234/atlas-copco-a",
    "ATCO B":   "https://www.avanza.se/aktier/om-aktien.html/5235/atlas-copco-b",
    "AZN":      "https://www.avanza.se/aktier/om-aktien.html/5361/astrazeneca",
    "AXFO":     "https://www.avanza.se/aktier/om-aktien.html/5465/axfood",
    "BALD B":   "https://www.avanza.se/aktier/om-aktien.html/5519/balder-b",
    "BILL":     "https://www.avanza.se/aktier/om-aktien.html/5253/billerud",
    "BOL":      "https://www.avanza.se/aktier/om-aktien.html/5564/boliden",
    "CAST":     "https://www.avanza.se/aktier/om-aktien.html/5353/castellum",
    "DOME":     "https://www.avanza.se/aktier/om-aktien.html/549782/dometic-group",
    "EKTA B":   "https://www.avanza.se/aktier/om-aktien.html/5280/elekta-b",
    "ELUX B":   "https://www.avanza.se/aktier/om-aktien.html/5238/electrolux-b",
    "EMBRAC B": "https://www.avanza.se/aktier/om-aktien.html/707695/embracer-group-b",
    "EPRO A":   "https://www.avanza.se/aktier/om-aktien.html/831540/epiroc-a",
    "EPRO B":   "https://www.avanza.se/aktier/om-aktien.html/831541/epiroc-b",
    "EQT":      "https://www.avanza.se/aktier/om-aktien.html/956272/eqt",
    "ERIC B":   "https://www.avanza.se/aktier/om-aktien.html/5240/ericsson-b",
    "ESSITY B": "https://www.avanza.se/aktier/om-aktien.html/764241/essity-b",
    "EVO":      "https://www.avanza.se/aktier/om-aktien.html/549768/evolution",
    "GETI B":   "https://www.avanza.se/aktier/om-aktien.html/5282/getinge-b",
    "HEXA B":   "https://www.avanza.se/aktier/om-aktien.html/5286/hexagon-b",
    "HM B":     "https://www.avanza.se/aktier/om-aktien.html/5364/h-m-b",
    "HOLMEN B": "https://www.avanza.se/aktier/om-aktien.html/5244/holmen-b",
    "HPOL B":   "https://www.avanza.se/aktier/om-aktien.html/39498/hexpol-b",
    "HUSQ B":   "https://www.avanza.se/aktier/om-aktien.html/45189/husqvarna-b",
    "INDU C":   "https://www.avanza.se/aktier/om-aktien.html/5245/industrivarden-c",
    "INDT":     "https://www.avanza.se/aktier/om-aktien.html/26607/indutrade",
    "INTRUM":   "https://www.avanza.se/aktier/om-aktien.html/5223/intrum",
    "INVE B":   "https://www.avanza.se/aktier/om-aktien.html/5247/investor-b",
    "KINV B":   "https://www.avanza.se/aktier/om-aktien.html/5369/kinnevik-b",
    "LAGR B":   "https://www.avanza.se/aktier/om-aktien.html/5514/lagercrantz-group-b",
    "LATO B":   "https://www.avanza.se/aktier/om-aktien.html/5321/latour-b",
    "LIFCO B":  "https://www.avanza.se/aktier/om-aktien.html/520898/lifco-b",
    "LOOMIS":   "https://www.avanza.se/aktier/om-aktien.html/154930/loomis",
    "LUND B":   "https://www.avanza.se/aktier/om-aktien.html/5375/lundbergforetagen-b",
    "MTRS":     "https://www.avanza.se/aktier/om-aktien.html/753399/munters-group",
    "NDA SE":   "https://www.avanza.se/aktier/om-aktien.html/5249/nordea-bank",
    "NIBE B":   "https://www.avanza.se/aktier/om-aktien.html/5325/nibe-industrier-b",
    "SAAB B":   "https://www.avanza.se/aktier/om-aktien.html/5260/saab-b",
    "SAND":     "https://www.avanza.se/aktier/om-aktien.html/5471/sandvik",
    "SBB B":    "https://www.avanza.se/aktier/om-aktien.html/808046/sbb-b",
    "SCA B":    "https://www.avanza.se/aktier/om-aktien.html/5263/sca-b",
    "SEB A":    "https://www.avanza.se/aktier/om-aktien.html/5255/seb-a",
    "SECU B":   "https://www.avanza.se/aktier/om-aktien.html/5270/securitas-b",
    "SECT B":   "https://www.avanza.se/aktier/om-aktien.html/16226/sectra-b",
    "SHB A":    "https://www.avanza.se/aktier/om-aktien.html/5264/handelsbanken-a",
    "SINCH":    "https://www.avanza.se/aktier/om-aktien.html/599956/sinch",
    "SKF B":    "https://www.avanza.se/aktier/om-aktien.html/5259/skf-b",
    "SOBI":     "https://www.avanza.se/aktier/om-aktien.html/5576/swedish-orphan-biovitrum",
    "SSAB A":   "https://www.avanza.se/aktier/om-aktien.html/5261/ssab-a",
    "SSAB B":   "https://www.avanza.se/aktier/om-aktien.html/495284/ssab-b",
    "STE R":    "https://www.avanza.se/aktier/om-aktien.html/5256/stora-enso-r",
    "SWEC B":   "https://www.avanza.se/aktier/om-aktien.html/5409/sweco-b",
    "SWED A":   "https://www.avanza.se/aktier/om-aktien.html/5241/swedbank-a",
    "TELE2 B":  "https://www.avanza.se/aktier/om-aktien.html/5386/tele2-b",
    "TELIA":    "https://www.avanza.se/aktier/om-aktien.html/5479/telia-company",
    "TIGO SDB": "https://www.avanza.se/aktier/om-aktien.html/5384/millicom-sdb",
    "TREL B":   "https://www.avanza.se/aktier/om-aktien.html/5267/trelleborg-b",
    "VOLCAR B": "https://www.avanza.se/aktier/om-aktien.html/1041480/volvo-cars-b",
    "VOLV A":   "https://www.avanza.se/aktier/om-aktien.html/5268/volvo-a",
    "VOLV B":   "https://www.avanza.se/aktier/om-aktien.html/5269/volvo-b",
    # ── Mid Cap ────────────────────────────────────────────────
    "ACAD":     "https://www.avanza.se/aktier/om-aktien.html/560907/academedia",
    "ADDT B":   "https://www.avanza.se/aktier/om-aktien.html/5537/addtech-b",
    "AMBEA":    "https://www.avanza.se/aktier/om-aktien.html/753387/ambea",
    "ARJO B":   "https://www.avanza.se/aktier/om-aktien.html/831548/arjo-b",
    "ATRLJ B":  "https://www.avanza.se/aktier/om-aktien.html/5272/atrium-ljungberg-b",
    "BETS B":   "https://www.avanza.se/aktier/om-aktien.html/5482/betsson-b",
    "BIOG B":   "https://www.avanza.se/aktier/om-aktien.html/5507/biogaia-b",
    "BONAV B":  "https://www.avanza.se/aktier/om-aktien.html/764238/bonava-b",
    "BOOZT":    "https://www.avanza.se/aktier/om-aktien.html/780423/boozt",
    "BRAV":     "https://www.avanza.se/aktier/om-aktien.html/753395/bravida-holding",
    "BUFAB":    "https://www.avanza.se/aktier/om-aktien.html/518131/bufab",
    "BURE":     "https://www.avanza.se/aktier/om-aktien.html/5277/bure-equity",
    "CAMX":     "https://www.avanza.se/aktier/om-aktien.html/521499/camurus",
    "CATE":     "https://www.avanza.se/aktier/om-aktien.html/5484/catena",
    "CIBUS":    "https://www.avanza.se/aktier/om-aktien.html/867390/cibus-nordic",
    "CINT":     "https://www.avanza.se/aktier/om-aktien.html/1061965/cint-group",
    "CLAS B":   "https://www.avanza.se/aktier/om-aktien.html/5276/clas-ohlson-b",
    "COOR":     "https://www.avanza.se/aktier/om-aktien.html/523418/coor-service-management",
    "CTM":      "https://www.avanza.se/aktier/om-aktien.html/5490/cellavision",
    "DIOS":     "https://www.avanza.se/aktier/om-aktien.html/45191/dios-fastigheter",
    "ELAN B":   "https://www.avanza.se/aktier/om-aktien.html/5485/elanders-b",
    "FABG":     "https://www.avanza.se/aktier/om-aktien.html/5300/fabege",
    "GREP":     "https://www.avanza.se/aktier/om-aktien.html/523418/granges",
    "HEBA B":   "https://www.avanza.se/aktier/om-aktien.html/5506/heba-b",
    "HMS":      "https://www.avanza.se/aktier/om-aktien.html/98412/hms-networks",
    "HTRO":     "https://www.avanza.se/aktier/om-aktien.html/299737/hexatronic-group",
    "HUFV A":   "https://www.avanza.se/aktier/om-aktien.html/5287/hufvudstaden-a",
    "JM":       "https://www.avanza.se/aktier/om-aktien.html/5501/jm",
    "KABE B":   "https://www.avanza.se/aktier/om-aktien.html/5308/kabe-b",
    "KNOW":     "https://www.avanza.se/aktier/om-aktien.html/5515/knowit",
    "LIME":     "https://www.avanza.se/aktier/om-aktien.html/867393/lime-technologies",
    "MEKO":     "https://www.avanza.se/aktier/om-aktien.html/5324/meko",
    "MEDIO B":  "https://www.avanza.se/aktier/om-aktien.html/788849/medicover-b",
    "MYCR":     "https://www.avanza.se/aktier/om-aktien.html/5383/mycronic",
    "NCAB":     "https://www.avanza.se/aktier/om-aktien.html/856458/ncab-group",
    "NEWA B":   "https://www.avanza.se/aktier/om-aktien.html/5326/new-wave-group-b",
    "NOLA B":   "https://www.avanza.se/aktier/om-aktien.html/5327/nolato-b",
    "NOTE":     "https://www.avanza.se/aktier/om-aktien.html/5328/note",
    "NP3":      "https://www.avanza.se/aktier/om-aktien.html/519504/np3-fastigheter",
    "NYFOSA":   "https://www.avanza.se/aktier/om-aktien.html/907825/nyfosa",
    "OEM B":    "https://www.avanza.se/aktier/om-aktien.html/5329/oem-international-b",
    "PEAB B":   "https://www.avanza.se/aktier/om-aktien.html/5330/peab-b",
    "PLAZ B":   "https://www.avanza.se/aktier/om-aktien.html/519508/platzer-fastigheter-b",
    "PNDX B":   "https://www.avanza.se/aktier/om-aktien.html/720476/pandox-b",
    "RATO B":   "https://www.avanza.se/aktier/om-aktien.html/5397/ratos-b",
    "RESURS":   "https://www.avanza.se/aktier/om-aktien.html/569437/resurs-holding",
    "RVRC":     "https://www.avanza.se/aktier/om-aktien.html/1041388/rvrc-holding",
    "SAGAX B":  "https://www.avanza.se/aktier/om-aktien.html/405815/sagax-b",
    "SAVE":     "https://www.avanza.se/aktier/om-aktien.html/325295/nordnet",
    "SDIP B":   "https://www.avanza.se/aktier/om-aktien.html/784434/sdiptech-b",
    "SYSR":     "https://www.avanza.se/aktier/om-aktien.html/956279/synsam-group",
    "THULE":    "https://www.avanza.se/aktier/om-aktien.html/521491/thule-group",
    "TOBS B":   "https://www.avanza.se/aktier/om-aktien.html/625680/tobii-b",
    "TROAX":    "https://www.avanza.se/aktier/om-aktien.html/549766/troax-group",
    "VBG B":    "https://www.avanza.se/aktier/om-aktien.html/5342/vbg-group-b",
    "WALL B":   "https://www.avanza.se/aktier/om-aktien.html/5344/wallenstam-b",
    "WIHL":     "https://www.avanza.se/aktier/om-aktien.html/5345/wihlborgs-fastigheter",
    "XVIVO":    "https://www.avanza.se/aktier/om-aktien.html/376275/xvivo-perfusion",
}

YAHOO_SYMBOLS = {
    # ── Large Cap ──────────────────────────────────────────────
    "AAK":      "AAK.ST",
    "ABB":      "ABB.ST",
    "AFRY":     "AFRY.ST",
    "ALFA":     "ALFA.ST",
    "ALIV SDB": "ALIV-SDB.ST",
    "ASSA B":   "ASSA-B.ST",
    "ATCO A":   "ATCO-A.ST",
    "ATCO B":   "ATCO-B.ST",
    "AZN":      "AZN.ST",
    "AXFO":     "AXFO.ST",
    "BALD B":   "BALD-B.ST",
    "BILL":     "BILL.ST",
    "BOL":      "BOL.ST",
    "CAST":     "CAST.ST",
    "DOME":     "DOME.ST",
    "EKTA B":   "EKTA-B.ST",
    "ELUX B":   "ELUX-B.ST",
    "EMBRAC B": "EMBRAC-B.ST",
    "EPRO A":   "EPRO-A.ST",
    "EPRO B":   "EPRO-B.ST",
    "EQT":      "EQT.ST",
    "ERIC B":   "ERIC-B.ST",
    "ESSITY B": "ESSITY-B.ST",
    "EVO":      "EVO.ST",
    "GETI B":   "GETI-B.ST",
    "HEXA B":   "HEXA-B.ST",
    "HM B":     "HM-B.ST",
    "HOLMEN B": "HOLM-B.ST",
    "HPOL B":   "HPOL-B.ST",
    "HUSQ B":   "HUSQ-B.ST",
    "INDU C":   "INDU-C.ST",
    "INDT":     "INDT.ST",
    "INTRUM":   "INTRUM.ST",
    "INVE B":   "INVE-B.ST",
    "KINV B":   "KINV-B.ST",
    "LAGR B":   "LAGR-B.ST",
    "LATO B":   "LATO-B.ST",
    "LIFCO B":  "LIFCO-B.ST",
    "LOOMIS":   "LOOMIS.ST",
    "LUND B":   "LUND-B.ST",
    "MTRS":     "MTRS.ST",
    "NDA SE":   "NDA-SE.ST",
    "NIBE B":   "NIBE-B.ST",
    "SAAB B":   "SAAB-B.ST",
    "SAND":     "SAND.ST",
    "SBB B":    "SBB-B.ST",
    "SCA B":    "SCA-B.ST",
    "SEB A":    "SEB-A.ST",
    "SECU B":   "SECU-B.ST",
    "SECT B":   "SECT-B.ST",
    "SHB A":    "SHB-A.ST",
    "SINCH":    "SINCH.ST",
    "SKF B":    "SKF-B.ST",
    "SOBI":     "SOBI.ST",
    "SSAB A":   "SSAB-A.ST",
    "SSAB B":   "SSAB-B.ST",
    "STE R":    "STE-R.ST",
    "SWEC B":   "SWEC-B.ST",
    "SWED A":   "SWED-A.ST",
    "TELE2 B":  "TELE2-B.ST",
    "TELIA":    "TELIA.ST",
    "TIGO SDB": "TIGO-SDB.ST",
    "TREL B":   "TREL-B.ST",
    "VOLCAR B": "VOLCAR-B.ST",
    "VOLV A":   "VOLV-A.ST",
    "VOLV B":   "VOLV-B.ST",
    # ── Mid Cap ────────────────────────────────────────────────
    "ACAD":     "ACAD.ST",
    "ADDT B":   "ADDT-B.ST",
    "AMBEA":    "AMBEA.ST",
    "ARJO B":   "ARJO-B.ST",
    "ATRLJ B":  "ATRLJ-B.ST",
    "BETS B":   "BETS-B.ST",
    "BIOG B":   "BIOG-B.ST",
    "BONAV B":  "BONAV-B.ST",
    "BOOZT":    "BOOZT.ST",
    "BRAV":     "BRAV.ST",
    "BUFAB":    "BUFAB.ST",
    "BURE":     "BURE.ST",
    "CAMX":     "CAMX.ST",
    "CATE":     "CATE.ST",
    "CIBUS":    "CIBUS.ST",
    "CINT":     "CINT.ST",
    "CLAS B":   "CLAS-B.ST",
    "COOR":     "COOR.ST",
    "CTM":      "CTM.ST",
    "DIOS":     "DIOS.ST",
    "ELAN B":   "ELAN-B.ST",
    "FABG":     "FABG.ST",
    "GREP":     "GREP.ST",
    "HEBA B":   "HEBA-B.ST",
    "HMS":      "HMS.ST",
    "HTRO":     "HTRO.ST",
    "HUFV A":   "HUFV-A.ST",
    "JM":       "JM.ST",
    "KABE B":   "KABE-B.ST",
    "KNOW":     "KNOW.ST",
    "LIME":     "LIME.ST",
    "MEKO":     "MEKO.ST",
    "MEDIO B":  "MEDIO-B.ST",
    "MYCR":     "MYCR.ST",
    "NCAB":     "NCAB.ST",
    "NEWA B":   "NEWA-B.ST",
    "NOLA B":   "NOLA-B.ST",
    "NOTE":     "NOTE.ST",
    "NP3":      "NP3.ST",
    "NYFOSA":   "NYFOSA.ST",
    "OEM B":    "OEM-B.ST",
    "PEAB B":   "PEAB-B.ST",
    "PLAZ B":   "PLAZ-B.ST",
    "PNDX B":   "PNDX-B.ST",
    "RATO B":   "RATO-B.ST",
    "RESURS":   "RESURS.ST",
    "RVRC":     "RVRC.ST",
    "SAGAX B":  "SAGAX-B.ST",
    "SAVE":     "SAVE.ST",
    "SDIP B":   "SDIP-B.ST",
    "SYSR":     "SYSR.ST",
    "THULE":    "THULE.ST",
    "TOBS B":   "TOBS-B.ST",
    "TROAX":    "TROAX.ST",
    "VBG B":    "VBG-B.ST",
    "WALL B":   "WALL-B.ST",
    "WIHL":     "WIHL.ST",
    "XVIVO":    "XVIVO.ST",
}


MIN_DAILY_TURNOVER_SEK = 30_000_000   # 30M SEK/dag — filtrerar bort illikvida mikrokap
MIN_HISTORY_DAYS      = 50            # Minst 50 handelsdagar för tillförlitlig bedömning


def score_candidate(ticker: str, indicators: dict, df) -> tuple[float, list[str]]:
    """
    Score a stock as a trading candidate (0–100+).
    Returns score=0 and a disqualification reason if liquidity/history filters fail.
    Higher score = bättre handelskandidat.
    """
    score = 0.0
    reasons = []

    price = indicators.get("current_price", 0)
    atr = indicators.get("atr", 0)

    # LIKVIDITETSFILTER: minst 30M SEK/dag i genomsnittlig omsättning.
    # Filtrerar bort mikrokap och First North-bolag med låg handel.
    if not df.empty and "close" in df.columns and "volume" in df.columns:
        avg_turnover = (df["close"] * df["volume"]).mean()
        if avg_turnover < MIN_DAILY_TURNOVER_SEK:
            return 0.0, [f"Filtrerad: omsättning {avg_turnover / 1e6:.1f}M SEK/dag (min {MIN_DAILY_TURNOVER_SEK // 1_000_000}M)"]
        elif avg_turnover >= 200_000_000:
            score += 20
            reasons.append(f"Mycket hög likviditet: {avg_turnover / 1e6:.0f}M SEK/dag")
        elif avg_turnover >= 80_000_000:
            score += 10
            reasons.append(f"God likviditet: {avg_turnover / 1e6:.0f}M SEK/dag")

    # HISTORIKFILTER: minst 50 handelsdagar för tillförlitliga indikatorer
    if len(df) < MIN_HISTORY_DAYS:
        return 0.0, [f"Filtrerad: bara {len(df)} handelsdagar (min {MIN_HISTORY_DAYS})"]

    # 1. Daglig volatilitet (ATR / pris) — vi vill ha 2–8% för bra handelsmöjligheter
    if price and atr:
        daily_vol_pct = (atr / price) * 100
        if 2 <= daily_vol_pct <= 8:
            score += 25
            reasons.append(f"Bra volatilitet: {daily_vol_pct:.1f}%/dag")
        elif daily_vol_pct > 8:
            score += 10
            reasons.append(f"Hög volatilitet: {daily_vol_pct:.1f}%/dag")
        else:
            reasons.append(f"Låg volatilitet: {daily_vol_pct:.1f}%/dag")

    # 2. Volymratio — vi vill ha >1.0 (aktivt handlad)
    vol_ratio = indicators.get("volume_ratio", 0)
    if vol_ratio >= 1.5:
        score += 20
        reasons.append(f"Hög volym: {vol_ratio:.1f}× snitt")
    elif vol_ratio >= 1.0:
        score += 10
        reasons.append(f"Normal volym: {vol_ratio:.1f}× snitt")

    # 3. Trендkvalitet — pris vs MA50/MA200
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    if price and ma50 and price > ma50:
        score += 20
        reasons.append("Pris över MA50 (upptrend)")
    if price and ma200 and price > ma200:
        score += 15
        reasons.append("Pris över MA200 (långsiktig upptrend)")

    # 4. RSI i handelsbart läge (30–70)
    rsi = indicators.get("rsi")
    if rsi and 30 <= rsi <= 70:
        score += 10
        reasons.append(f"RSI: {rsi:.0f} (handelsbart läge)")

    return round(score, 1), reasons


def _derive_stock_config(indicators: dict, df) -> dict:
    """
    Derive per-stock trading config (strategy, SL%, TP%, ATR-multiplier)
    from the stock's own volatility profile.
    """
    price = indicators.get("current_price", 1)
    atr = indicators.get("atr") or 0
    rsi = indicators.get("rsi") or 50
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    atr_pct = atr / price if price else 0.02

    # Strategy determination
    if rsi < 40 and ma50 and price < ma50:
        strategy = "mean_reversion"
    elif ma50 and ma200 and price > ma50 and price > ma200:
        strategy = "trend_following"
    else:
        strategy = "trend_following"

    # ATR-baserade SL/TP — begränsade till rimliga intervall
    stop_loss_pct  = round(min(0.09, max(0.03, atr_pct * 1.5)), 3)
    take_profit_pct = round(min(0.18, max(0.06, atr_pct * 3.0)), 3)

    return {
        "strategy":        strategy,
        "stop_loss_pct":   stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "atr_multiplier":  1.3,
    }


ROTATION_MARGIN = 25   # Ny kandidat måste vara minst 25p bättre än den svagaste
DISCOVERY_WATCHLIST_SIZE = 15  # Antal aktier i watchlist under discovery-fas


async def discovery_scan():
    """
    Morning discovery: scan full universe and fill watchlist with top candidates.

    Called at 08:55 when open positions < MAX_POSITIONS.
    Ranks all stocks by combined candidate score + technical buy pre-score,
    then sets the top DISCOVERY_WATCHLIST_SIZE as the active watchlist.
    Stocks with open positions are always kept.
    """
    logger.info("=== DISCOVERY SCAN START ===")
    logger.info(f"Skannar {len(STOCK_UNIVERSE)} aktier för att hitta bästa handels­kandidaterna...")

    # Get current open positions (must keep these)
    db_client = get_client()
    open_trades = db_client.table("stock_trades").select("ticker").eq("status", "open").execute()
    positioned_tickers = {t["ticker"] for t in (open_trades.data or [])}
    logger.info(f"Skyddade positioner: {positioned_tickers or '{inga}'}")

    # Current watchlist — gives stability bonus to existing entries
    watchlist = await get_watchlist()
    current_watchlist_tickers = {s["ticker"] for s in watchlist}

    # Fetch OMXS30 for relative strength
    try:
        index_df = await get_index_history()
    except Exception as e:
        logger.warning(f"Kunde inte hämta OMXS30-data: {e}")
        index_df = None

    market_regime = calculate_market_regime(index_df)
    logger.info(f"Marknadsregim: {market_regime}")

    results = []
    scanned = 0
    errors = 0

    for ticker, name in STOCK_UNIVERSE.items():
        yahoo_symbol = YAHOO_SYMBOLS.get(ticker)
        if not yahoo_symbol:
            continue
        try:
            df = await get_price_history(ticker, days=220)
            if df.empty or len(df) < MIN_HISTORY_DAYS:
                continue

            indicators = calculate_indicators(df)
            if not indicators:
                continue

            # 1. Candidate score (liquidity, volatility, trend)
            cand_score, cand_reasons = score_candidate(ticker, indicators, df)
            if cand_score == 0:
                logger.debug(f"  {ticker}: filtrerad — {cand_reasons[0] if cand_reasons else '?'}")
                continue

            # 2. Technical buy pre-score (without sentiment — quick & free)
            rs = calculate_relative_strength(df, index_df) if index_df is not None else None
            buy_pre_score, buy_reasons = score_buy_signal(
                ticker, indicators,
                news_sentiment=None, insider_trades=None,
                has_open_report_soon=False,
                relative_strength=rs,
                market_regime=market_regime,
            )

            # Combined score: 40% candidate quality + 60% buy readiness
            # This prioritizes stocks that are both good candidates AND close to a buy signal
            combined_score = cand_score * 0.4 + buy_pre_score * 0.6

            # Stability bonus: stocks already on the watchlist get a small boost
            # to prevent unnecessary churn
            if ticker in current_watchlist_tickers:
                combined_score += 5
                cand_reasons.append("Stabilitet: redan på watchlist (+5p)")

            results.append({
                "ticker": ticker,
                "name": name,
                "candidate_score": cand_score,
                "buy_pre_score": buy_pre_score,
                "combined_score": round(combined_score, 1),
                "reasons": cand_reasons,
                "buy_reasons": buy_reasons,
                "indicators": indicators,
                "df": df,
                "is_positioned": ticker in positioned_tickers,
            })
            scanned += 1

            if buy_pre_score >= 30:
                logger.info(f"  {ticker}: kandidat={cand_score:.0f}p  köp_pre={buy_pre_score:.0f}p  kombi={combined_score:.0f}p ★")
            else:
                logger.debug(f"  {ticker}: kandidat={cand_score:.0f}p  köp_pre={buy_pre_score:.0f}p  kombi={combined_score:.0f}p")

        except Exception as e:
            errors += 1
            logger.warning(f"  {ticker}: fel — {e}")

    if not results:
        logger.warning("Discovery scan returnerade inga resultat.")
        return

    # Sort by combined score
    results.sort(key=lambda x: x["combined_score"], reverse=True)

    # Select top candidates: positioned stocks always included + best N non-positioned
    positioned_results = [r for r in results if r["is_positioned"]]
    non_positioned = [r for r in results if not r["is_positioned"]]
    slots_available = DISCOVERY_WATCHLIST_SIZE - len(positioned_results)
    top_candidates = non_positioned[:max(0, slots_available)]

    final_selection = positioned_results + top_candidates

    # Build new watchlist entries
    new_entries = []
    for r in final_selection:
        if r["ticker"] in positioned_tickers:
            continue  # positioned stocks are already in watchlist — don't re-add
        cfg = _derive_stock_config(r["indicators"], r["df"])
        new_entries.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "strategy": cfg["strategy"],
            "stop_loss_pct": cfg["stop_loss_pct"],
            "take_profit_pct": cfg["take_profit_pct"],
            "atr_multiplier": cfg["atr_multiplier"],
            "avanza_url": AVANZA_URLS.get(r["ticker"]),
        })

    # Update watchlist in DB
    await bulk_update_watchlist(positioned_tickers, new_entries)

    # Summary notification
    top5 = final_selection[:5]
    top5_lines = []
    for r in top5:
        star = "⭐" if r["buy_pre_score"] >= 40 else "▪"
        top5_lines.append(
            f"  {star} {r['ticker']} — kombi {r['combined_score']:.0f}p (köp {r['buy_pre_score']:.0f}p)"
        )
    top5_str = "\n".join(top5_lines)

    msg = (
        f"Discovery: {scanned} aktier skannade, {len(final_selection)} i watchlist\n"
        f"Marknadsregim: {market_regime}\n\n"
        f"Topp 5 kandidater:\n{top5_str}"
    )
    if errors > 0:
        msg += f"\n\n({errors} aktier kunde inte analyseras)"

    await ntfy._send(
        msg,
        title=f"Discovery — {len(final_selection)} aktier bevakas",
        priority="default",
        tags=["mag", "bar_chart"],
        notif_type="discovery_scan",
    )

    logger.info(
        f"=== DISCOVERY SCAN KLAR === "
        f"{scanned} skannade, {len(final_selection)} i watchlist, {errors} fel"
    )

    # Return structured result for API consumers
    return {
        "scanned": scanned,
        "errors": errors,
        "market_regime": market_regime,
        "watchlist_size": len(final_selection),
        "candidates": [
            {
                "ticker": r["ticker"],
                "name": r["name"],
                "combined_score": r["combined_score"],
                "candidate_score": r["candidate_score"],
                "buy_pre_score": r["buy_pre_score"],
                "reasons": r["reasons"][:3],
                "is_positioned": r["is_positioned"],
            }
            for r in final_selection
        ],
    }


async def run_scan():
    """Main scan function — called daily/weekly by scheduler."""
    logger.info("Startar aktiesskanning...")
    db = get_client()

    # Get current watchlist tickers
    watchlist = await get_watchlist()
    current_tickers = {s["ticker"] for s in watchlist}

    results = []

    for ticker, name in STOCK_UNIVERSE.items():
        yahoo_symbol = YAHOO_SYMBOLS.get(ticker)
        if not yahoo_symbol:
            continue
        try:
            # 220 dagar för att MA200 ska beräknas korrekt
            df = await get_price_history(ticker, days=220)
            if df.empty or len(df) < MIN_HISTORY_DAYS:
                continue
            indicators = calculate_indicators(df)
            if not indicators:
                continue
            score, reasons = score_candidate(ticker, indicators, df)
            results.append({
                "ticker": ticker,
                "name": name,
                "score": score,
                "reasons": reasons,
                "indicators": indicators,
                "df": df,
                "in_watchlist": ticker in current_tickers,
            })
            if score > 0:
                logger.info(f"  {ticker}: {score:.0f}p")
            else:
                logger.debug(f"  {ticker}: filtrerad – {reasons[0] if reasons else '?'}")
        except Exception as e:
            logger.warning(f"  {ticker}: fel – {e}")

    if not results:
        logger.warning("Skanning returnerade inga resultat.")
        return

    # Sort by score — disqualified stocks (score=0) hamnar sist
    results.sort(key=lambda x: x["score"], reverse=True)

    # Top candidates NOT in watchlist (only qualified, score > 0)
    top_new = [r for r in results if not r["in_watchlist"] and r["score"] > 0][:5]

    # Weakest in current watchlist (only those that qualified the liquidity filter)
    current_scored = [r for r in results if r["in_watchlist"] and r["score"] > 0]
    current_scored.sort(key=lambda x: x["score"])
    weakest = current_scored[:2] if current_scored else []

    # Check which tickers have open positions (never rotate out of those)
    open_trades = db.table("stock_trades").select("ticker").eq("status", "open").execute()
    open_tickers = {t["ticker"] for t in (open_trades.data or [])}

    replaced = []
    replaced_tickers = set()

    for candidate in top_new:
        for weak in weakest:
            if weak["ticker"] in replaced_tickers:
                continue
            if weak["ticker"] in open_tickers:
                logger.info(f"Hoppar over {weak['ticker']} — öppen position finns.")
                continue
            # Kräv att ny kandidat är minst ROTATION_MARGIN poäng bättre
            if candidate["score"] > weak["score"] + ROTATION_MARGIN:
                cfg = _derive_stock_config(candidate["indicators"], candidate["df"])

                # Deactivate the weak stock
                db.table("stock_watchlist").update({"active": False}).eq("ticker", weak["ticker"]).execute()

                # Add the better stock with derived config
                db.table("stock_watchlist").insert({
                    "ticker":          candidate["ticker"],
                    "name":            candidate["name"],
                    "strategy":        cfg["strategy"],
                    "stop_loss_pct":   cfg["stop_loss_pct"],
                    "take_profit_pct": cfg["take_profit_pct"],
                    "atr_multiplier":  cfg["atr_multiplier"],
                    "avanza_url":      AVANZA_URLS.get(candidate["ticker"]),
                    "active":          True,
                    "created_at":      datetime.now(timezone.utc).isoformat(),
                }).execute()

                replaced.append((weak, candidate))
                replaced_tickers.add(weak["ticker"])
                logger.info(
                    f"Bytte {weak['ticker']} ({weak['score']:.0f}p) mot "
                    f"{candidate['ticker']} ({candidate['score']:.0f}p) | "
                    f"strategi={cfg['strategy']} SL={cfg['stop_loss_pct']} TP={cfg['take_profit_pct']}"
                )
                break

    # Send ntfy summary
    if replaced:
        sections = []
        for w, c in replaced[:3]:
            top_reasons = c["reasons"][:3]
            reasons_str = "\n".join(f"    ✓ {r}" for r in top_reasons)
            sections.append(
                f"  {w['ticker']} ({w['score']:.0f}p) → {c['ticker']} ({c['score']:.0f}p)\n{reasons_str}"
            )
        lines = "\n".join(sections)
        await ntfy._send(
            f"Watchlist uppdaterad – {len(replaced)} byte(n):\n{lines}",
            title="Watchlist uppdaterad",
            priority="default",
            tags=["bar_chart"],
            notif_type="scan_suggestion",
        )
    else:
        await ntfy._send(
            "Nuvarande watchlist är fortsatt optimal – inga byten gjordes.",
            title="Watchlist-skanning klar",
            priority="min",
            tags=["bar_chart"],
            notif_type="scan_suggestion",
        )

    logger.info(f"Skanning klar. {len(results)} aktier analyserade, {len(replaced)} byten.")
