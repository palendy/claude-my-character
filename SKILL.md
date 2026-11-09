---
name: 내캐릭터
description: 내 Claude Code 세션 기록을 전부 훑어서 나를 닮은 귀여운 캐릭터를 그려 주고, 성격·개발 유형 코드·능력치·입버릇·배지·동료 궁합을 숫자 근거와 함께 알려 준다. 결과는 내 PC의 HTML 한 장과 공유용 PNG 카드다. "/내캐릭터", "내 캐릭터 만들어줘", "내 성격 분석", "나 어떤 개발자야" 요청 시 사용. 인자로 기간(예: 30)을 받는다.
---

# /내캐릭터 — 세션 기록으로 만드는 나의 캐릭터

목표는 **"이거 완전 나잖아"** 한마디다. 재미는 근거가 구체적일 때 생긴다. 누구에게나 맞는 말(바넘 효과)은 재미가 없다.
그래서 **성격·능력치·배지는 반드시 stats.json의 숫자나 실제 입버릇을 근거로 단다.**

## 프라이버시 경계 (먼저 지킨다)

- 로그는 **내 PC 밖으로 보내지 않는다.** 웹 검색·업로드·아티팩트 게시·외부 API 호출을 하지 않는다.
- 결과는 `~/내캐릭터/`에만 쓴다(stats.json · profile.json · HTML · 카드 SVG).
- **공유 카드에 보이는 칸**(name · title · catchphrase · stats 라벨 · badges 이름)에는 프로젝트명·고객사·사람 이름·사내 주소·
  코드 조각을 넣지 않는다. 동료에게 그대로 보여 줘도 되는 말만 쓴다. 페이지 본문 근거에는 숫자와 짧은 입버릇만 쓴다.

## 1. 집계 (스크립트, 약 20초)

```bash
python3 ~/.claude/skills/내캐릭터/scripts/analyze.py            # 전체 기간
python3 ~/.claude/skills/내캐릭터/scripts/analyze.py --days 30  # 인자에 숫자가 있으면 최근 N일
```

출력은 `~/내캐릭터/stats.json` 경로 한 줄이다. 그 파일을 **처음부터 끝까지 읽는다.** 들어 있는 것:
`totals`(말 수·도구 호출·끊기) · `time`(24시간 분포·주말·새벽·최장 연속 출석·가장 긴 몰입·가장 늦은 새벽의 말) ·
`talk`(말 길이·반말/존댓말·물음표·말줄임·말버릇 범주·짧은 말 Top·단어·두 단어 묶음) · `claude_side`(도구·MCP·스킬·
슬래시 명령·서브에이전트·모델·git) · `insights_facets`(`/insights`를 돌린 적 있으면 결과·마찰 종류) ·
`samples`(가린 내 말 90개) · `type_inputs`(유형 코드 공식에 들어가는 값).

메시지가 30개 미만이면 "기록이 적어서 대충 그린 캐릭터예요"라고 먼저 말하고 진행한다.

## 2. 근거 확인

쓰려는 숫자가 stats.json에 없으면 직접 센다. 추측한 숫자는 쓰지 않는다.

```bash
python3 ~/.claude/skills/내캐릭터/scripts/analyze.py --phrases "완벽한거지,철저하게,고마워" --out /tmp/내캐릭터-phrases.json
```

`phrase_counts`에 표현마다 몇 번 나왔는지와 마지막 예시가 들어 있다.

## 3. 해석 → `~/내캐릭터/profile.json` 작성

스키마와 예시는 [reference/profile.md](reference/profile.md)에 있다. 먼저 읽는다. 원칙:

- **`work_labels`를 먼저 쓴다.** `samples.random`의 말을 순서대로 하나씩 읽고 업무면 `W`, 딴짓이면 `D` 한 글자를 붙여
  90글자 문자열로 적는다. 업무는 맡은 제품·코드·문서·배포·운영과 그 일을 하며 던진 짧은 지시("다시 시도", "푸시해줘")다.
  딴짓은 일과 상관없는 것이다: 개인 호기심, Claude 자체에 대한 궁금증, 개인 프로젝트, 공부, 놀이·이벤트, 생활 질문.
  `projects_top`의 상위 프로젝트가 그 사람의 일이다. 애매하면 `W`로 둔다. 단어로 고르지 말고 말 전체의 목적으로 판단한다.
- **유형 코드와 등급은 고르지 않는다.** 렌더러가 `work_labels`의 딴짓 비율과 `type_inputs`로 모두 같은 공식을 써서 계산한다.
  동료끼리 같은 잣대로 비교하라고 그렇게 했다. 내가 쓸 것은 `type_code.summary`(한두 문장)와 `rarity.reason`(왜 이 등급인지 숫자로)뿐이다.
  축은 W 업무형/D 딴짓형 · S 한마디형/L 브리핑형 · O 한우물형/M 멀티형 · A 오전형/P 오후형이다.
- **종(species)·눈·입·소품은 성격에서 고른다.** 아무거나 고르지 않는다. 고른 이유가 traits 안에서 설명돼야 한다
  (예: 검증 집착 → 돋보기·방패, 새벽형 → 수면모자·zzz, 위임형 → 헤드셋·깃발). 매핑 표는 reference에 있다.
- traits 3~4개, stats 5~6개, badges 4~6개를 쓴다. **모두 `evidence`에 숫자나 실제 입버릇**을 단다.
- 이름은 "형용사 + 동물" 꼴의 짧은 별명이다(예: "철벽검증 댕댕이", "새벽코딩 부엉이").
- 말투는 친구가 놀리듯 다정하게 쓴다. 한국어로 쓰고 AI 말투를 쓰지 않는다("~할 수 있습니다", "다양한", "인사이트" 금지).
- **매운맛이 기본이다.** roast·weakness·worst_match는 친구가 회식 자리에서 놀리듯 세게 쓴다. 숫자로 정곡을 찌르고 돌려 말하지 않는다.
  그래도 인신공격과 외모·성별·나이·건강 언급은 하지 않는다. claude_says만 다정하게 쓴다.
- `best_match`·`worst_match`는 다른 유형의 가상 동료다. 미니 캐릭터 파라미터를 함께 넣는다.

## 4. 그리기

```bash
python3 ~/.claude/skills/내캐릭터/scripts/render.py ~/내캐릭터/profile.json ~/내캐릭터/stats.json
```

`~/내캐릭터/내캐릭터-YYYYMMDD.html`과 `…-card.svg`가 생긴다. 페이지 맨 아래 [PNG로 저장]·[이미지 복사]로 1080×1350 카드를 받는다.
렌더러가 실패하면 오류의 필드를 고치고 다시 돌린다. 캐릭터 부품이 맞는지 보려면 `render.py --gallery /tmp/kit.html`.

## 5. 열어 주고 짧게 알린다

```bash
f=~/내캐릭터/내캐릭터-$(date +%Y%m%d).html
if grep -qi microsoft /proc/version 2>/dev/null; then explorer.exe "$(wslpath -w "$f")"; \
elif command -v open >/dev/null; then open "$f"; else xdg-open "$f" 2>/dev/null; fi; echo "$f"
```

채팅에는 짧게 쓴다. 캐릭터 이름 · 유형 코드와 등급 · 한 줄 성격 · 파일 경로 · "로그는 PC 밖으로 나가지 않았어요" 한 줄.
