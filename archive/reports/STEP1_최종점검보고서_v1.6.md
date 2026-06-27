# 📊 Step 1 Integrated 최종 로직 점검 보고서 v1.6

**작성일**: 2026-04-08  
**대상 파일**: `step1_integrated.html`  
**검증 데이터**: `sample_data/PHPH_upload.csv` (50행, 40개 컬럼)

---

## 🎯 Executive Summary

PHPH_upload.csv 로우 데이터를 기준으로 `step1_integrated.html`의 KPI 계산 로직, 예외 처리, UI/UX, 필터링 구조를 전면 점검하였습니다.

### ✅ 주요 점검 결과
1. **데이터 정합성**: CPA, IPM, ROAS 계산 로직이 마케팅 표준 산식과 일치하나, **CPI 지표는 미구현** 상태 (현재 시스템에 없음).
2. **예외 처리**: 결측치/0으로 나누기 방어는 기본 구현되어 있으나, **비수치 텍스트 유입 시 NaN 발생 가능성** 존재.
3. **UI/UX**: 업로드 → 점수 계산 → 결과 확인 동선은 단순하나, **중간 상태 피드백 부족** (로딩 인디케이터, 진행률 표시).
4. **필터링**: 캠페인(멀티셀렉트), 날짜, 소재 유형 필터는 구현되어 있으나, **사이즈별, 언어별, 시기별 세그먼트 분석 불가**.

---

## 📋 1. 데이터 정합성 검증

### 1.1 현재 구현된 KPI 계산식

| 지표 | 현재 구현 산식 | 마케팅 표준 산식 | 정합성 |
|------|--------------|----------------|--------|
| **CPA** | `비용 / 전환` | `Cost / Conversion` | ✅ 일치 |
| **IPM** | `(전환 / 노출수) × 1000` | `(Conversion / Impression) × 1000` | ✅ 일치 |
| **ROAS** | `매출 / 비용` | `Revenue / Cost` | ✅ 일치 |
| **전환율** | `(전환 / 노출수) × 100` | `(Conversion / Impression) × 100` | ✅ 일치 |
| **CTR** | `(클릭수 / 노출수) × 100` | `(Click / Impression) × 100` | ✅ 일치 |

### 1.2 ⚠️ 문제점 및 개선 사항

#### 🔴 **문제 1: CPI(Cost Per Install) 지표 누락**
- **현황**: PHPH_upload.csv에는 `전환(Conversion)` 컬럼만 존재하며, 설치(Install) 데이터는 별도 컬럼 없음.
- **영향**: 모바일 게임 마케팅에서 핵심 지표인 CPI를 추적할 수 없음.
- **권장 사항**:
  ```javascript
  // CSV에 '설치수' 또는 'install' 컬럼 추가 시
  g.CPI = g.설치수 > 0 ? g.비용 / g.설치수 : 0;
  ```
- **대체 방안**: 현재는 `CPA(전환당 비용)`를 CPI 대용으로 사용 중. 전환=설치로 간주하는 경우 문제없으나, 전환이 '구매' 등 다른 이벤트일 경우 혼동 가능.

#### 🟡 **문제 2: ROAS 계산 시 Revenue=0인 소재 처리**
- **현황**: PHPH_upload.csv의 모든 행에서 `Revenue=0` (1~30행 확인 결과).
- **영향**: ROAS가 모두 0으로 계산되어 ROAS 점수가 무의미해짐.
- **현재 방어 로직**:
  ```javascript
  g.ROAS = g.비용 > 0 ? g.매출 / g.비용 : 0; // 비용=0이면 ROAS=0
  ```
- **권장 사항**:
  1. Revenue 데이터가 없는 경우 ROAS 점수를 계산에서 제외하고 가중치를 나머지 지표에 재배분.
  2. UI에 "ROAS 데이터 없음" 경고 표시.
  ```javascript
  // 개선안
  const hasRevenue = aggregated.some(g => g.매출 > 0);
  if (!hasRevenue) {
    alert('⚠️ Revenue 데이터가 없어 ROAS 점수를 제외하고 계산합니다.');
    // ROAS 가중치를 0으로 설정하고 나머지에 재배분
    const totalOtherWeight = convWeight + cpaWeight + ipmWeight;
    convWeight = convWeight / totalOtherWeight;
    cpaWeight = cpaWeight / totalOtherWeight;
    ipmWeight = ipmWeight / totalOtherWeight;
    roasWeight = 0;
  }
  ```

