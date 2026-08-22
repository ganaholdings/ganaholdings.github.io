# 금리 데이터 파이프라인 (investcal-data)

앱은 `https://ganaholdings.github.io/investcal-data/rates.json`, `config.json`만 GET 한다. 수집은 여기서.

## 1회 설정 (ganaholdings.github.io 저장소)
1. `tools/investcal/fetch_rates.py`, `tools/investcal/config.json` 복사 (이 폴더의 파일)
2. `.github/workflows/update-investcal-data.yml` 복사
3. 저장소 Settings › Secrets › Actions › `FINLIFE_AUTH` = 금감원 인증키
   (신청: https://finlife.fss.or.kr/finlife/api/finlifeApiKey/list.do?menuNo=700034 — 무료, 이메일 인증)
4. Actions 탭에서 `update-investcal-data` › Run workflow 로 첫 실행 → `investcal-data/rates.json` 생성 확인

## 로컬에서 한 번 돌려 번들 스냅샷 만들기
```bash
python3 pipeline/fetch_rates.py --auth <인증키> --out /tmp/investcal-data
cp /tmp/investcal-data/rates.json InvestCal/Data/rates_snapshot.json
```
`rates_snapshot.json`이 `"sample": true`이면 앱 화면에 "⚠︎ 샘플 데이터"가 표시된다.

## 규정 상수 바꾸기
`config.json`의 `stressDSR` 값을 고치고 커밋 → 다음 수집 때 `investcal-data/config.json`으로 배포 → 앱이 하루 1회 받아 적용(앱 업데이트 불필요).
