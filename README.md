# DART 재무정보 조회 툴

기업명 검색으로 DART 공시 재무데이터를 조회하는 웹 앱.

GitHub Pages로 배포: https://qorky01.github.io/dart-financial-tool/

---

## 파일 구성

```
dart-financial-tool/
├── index.html        # 메인 앱 (전체 로직 포함)
├── corpCode.json     # DART 기업코드 목록 (make_corpcode.py로 생성)
├── make_corpcode.py  # corpCode.json 생성 스크립트
└── README.md         # 이 파일
```

---

## 아키텍처

```
브라우저 (GitHub Pages)
    │
    ├─ corpCode.json 로컬 검색 (자동완성)
    │
    └─ fetch → Cloudflare Worker (dart-proxy.qorky01.workers.dev)
                    │
                    ├─ DART OpenAPI (opendart.fss.or.kr)
                    └─ 금융위 공공데이터 (apis.data.go.kr)
```

**검색 우선순위:**
1. DART API로 재무데이터 조회 시도
2. 실패 시 금융위 공공데이터 API로 fallback
3. 둘 다 없으면 DART 감사보고서 바로가기 링크 제공

---

## API 키 목록

### 1. DART OpenAPI
- **발급처**: https://opendart.fss.or.kr
- **인증키**: `43290be06d0cc2ce9323fceee47d4d12274e56b0`
- **무료 한도**: 일 10,000건
- **용도**: 재무제표 조회, 공시 목록 조회, 기업코드 목록 다운로드

### 2. 공공데이터포털 (금융위원회)
- **발급처**: https://www.data.go.kr
- **일반 인증키**: `c46fd3231b0bef66397ffff17b4fc1b78ba0e8a59b6b139e7fc595f5def72eb8`
- **활용기간**: 2026-04-10 ~ 2028-04-10
- **용도**: 비상장법인 포함 기업 재무정보 조회

### 3. Cloudflare Workers (CORS 프록시)
- **Worker URL**: `https://dart-proxy.qorky01.workers.dev/`
- **대시보드**: https://dash.cloudflare.com → Workers & Pages → dart-proxy
- **무료 한도**: 일 100,000 요청
- **역할**: 브라우저 CORS 제한 우회, DART/금융위 API 프록시

---

## 사용 API 엔드포인트

### DART OpenAPI (opendart.fss.or.kr)

| 기능 | 엔드포인트 | 주요 파라미터 |
|------|-----------|--------------|
| 기업코드 전체 다운로드 | `/api/corpCode.xml` | `crtfc_key` |
| 공시 목록 조회 | `/api/list.json` | `corp_code`, `pblntf_detail_ty` |
| 재무제표 조회 (전체) | `/api/fnlttSinglAcntAll.json` | `corp_code`, `bsns_year`, `reprt_code`, `fs_div` |

**reprt_code 값:**
- `11011` : 사업보고서 (연간, 상장법인 주로 사용)
- `11012` : 반기보고서
- `11013` : 1분기보고서
- `11014` : 3분기보고서

**fs_div 값:**
- `CFS` : 연결재무제표 (먼저 시도)
- `OFS` : 개별재무제표 (CFS 없을 때 fallback)

**pblntf_detail_ty 값 (감사보고서 조회 시):**
- `F001` : 감사보고서

**한계:**
- 상장법인 + 사업보고서 제출 의무 법인만 지원
- 비상장 감사보고서만 제출하는 법인은 재무API 조회 불가
- IFRS 적용 법인 위주로 데이터 제공

---

### 금융위원회 공공데이터 (apis.data.go.kr/1160100)

| 기능 | 엔드포인트 | 주요 파라미터 |
|------|-----------|--------------|
| 기업 기본정보 (법인등록번호 조회) | `/service/GetCorpBasicInfoService_V2/getCorpOutline_V2` | `corpNm` |
| 요약재무제표 조회 | `/service/GetFinaStatInfoService_V2/getSummFinaStat_V2` | `crno`, `bizYear` |
| 손익계산서 조회 | `/service/GetFinaStatInfoService_V2/getIncoStat_V2` | `crno`, `bizYear` |

**특징:**
- 법인등록번호(`crno`)로 조회 (기업명 먼저 조회 후 법인등록번호 획득)
- 외감법인 + 비외감법인 약 58만건 커버
- DART에 없는 비상장 소규모 법인도 일부 조회 가능
- 인증키는 URL 인코딩 필요: `encodeURIComponent(key)`

---

## Cloudflare Worker 코드

```javascript
export default {
  async fetch(request) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      const requestUrl = request.url;
      const queryStart = requestUrl.indexOf('?url=');

      if (queryStart === -1) {
        return new Response('url 파라미터가 필요합니다', { status: 400, headers: corsHeaders });
      }

      const target = decodeURIComponent(requestUrl.slice(queryStart + 5));

      if (
        !target.startsWith('https://opendart.fss.or.kr/') &&
        !target.startsWith('https://apis.data.go.kr/1160100/')
      ) {
        return new Response('허용되지 않는 URL입니다', { status: 403, headers: corsHeaders });
      }

      const res = await fetch(target, {
        redirect: 'follow',
        headers: {
          'User-Agent': 'Mozilla/5.0',
          'Accept': 'application/json',
        }
      });

      const body = await res.text();

      return new Response(body, {
        status: 200,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json; charset=utf-8',
        }
      });
    } catch (e) {
      return new Response('Worker error: ' + e.message, { status: 500, headers: corsHeaders });
    }
  }
};
```

---

## corpCode.json 업데이트 방법

DART 기업 목록은 신규 상장/폐지 시 변경되므로 주기적으로 갱신 권장 (연 1회 정도).

```bash
# dart-financial-tool 폴더에서 실행
python make_corpcode.py
```

실행하면 `corpCode.json` 파일이 갱신됨. 이후 GitHub에 다시 업로드.

**corpCode.json 구조:**
```json
[
  { "n": "삼성전자", "c": "00126380", "s": "005930" },
  { "n": "인실리코",  "c": "01048274", "s": "" }
]
```
- `n`: 기업명
- `c`: DART corp_code (8자리)
- `s`: 상장코드 (비상장이면 빈 문자열)

---

## 알려진 한계

| 상황 | 결과 |
|------|------|
| 상장법인 | DART API로 정상 조회 |
| 비상장 외감법인 (자산 120억+) | DART 또는 금융위 API로 조회 |
| 비상장 감사보고서만 제출 (인실리코 등) | 재무수치 API 조회 불가 → DART 링크 제공 |
| 아주 소규모 비상장법인 | 데이터 없음 |

**인실리코 케이스:**
- DART에 감사보고서 존재 (corp_code: `01048274`)
- `fnlttSinglAcntAll` API는 사업보고서 제출 법인만 지원하므로 조회 불가
- 감사보고서 접수번호(`rcept_no`)로 DART 뷰어 직접 링크 제공으로 대응

---

## 배포

- **프론트**: GitHub Pages (`main` 브랜치 자동 배포)
- **프록시**: Cloudflare Workers (수동 배포, 변경 시 대시보드에서 Edit code → Deploy)
- **기업 목록**: `corpCode.json` 파일 GitHub 업로드로 갱신