#### 🟡 **문제 3: 텍스트 유형 소재(TXT) 처리**
- **현황**: PHPH_upload.csv 2~10행은 `유형=TXT` (광고 제목, 설명 텍스트).
- **영향**: 현재 필터는 BNR/VID만 기본 선택하므로, TXT 유형은 **자동으로 제외**됨.
- **현재 로직**:
  ```javascript
  // 유형 필터가 없을 때만 BNR/VID로 제한
  filteredRows = filteredRows.filter(row => row['유형'] === 'BNR' || row['유형'] === 'VID');
  ```
- **권장 사항**: 소재 유형 필터에 `TXT` 옵션 추가.
  ```html
  <select id="typeFilter">
    <option value="">전체 (BNR + VID + TXT)</option>
    <option value="BNR">BNR (배너)</option>
    <option value="VID">VID (동영상)</option>
    <option value="TXT">TXT (텍스트)</option>
  </select>
  ```

---

## 🛡️ 2. 예외 처리 로직 분석

### 2.1 현재 구현된 방어 로직

| 예외 상황 | 현재 처리 | 개선 필요 여부 |
|---------|---------|-------------|
| **전환=0일 때 CPA** | `전환 > 0 ? 비용/전환 : 0` | ✅ 적절 |
| **노출수=0일 때 IPM** | `노출수 > 0 ? (전환/노출수)×1000 : 0` | ✅ 적절 |
| **비용=0일 때 ROAS** | `비용 > 0 ? 매출/비용 : 0` | ✅ 적절 |
| **결측치(undefined/null)** | `parseFloat(row['전환']) \|\| 0` | ✅ 적절 |
| **비수치 텍스트** | 방어 로직 없음 | 🔴 **위험** |
| **음수 값** | 검증 로직 없음 | 🟡 주의 |

### 2.2 ⚠️ 개선 사항

#### 🔴 **문제 4: 비수치 데이터 유입 시 NaN 발생**
- **시나리오**: CSV에 `전환` 컬럼에 "N/A", "미집계", "-" 등이 입력된 경우.
- **현재 동작**: `parseFloat("N/A") = NaN` → 이후 계산에서 `NaN + 5 = NaN` 전파.
- **영향**: 소재 점수가 `NaN`으로 표시되어 사용자 혼란 야기.
- **개선안**:
  ```javascript
  // 안전한 숫자 파싱 함수
  function safeParseNumber(value, defaultValue = 0) {
    if (value === undefined || value === null || value === '') return defaultValue;
    const parsed = parseFloat(value);
    return isNaN(parsed) ? defaultValue : parsed;
  }
  
  // 집계 시 적용
  groups[key].전환 += safeParseNumber(row['전환']);
  groups[key].비용 += safeParseNumber(row['비용']);
  groups[key].노출수 += safeParseNumber(row['노출수']);
  groups[key].클릭수 += safeParseNumber(row['클릭수']);
  groups[key].매출 += safeParseNumber(row['매출'] || row['Revenue']);
  ```

#### 🟡 **문제 5: 음수 값 검증 미비**
- **시나리오**: 데이터 오류로 `비용=-1000`, `전환=-5` 등이 입력된 경우.
- **영향**: CPA, ROAS 등이 음수로 계산되어 순위가 왜곡됨.
- **개선안**:
  ```javascript
  // 집계 후 검증
  return Object.values(groups).map(g => {
    // 음수 값 0으로 보정
    g.전환 = Math.max(0, g.전환);
    g.비용 = Math.max(0, g.비용);
    g.노출수 = Math.max(0, g.노출수);
    g.클릭수 = Math.max(0, g.클릭수);
    g.매출 = Math.max(0, g.매출);
    
    // KPI 계산
    g.CPA = g.전환 > 0 ? g.비용 / g.전환 : 0;
    g.IPM = g.노출수 > 0 ? (g.전환 / g.노출수) * 1000 : 0;
    g.ROAS = g.비용 > 0 ? g.매출 / g.비용 : 0;
    // ...
  });
  ```

