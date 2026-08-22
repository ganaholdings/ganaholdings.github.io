#!/usr/bin/env python3
"""
금융감독원 "금융상품한눈에" Open API → 앱용 rates.json 생성.

사용:
  FINLIFE_AUTH=<인증키> python3 fetch_rates.py --out ./public/investcal-data
  python3 fetch_rates.py --auth <인증키> --out ./out

출력:
  rates.json   : {schema, generatedAt, sample:false, source, products:{mortgage,jeonse,credit,deposit,saving:[...]}}
  config.json  : 규정 상수(StressDSRConfig) — pipeline/config.json 을 그대로 복사 (사람이 편집)
인증키 신청: https://finlife.fss.or.kr/finlife/api/finlifeApiKey/list.do?menuNo=700034 (무료, 개인키는 일일 호출 제한)
"""
import argparse, datetime, json, os, sys, time, urllib.request, urllib.parse

BASE = "https://finlife.fss.or.kr/finlifeapi/"
SECTORS = {"020000": "은행", "030300": "저축은행", "050000": "보험", "030200": "여신전문"}
ENDPOINTS = {
    "mortgage": "mortgageLoanProductsSearch.json",
    "jeonse": "rentHouseLoanProductsSearch.json",
    "credit": "creditLoanProductsSearch.json",
    "deposit": "depositProductsSearch.json",
    "saving": "savingProductsSearch.json",
}
# 신용대출 신용점수 구간 필드 → 라벨
CREDIT_GRADES = [("crdt_grad_1", "900점 초과"), ("crdt_grad_4", "801~900"), ("crdt_grad_5", "701~800"), ("crdt_grad_6", "601~700"),
                 ("crdt_grad_10", "501~600"), ("crdt_grad_11", "401~500"), ("crdt_grad_12", "301~400"), ("crdt_grad_13", "300 이하")]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "InvestCal-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_all(endpoint, auth, grp):
    page, out_base, out_opts = 1, [], []
    while True:
        q = urllib.parse.urlencode({"auth": auth, "topFinGrpNo": grp, "pageNo": page})
        data = get(BASE + endpoint + "?" + q)
        res = data.get("result", {})
        if res.get("err_cd") != "000":
            raise SystemExit(f"API error {res.get('err_cd')}: {res.get('err_msg')} ({endpoint}, {grp})")
        out_base += res.get("baseList", [])
        out_opts += res.get("optionList", [])
        if page >= int(res.get("max_page_no") or 1):
            break
        page += 1
        time.sleep(0.3)
    return out_base, out_opts

def num(v):
    try:
        return float(v) if v not in (None, "", "null") else None
    except ValueError:
        return None

def build_product(b, sector, opts, cat):
    pid = f"{b['fin_co_no']}-{b['fin_prdt_cd']}"
    p = {
        "id": pid, "company": b.get("kor_co_nm", ""), "sector": sector, "name": b.get("fin_prdt_nm", ""),
        "dclsMonth": b.get("dcls_month", ""), "joinWay": b.get("join_way"),
        "extraCost": b.get("loan_inci_expn"), "earlyFee": b.get("erly_rpay_fee"), "lateRate": b.get("dly_rate"),
        "limit": b.get("loan_lmt") or (("최고 " + format(int(b["max_limit"]), ",") + "원") if b.get("max_limit") else None),
        "homepage": None, "note": " / ".join(x for x in [b.get("spcl_cnd"), b.get("join_deny") and {"1": "제한 없음", "2": "서민전용", "3": "일부 제한"}.get(str(b.get("join_deny"))), b.get("join_member"), b.get("cb_name") and ("신용평가: " + b["cb_name"])] if x) or None,
        "options": [],
    }
    for o in opts:
        if cat == "mortgage":
            p["options"].append({"collateral": o.get("mrtg_type_nm"), "repay": o.get("rpay_type_nm"), "rateType": o.get("lend_rate_type_nm"),
                                 "min": num(o.get("lend_rate_min")), "max": num(o.get("lend_rate_max")), "avg": num(o.get("lend_rate_avg"))})
        elif cat == "jeonse":
            p["options"].append({"repay": o.get("rpay_type_nm"), "rateType": o.get("lend_rate_type_nm"),
                                 "min": num(o.get("lend_rate_min")), "max": num(o.get("lend_rate_max")), "avg": num(o.get("lend_rate_avg"))})
        elif cat == "credit":
            p["options"].append({"rateType": " · ".join(x for x in [b.get("crdt_prdt_type_nm"), o.get("crdt_lend_rate_type_nm")] if x),
                                 "avg": num(o.get("crdt_grad_avg")),
                                 "scores": [{"label": lab, "rate": num(o.get(k))} for k, lab in CREDIT_GRADES]})
        else:
            p["options"].append({"term": int(o.get("save_trm") or 0) or None, "rateType": o.get("intr_rate_type_nm"),
                                 "reserveType": o.get("rsrv_type_nm"), "base": num(o.get("intr_rate")), "top": num(o.get("intr_rate2"))})
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", default=os.environ.get("FINLIFE_AUTH"))
    ap.add_argument("--auth-file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".finlife_auth"),
                    help="인증키가 한 줄로 들어 있는 파일 (기본: pipeline/.finlife_auth, git 제외)")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--sectors", default="020000,030300")
    a = ap.parse_args()
    if not a.auth and os.path.exists(a.auth_file):
        a.auth = open(a.auth_file, encoding="utf-8").read().strip()
    if not a.auth:
        sys.exit("인증키가 없습니다: --auth / FINLIFE_AUTH / pipeline/.finlife_auth 파일")
    os.makedirs(a.out, exist_ok=True)
    products = {}
    for cat, ep in ENDPOINTS.items():
        items = []
        for grp in a.sectors.split(","):
            sector = SECTORS.get(grp, grp)
            base, opts = fetch_all(ep, a.auth, grp)
            by_key = {}
            for o in opts:
                by_key.setdefault((o.get("fin_co_no"), o.get("fin_prdt_cd")), []).append(o)
            for b in base:
                items.append(build_product(b, sector, by_key.get((b.get("fin_co_no"), b.get("fin_prdt_cd")), []), cat))
            print(f"{cat} {sector}: {len(base)}개", file=sys.stderr)
        products[cat] = items
    payload = {
        "schema": 1,
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample": False,
        "source": "금융감독원 금융상품통합비교공시(금융상품한눈에) Open API",
        "products": products,
    }
    with open(os.path.join(a.out, "rates.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_src = os.path.join(here, "config.json")
    if os.path.exists(cfg_src):
        cfg = json.load(open(cfg_src, encoding="utf-8"))
        cfg["generatedAt"] = payload["generatedAt"]
        json.dump(cfg, open(os.path.join(a.out, "config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("done:", a.out, file=sys.stderr)

if __name__ == "__main__":
    main()
