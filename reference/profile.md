# profile.json 스키마

렌더러(`scripts/render.py`)가 읽는 필드다. 없는 칸은 화면에서 빠진다. `type_code.code/name/axes`와 `rarity.tier/stars`는
stats.json 값으로 덮어쓰니 적지 않아도 된다.

| 필드 | 뜻 | 화면 |
|---|---|---|
| `name` | "형용사 + 동물" 별명, 10자 안팎 | 첫 화면 · 카드 |
| `title` | 한 줄 직함 ("기존 사용자 수호대장 · 확인하고 또 확인") | 첫 화면 · 카드 |
| `species` `eyes` `mouth` `accessories[≤4]` `colors` | 캐릭터 부품 (아래 표) | 캐릭터 |
| `extra_svg` | (선택) 400×400 좌표계 SVG 조각 하나. 소품 표에 없는 걸 꼭 그려야 할 때만 | 캐릭터 |
| `hashtags[≤4]` | `#` 없이 | 첫 화면 |
| `rarity.reason` | 이 등급인 이유, 숫자로 | 첫 화면 |
| `type_code.summary` | 유형 한두 문장 | 유형 칸 |
| `wrapped_title`, `wrapped[≤6]` `{big,label,comment}` | 연말결산식 큰 숫자. `big`이 숫자로 시작하면 올라가는 애니메이션 | 숫자 칸 |
| `chronotype`, `chronotype_comment` | 시간대 별명과 한두 문장. 가장 늦은 새벽의 말을 쓰면 재밌다 | 시계 칸 |
| `traits[3~4]` `{emoji,title,body,evidence}` | 성격. evidence는 숫자·입버릇 | 성격 칸 |
| `stats[5~6]` `{label,value 0~100,evidence}` | 능력치. 카드엔 앞 6개 | 스탯 · 카드 |
| `superpower`, `weakness` | 필살기 · 약점 한 줄 | 스탯 칸 |
| `catchphrase` | 카드 말풍선, 10자 안팎 | 카드 |
| `catchphrases[≤10]` `{text,count}` | 입버릇 Top | 입버릇 칸 |
| `catchphrase_comment` | 한 줄 | 입버릇 칸 |
| `badges[4~6]` `{icon(이모지),name(9자 안),desc}` | 업적. 카드엔 앞 3개 | 배지 · 카드 |
| `best_match`, `worst_match` | `{name,why,species,eyes,mouth,accessories,colors}` 가상 동료 | 궁합 칸 |
| `claude_says` | Claude가 건네는 한마디, 3~4문장, 다정하게 | 마지막 칸 |
| `roast` | 한 줄 놀림 (맛에 따라 세기 조절) | 마지막 칸 |
| `fortune` | 내일의 개발 운세 한 줄 | 마지막 칸 |

`colors`: `body` `belly` `accent` `cheek` `bg` `bg2` (모두 `#rrggbb`). 배경은 연한 파스텔, accent는 진하게 고른다.

## 부품

- **species**: cat · dog · bear · panda · rabbit · fox · hamster · owl · penguin · dino · ghost · robot · slime · otter · chick
- **eyes**: round · sparkle · sleepy · determined · wink · dot · star · teary
- **mouth**: smile · cat · o · flat · grin · smirk · wobbly
- **accessories**: glasses · magnifier · coffee · headset · laptop · nightcap · wizard_hat · crown · hardhat · checklist · bow ·
  sprout · flag · sweat · zzz · sparkles · rocket · shield · terminal · bug_net · scarf · heart · book · wrench · stopwatch · lightbulb

## 성격 → 부품 고르기 (예시일 뿐, 근거가 다르면 다르게)

| 신호 (stats.json) | 어울리는 것 |
|---|---|
| 검증·완벽 범주 높음, Playwright·테스트 많음 | dog·owl, determined 눈, magnifier · shield · checklist |
| `tool_calls_per_prompt` 높음 (크게 맡김) | headset · flag, 말 짧고 반말 많음이면 smirk |
| 손수형 (도구 적음, Edit·Read 비중 큼) | hamster·otter, wrench · laptop |
| 밤 비율 높음 | owl·ghost, sleepy 눈, nightcap · zzz · coffee |
| 설명요청·호기심 높음 | rabbit·chick, sparkle 눈, book · lightbulb |
| 속도·끊기 많음 | fox·dino, rocket · stopwatch · sweat |
| 배포·git 많음 | rocket · flag · hardhat |
| 다정 범주 높음, 감사 표현 많음 | bear·panda, heart · bow, cat 입 |
| 새로 시작함 (기록 적음) | chick·slime, sprout |
| MCP·서브에이전트·스킬 다양 | robot·wizard_hat · terminal |

## 예시 (가공의 사람)

```json
{
  "name": "새벽코딩 부엉이",
  "title": "모두 잘 때 PR을 여는 사람",
  "species": "owl", "eyes": "sleepy", "mouth": "smile",
  "accessories": ["nightcap", "coffee", "terminal"],
  "colors": {"body": "#9c8ad8", "belly": "#f1ecff", "accent": "#6c4bd8", "cheek": "#ffb3c7", "bg": "#e9e4ff", "bg2": "#d9d0ff"},
  "hashtags": ["새벽2시", "커피수혈", "조용한_고수"],
  "rarity": {"reason": "말의 41%가 밤 10시~새벽 4시예요. 밤 축이 거의 끝까지 갔어요."},
  "type_code": {"summary": "혼자 조용히 손으로 고치고, 결과만 확인하는 밤의 장인."},
  "wrapped_title": "석 달, 61일의 기록",
  "wrapped": [{"big": "1,204번", "label": "Claude에게 건넨 말", "comment": "그중 493번이 밤 10시 이후"}],
  "chronotype": "새벽 2시가 피크인 올빼미형",
  "chronotype_comment": "가장 늦은 말은 새벽 4시 12분의 \"이거 내일 아침에 다시 보자\"였어요.",
  "traits": [{"emoji": "🌙", "title": "밤에 깨어나는 장인", "body": "낮에는 조용하다가 밤에 몰아칩니다.", "evidence": "밤 비율 41% · 최장 몰입 5.2시간(새벽 1시 시작)"}],
  "stats": [{"label": "야행성", "value": 94, "evidence": "밤 비율 41%"}],
  "superpower": "아무도 없는 새벽에 PR을 세 개 연다.",
  "weakness": "아침 회의 때 그 PR을 기억하지 못한다.",
  "catchphrase": "내일 다시 보자",
  "catchphrases": [{"text": "내일 다시 보자", "count": "23번"}],
  "badges": [{"icon": "🌙", "name": "새벽 수호자", "desc": "밤 10시 이후 493번"}],
  "best_match": {"name": "아침형 리뷰어 병아리", "species": "chick", "eyes": "sparkle", "mouth": "smile", "accessories": ["checklist"], "colors": {"body": "#ffe066"}, "why": "밤에 연 PR을 아침 9시에 바로 봐 줘요."},
  "worst_match": {"name": "9시 회의 판다", "species": "panda", "eyes": "round", "mouth": "flat", "accessories": ["stopwatch"], "why": "회의를 9시에 잡는 순간 상극."},
  "claude_says": "새벽에 같이 일한 날이 많았죠. 다음엔 조금 일찍 자도 PR은 도망가지 않아요.",
  "roast": "커피 이야기가 버그 이야기보다 많았어요.",
  "fortune": "내일은 해가 떠 있을 때 버그 하나를 잡습니다."
}
```