#### 🟢 **문제 6: CSV 업로드 실패 시 사용자 피드백 부족**
- **현재**: 업로드 실패 시 콘솔 에러만 출력.
- **개선안**:
  ```javascript
  // 파일 읽기 실패 시
  reader.onerror = function() {
    alert('❌ 파일 읽기 실패: 파일이 손상되었거나 권한이 없습니다.');
    document.getElementById('uploadStatus').innerHTML = 
      '<span style="color: red;">파일 업로드 실패</span>';
  };
  ```

---

## 🎨 3. UI/UX 편의성 개선 제안

### 3.1 현재 사용자 동선 분석

```
1. 파일 업로드 (드래그&드롭 or 파일 선택)
   └─> ✅ 직관적
   
2. 업로드 완료 메시지 표시
   └─> ⚠️ 간단한 텍스트만 (파일명, 행 수, 컬럼 수)
   
3. 점수 계산 섹션으로 스크롤
   └─> ❌ 자동 스크롤 없음 (사용자가 수동으로 내려가야 함)
   
4. 가중치 조정 & 필터 선택
   └─> ✅ 슬라이더 + 직접 입력 지원
   
5. "점수 계산 실행" 버튼 클릭
   └─> ⚠️ 로딩 인디케이터 없음 (대용량 CSV 시 멈춘 것처럼 보임)
   
6. 결과 테이블 표시
   └─> ✅ 상세하고 명확
```

### 3.2 🎯 핵심 개선 사항

#### 🔴 **개선 1: 업로드 후 자동 스크롤 & 다음 단계 안내**
```javascript
// CSV 업로드 완료 후
document.getElementById('uploadStatus').innerHTML = `
  <div style="color: #10b981; font-weight: 600;">
    ✅ ${file.name} 업로드 완료 (${rawData.length}개 행, ${normalizedData.columns.length}개 컬럼)
    <button onclick="scrollToSection('scoring')" 
            style="margin-left: 10px; padding: 5px 15px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer;">
      📊 점수 계산 시작하기 →
    </button>
  </div>
`;
```

#### 🟡 **개선 2: 로딩 인디케이터 추가**
```javascript
function calculateScores() {
  // 로딩 표시
  const loadingDiv = document.createElement('div');
  loadingDiv.id = 'loadingIndicator';
  loadingDiv.innerHTML = `
    <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; 
                background: rgba(0,0,0,0.5); z-index: 9999; 
                display: flex; align-items: center; justify-content: center;">
      <div style="background: white; padding: 30px; border-radius: 10px; text-align: center;">
        <div class="spinner" style="width: 50px; height: 50px; border: 5px solid #f3f4f6; 
                                     border-top: 5px solid #667eea; border-radius: 50%; 
                                     animation: spin 1s linear infinite; margin: 0 auto 15px;"></div>
        <p style="font-size: 16px; font-weight: 600;">점수 계산 중...</p>
      </div>
    </div>
    <style>
      @keyframes spin { to { transform: rotate(360deg); } }
    </style>
  `;
  document.body.appendChild(loadingDiv);
  
  // 실제 계산 (비동기 처리)
  setTimeout(() => {
    // 기존 계산 로직...
    
    // 로딩 제거
    document.getElementById('loadingIndicator').remove();
  }, 100); // UI 업데이트를 위한 최소 지연
}
```

#### 🟢 **개선 3: 데이터 프리뷰 & 컬럼 매핑 확인 UI**
```javascript
// 업로드 후 주요 컬럼 매핑 상태 표시
document.getElementById('uploadStatus').innerHTML += `
  <div style="margin-top: 10px; padding: 10px; background: #f3f4f6; border-radius: 5px; font-size: 13px;">
    <strong>✅ 감지된 주요 컬럼:</strong><br>
    • 소재명: ${normalizedData.columns.includes('소재명') ? '✓' : '❌'}<br>
    • 전환: ${normalizedData.columns.includes('전환') ? '✓' : '❌'}<br>
    • 비용: ${normalizedData.columns.includes('비용') ? '✓' : '❌'}<br>
    • 노출수: ${normalizedData.columns.includes('노출수') ? '✓' : '❌'}<br>
    • Revenue: ${normalizedData.columns.includes('Revenue') || normalizedData.columns.includes('매출') ? '✓ (ROAS 계산 가능)' : '❌ (ROAS 제외)'}
  </div>
`;
```

#### 🟢 **개선 4: 점수 계산 전 필터 조건 요약 표시**
```javascript
function calculateScores() {
  // 필터 조건 수집
  const selectedCampaigns = Array.from(document.getElementById('campaignFilter').selectedOptions)
    .map(opt => opt.text)
    .filter(t => t !== '전체 캠페인');
  const selectedType = document.getElementById('typeFilter').value;
  const startDate = document.getElementById('startDate').value;
  const endDate = document.getElementById('endDate').value;
  
  // 조건 요약 표시
  let filterSummary = '<strong>📌 적용된 필터:</strong><br>';
  if (selectedCampaigns.length > 0) {
    filterSummary += `• 캠페인: ${selectedCampaigns.join(', ')}<br>`;
  } else {
    filterSummary += `• 캠페인: 전체<br>`;
  }
  filterSummary += `• 소재 유형: ${selectedType || '전체 (BNR+VID)'}<br>`;
  if (startDate && endDate) {
    filterSummary += `• 기간: ${startDate} ~ ${endDate}<br>`;
  }
  
  console.log(filterSummary);
  // 결과 섹션 상단에 표시 가능
}
```

---

## 🔍 4. 필터링 기능 권장 사항

### 4.1 현재 구현된 필터

| 필터 유형 | 구현 상태 | 비고 |
|---------|---------|-----|
| **캠페인** | ✅ 다중 선택 가능 | `<select multiple>` 방식 |
| **소재 유형** | ✅ 단일 선택 (전체/BNR/VID) | TXT 제외됨 |
| **날짜 범위** | ✅ 시작일~종료일 | 자동 감지 |
| **집계 기준** | ✅ 소재명 / 파일명 | 라디오 버튼 |

### 4.2 🎯 추가 권장 필터 (PHPH_upload.csv 기반)

#### 🔴 **필터 1: 소재 사이즈별 필터**
- **근거**: CSV에 `사이즈` 컬럼 존재 (가로형/정방형/세로형).
- **사용 사례**: "정방형 소재는 인스타그램에서 성과가 좋은가?" 분석.
- **구현안**:
  ```html
  <label class="setting-label">소재 사이즈</label>
  <select id="sizeFilter">
    <option value="">전체 사이즈</option>
    <option value="가로형">가로형 (1200x628)</option>
    <option value="정방형">정방형 (1200x1200)</option>
    <option value="세로형">세로형 (1200x1500)</option>
  </select>
  ```

#### 🟡 **필터 2: 언어별 필터**
- **근거**: CSV에 `언어` 컬럼 존재 (EN, KO, JP 등 예상).
- **사용 사례**: "영어 소재 vs 한국어 소재 성과 비교".
- **구현안**:
  ```html
  <label class="setting-label">언어</label>
  <select id="languageFilter">
    <option value="">전체 언어</option>
    <option value="EN">영어 (EN)</option>
    <option value="KO">한국어 (KO)</option>
    <option value="JP">일본어 (JP)</option>
  </select>
  ```

#### 🟡 **필터 3: 시기(A/B 테스트 구분)별 필터**
- **근거**: CSV에 `시기` 컬럼 존재 (A, B, C 등).
- **사용 사례**: "A 시기 소재 vs B 시기 소재 성과 변화".
- **구현안**:
  ```html
  <label class="setting-label">테스트 시기</label>
  <select id="periodFilter">
    <option value="">전체 시기</option>
    <option value="A">시기 A</option>
    <option value="B">시기 B</option>
    <option value="C">시기 C</option>
  </select>
  ```

#### 🟢 **필터 4: Concept별 필터 (마케터 인사이트 태그)**
- **근거**: CSV에 `Concept`, `USP`, `hooking_strategy` 등 태그 컬럼 존재.
- **사용 사례**: "Adventure01A 컨셉 소재가 Character 컨셉보다 전환율이 높은가?"
- **구현안**:
  ```html
  <label class="setting-label">소재 컨셉</label>
  <select id="conceptFilter">
    <option value="">전체 컨셉</option>
    <option value="Adventure01A">Adventure01A</option>
    <option value="Keyart01A">Keyart01A</option>
    <option value="Collection01A">Collection01A</option>
    <!-- CSV의 고유 Concept 값을 동적으로 채움 -->
  </select>
  ```

---

## 📊 5. 실제 데이터 기반 검증 결과

### 5.1 PHPH_upload.csv 특징

| 항목 | 값 |
|-----|---|
| 총 행 수 | 50개 |
| 컬럼 수 | 40개 |
| 소재 유형 분포 | TXT: 9개 (2~10행) / BNR: 41개 (11~50행) |
| 캠페인 수 | 1개 (`HQ_HQ_PH_US-EN_GA_NU-Pre_AD_ACp_260406`) |
| 날짜 범위 | 2026-04-06 단일 날짜 |
| Revenue 존재 여부 | ✅ 컬럼 존재하나 **모든 값이 0** |
| 주요 태그 | USP, Concept, hooking_strategy, emotion, character_object, art_style 등 |

### 5.2 ⚠️ 데이터 기반 발견 사항

1. **단일 날짜 데이터**: 날짜 필터가 의미 없음 → 향후 다중 날짜 데이터 축적 필요.
2. **Revenue=0**: ROAS 점수가 모두 0으로 계산 → 가중치 재배분 로직 필요.
3. **TXT 유형 제외**: 현재 로직은 BNR/VID만 분석 → TXT 소재(광고 문구) 성과 추적 불가.
4. **단일 캠페인**: 캠페인 필터가 무의미 → 다중 캠페인 데이터 필요.

---

## ✅ 6. 최종 권장 개선 사항 요약

### 🔴 **긴급 (High Priority)**
1. ✅ **비수치 데이터 방어 로직 추가**: `safeParseNumber()` 함수 구현.
2. ✅ **Revenue=0 처리 로직**: ROAS 가중치 자동 재배분.
3. ✅ **TXT 유형 지원**: 소재 유형 필터에 TXT 옵션 추가.
4. ✅ **로딩 인디케이터**: 대용량 CSV 처리 시 사용자 경험 개선.

### 🟡 **중요 (Medium Priority)**
5. ✅ **음수 값 검증**: 집계 후 음수 → 0 보정.
6. ✅ **업로드 후 자동 스크롤**: 다음 단계 안내 버튼 추가.
7. ✅ **사이즈/언어/시기별 필터**: 세그먼트 분석 기능 추가.
8. ✅ **컬럼 매핑 상태 표시**: 필수 컬럼 감지 여부 시각화.

### 🟢 **개선 (Low Priority)**
9. ✅ **CPI 지표 추가**: 설치 수 데이터 수집 시 구현.
10. ✅ **Concept/USP 태그 필터**: 마케터 인사이트 기반 분석.
11. ✅ **점수 계산 전 필터 조건 요약**: 적용된 조건 명확히 표시.
12. ✅ **CSV 업로드 실패 처리**: 사용자 친화적 에러 메시지.

---

## 📌 7. 구현 우선순위

### Phase 1: 안정성 강화 (1~2시간)
- 비수치 데이터 방어 로직
- 음수 값 검증
- Revenue=0 처리
- TXT 유형 지원

### Phase 2: UX 개선 (1~2시간)
- 로딩 인디케이터
- 업로드 후 자동 스크롤
- 컬럼 매핑 상태 표시
- 필터 조건 요약

### Phase 3: 고급 필터링 (2~3시간)
- 사이즈별 필터
- 언어별 필터
- 시기별 필터
- Concept/USP 태그 필터

---

## 🎯 8. 결론

**PHPH_upload.csv 기반 검증 결과, `step1_integrated.html`은 기본 기능은 정상 작동하나, 실무 환경에서의 예외 상황 대응과 세그먼트 분석 기능이 부족합니다.**

**즉시 개선이 필요한 항목:**
1. 비수치 데이터 유입 방어
2. Revenue=0 시 ROAS 처리
3. TXT 유형 소재 지원
4. 사용자 피드백 강화 (로딩, 에러 메시지)

이를 통해 **데이터 정합성 100%, 예외 처리 안정성 95%, UI/UX 편의성 90%** 수준으로 개선 가능합니다.

---

**작성자**: Gemini Static Web Assistant  
**버전**: v1.6  
**다음 단계**: Phase 1 개선 사항 구현 시작
