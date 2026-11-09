#!/usr/bin/env python3
"""Aggregate local Claude Code session logs into a fun-stats JSON for /내캐릭터.

Reads only local files (~/.claude/projects/**/*.jsonl and, if present,
~/.claude/usage-data/{facets,session-meta}). Nothing leaves the machine.
Output: one JSON file with aggregate numbers plus a small, masked sample of
the user's own prompts so the model can write a grounded personality.

Usage: python3 analyze.py [--days N] [--out PATH] [--root ~/.claude]
"""
import argparse
import bisect
import collections
import datetime as dt
import glob
import json
import os
import random
import re
import statistics
import sys

# ---------- what counts as a real human prompt ----------
SYSTEM_PREFIXES = (
    "<task-notification", "<local-command", "<command-", "This session is being continued",
    "Base directory for", "(Re-invocation", "<system-reminder", "<artifact-content-", "Caveat:",
    "<user-prompt-submit-hook", "[Request interrupted", "You extract what i", "<ci-monitor-event",
    "# Autonomous loop", "<bash-", "<tool_use_error",
)
INTERRUPT = "[Request interrupted"
IMAGE_RE = re.compile(r"\[Image[^\]]*\]")
PASTE_RE = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)
CMD_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")

# ---------- masking for samples ----------
MASKS = [
    (re.compile(r"https?://\S+"), "<링크>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<메일>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[bap]|AKIA)[-_A-Za-z0-9]{10,}\b"), "<키>"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "<토큰>"),
    (re.compile(r"(/home/|/Users/|C:\\\\Users\\\\)\S+"), "<경로>"),
]


def mask(s, limit=160):
    for rx, rep in MASKS:
        s = rx.sub(rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ---------- talk-style lexicons (fun stats only; the model interprets) ----------
CATEGORIES = {
    "검증": ["확인", "검증", "테스트", "진짜", "실제로", "제대로", "맞아?", "맞는지", "증명", "근거"],
    "정정": ["아니", "다시", "틀렸", "그게 아니라", "잘못", "왜 또", "말고", "원복", "되돌"],
    "호기심": ["왜", "어떻게", "뭐야", "궁금", "무슨", "어떤", "원리", "이유"],
    "속도": ["빨리", "바로", "그냥", "일단", "얼른", "급해", "당장"],
    "완벽": ["완벽", "꼼꼼", "철저", "끝까지", "반드시", "확실", "전부", "모두", "최대한"],
    "다정": ["고마워", "감사", "수고", "좋아", "굿", "최고", "잘했", "멋지", "훌륭"],
    "진행": ["진행", "계속", "이어서", "해줘", "해 줘", "가자", "고고", "ㄱㄱ"],
    "설명요청": ["설명", "쉽게", "알려줘", "정리", "요약", "eli5", "easy"],
    "배포": ["푸시", "push", "PR", "머지", "merge", "배포", "커밋", "commit"],
}
POLITE_END = re.compile(r"(요|니다|세요|까요|죠)[\s.!?~]*$")
BANMAL_END = re.compile(r"(해|줘|야|어|지|자|냐|니|라|봐|돼|네|군|다)[\s.!?~]*$")
LAUGH = re.compile(r"ㅋ{2,}|ㅎ{2,}|ㅠ{2,}|ㅜ{2,}")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9_+-]{2,}")
STOP = set(
    "그리고 그럼 근데 이거 저거 그거 이건 그건 있는 없는 하는 하고 해서 에서 으로 이렇게 그렇게 지금 현재 "
    "대한 위해 같은 하면 되는 했는데 하는데 있어 없어 the and for you this that with are not was have from "
    "되나 하나 인지 처럼 까지 부터 하지 이런 그런 어떤 혹시 해줘 해주고 해주세요 그래 그래서 한번 좀더 같아 "
    "아니라 거야 거지 건데 것도 것이 것을 수도 하게 할때 할떄 있게 있는지 하는지 어디 뭔가 저기 여기".split()
)


def classify(text):
    t = text.strip()
    return {k: sum(t.count(w) for w in ws) for k, ws in CATEGORIES.items()}


# code letters: 업무/딴짓 W/D · 말 길이 S/L · 일하는 방식 O/M · 시간 A/P
TONE = {"WS": "칼같은", "WL": "꼼꼼한", "DS": "몰래 딴짓하는", "DL": "딴짓에 진심인"}
ROLE = {"OA": "아침 장인", "OP": "오후 장인", "MA": "아침 저글러", "MP": "오후 저글러"}
TYPE_NAMES = {t[0] + t[1] + r[0] + r[1]: f"{tn} {rn}" for t, tn in TONE.items() for r, rn in ROLE.items()}
TIERS = {1: "N", 2: "R", 3: "SR", 4: "SSR", 5: "UR"}


def clamp(x):
    return max(0.0, min(1.0, x))


def dev_type(offtask, short, long, multi_ratio, median_hour):
    """Same formula for everyone so colleagues can compare codes. value < .5 → left letter.

    `offtask` is (off-task, labelled) counts over samples.random, labelled by Claude in profile.json
    (`work_labels`); None until then, which leaves the first letter as "?".
    Each axis compares two habits of the same person (or a clock time), not keyword lists.
    """
    sl = long / (short + long) if short + long else 0.5
    om = clamp(multi_ratio / 0.6)  # 30% of prompts sent while another session is running is the midpoint
    ap = clamp((median_hour - 10) / 8)  # half of my prompts before 14:00 is the midpoint
    hh = int(median_hour) % 24
    if offtask and offtask[1]:
        wd = clamp(offtask[0] / offtask[1] / 0.4)  # one prompt in five off-task is the midpoint
        first = {"letter": "W" if wd < .5 else "D", "value": round(wd, 2),
                 "measure": f"무작위로 뽑은 말 {offtask[1]}개 중 딴짓 {offtask[0]}개"}
    else:
        first = {"letter": "?", "value": 0.5, "measure": "아직 업무/딴짓 표시 전"}
    axes = [
        dict(first, left="W 업무형", right="D 딴짓형"),
        {"letter": "S" if sl < .5 else "L", "left": "S 한마디형", "right": "L 브리핑형", "value": round(sl, 2),
         "measure": f"25자 이하 {short}번 · 100자 이상 {long}번"},
        {"letter": "O" if om < .5 else "M", "left": "O 한우물형", "right": "M 멀티형", "value": round(om, 2),
         "measure": f"다른 대화를 돌리는 중에 보낸 말 {multi_ratio:.0%}"},
        {"letter": "A" if ap < .5 else "P", "left": "A 오전형", "right": "P 오후형", "value": round(ap, 2),
         "measure": f"말의 절반을 {hh}시 {int(median_hour % 1 * 60):02d}분까지 보냄"},
    ]
    code = "".join(a["letter"] for a in axes)
    sharp = sum(abs(a["value"] - .5) for a in axes) / len(axes) * 2  # 0 = balanced, 1 = extreme
    stars = 1 + round(sharp * 4)
    return {"code": code, "name": TYPE_NAMES.get(code, ""), "axes": axes,
            "rarity": {"tier": TIERS[stars], "stars": stars, "sharpness": round(sharp, 2)}}


def multi_ratio(prompts, window_min=10):
    """Share of prompts sent while a different session also got a prompt within ±window."""
    times = [p[0] for p in prompts]  # prompts are sorted by time
    win = dt.timedelta(minutes=window_min)
    hits = 0
    for i, (when, _, sid, _) in enumerate(prompts):
        lo = bisect.bisect_left(times, when - win)
        hi = bisect.bisect_right(times, when + win)
        hits += any(prompts[k][2] != sid for k in range(lo, hi))
    return hits / len(prompts)


def median_hour(prompts):
    """Median clock time; the day starts at 05:00 so late-night work counts as the end of the day."""
    hrs = sorted(((p[0].hour - 5) % 24) + 5 + p[0].minute / 60 for p in prompts)
    return hrs[len(hrs) // 2]


def iter_lines(path):
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                yield line
    except OSError:
        return


HOME = os.path.expanduser("~").rstrip("/")


def project_name(cwd):
    """Repo-level name: worktrees fold into their repo, sub-dirs into the top folder under ~."""
    cwd = (cwd or "").rstrip("/")
    if "/.claude/worktrees/" in cwd:
        cwd = cwd.split("/.claude/worktrees/")[0]
    if cwd.startswith(HOME + "/"):
        return cwd[len(HOME) + 1 :].split("/")[0]
    return os.path.basename(cwd)


def local(ts):
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="최근 N일만 (0 = 전체)")
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--phrases", default="", help="쉼표로 구분한 표현의 등장 횟수를 센다 (근거 확인용)")
    a = ap.parse_args()

    since = None
    if a.days > 0:
        since = dt.datetime.now().astimezone() - dt.timedelta(days=a.days)

    files = glob.glob(os.path.join(a.root, "projects", "*", "*.jsonl"))
    seen_uuid = set()
    seen_prompt = set()
    prompts = []  # (local_dt, text, session, project)
    interrupts = 0
    images = 0
    pastes = 0
    slash = collections.Counter()
    tools = collections.Counter()
    mcp = collections.Counter()
    skills = collections.Counter()
    agents = collections.Counter()
    models = collections.Counter()
    git = collections.Counter()
    tool_errors = 0
    tool_results = 0
    session_span = collections.defaultdict(list)
    assistant_turns = 0
    out_tokens = 0

    for path in files:
        proj_dir = os.path.basename(os.path.dirname(path))
        if proj_dir.startswith("-tmp"):
            continue  # scratch / automated runs
        if since and dt.datetime.fromtimestamp(os.path.getmtime(path)).astimezone() < since:
            continue
        for line in iter_lines(path):
            if '"type":"user"' not in line and '"type":"assistant"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            typ = d.get("type")
            if typ not in ("user", "assistant") or d.get("isSidechain"):
                continue
            uid = d.get("uuid")
            if uid:
                if uid in seen_uuid:
                    continue  # forked / resumed sessions copy history
                seen_uuid.add(uid)
            when = local(d.get("timestamp", ""))
            if when is None or (since and when < since):
                continue
            sid = d.get("sessionId", path)
            cwd = d.get("cwd") or ""
            m = d.get("message") or {}
            content = m.get("content")

            if typ == "assistant":
                assistant_turns += 1
                if m.get("model") and not str(m.get("model")).startswith("<"):
                    models[m["model"]] += 1
                out_tokens += (m.get("usage") or {}).get("output_tokens", 0) or 0
                if isinstance(content, list):
                    for blk in content:
                        if not isinstance(blk, dict) or blk.get("type") != "tool_use":
                            continue
                        name = blk.get("name", "?")
                        tools[name] += 1
                        if name.startswith("mcp__"):
                            mcp[name.split("__")[1]] += 1
                        inp = blk.get("input") or {}
                        if name == "Skill":
                            skills[str(inp.get("skill", "?"))] += 1
                        if name in ("Agent", "Task"):
                            agents[str(inp.get("subagent_type", "general"))] += 1
                        if name == "Bash":
                            cmd = str(inp.get("command", ""))
                            if "git commit" in cmd or "-c user.name" in cmd and "commit" in cmd:
                                git["commit"] += 1
                            if "git push" in cmd:
                                git["push"] += 1
                            if "gh pr create" in cmd:
                                git["pr"] += 1
                continue

            # ---- user records ----
            if isinstance(content, list):
                if any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content):
                    for x in content:
                        if isinstance(x, dict) and x.get("type") == "tool_result":
                            tool_results += 1
                            if x.get("is_error"):
                                tool_errors += 1
                    continue
                text = " ".join(
                    x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text"
                )
                images += sum(1 for x in content if isinstance(x, dict) and x.get("type") == "image")
            else:
                text = content or ""
            if not text:
                continue
            for cm in CMD_RE.findall(text):
                slash[cm] += 1
            if text.startswith(INTERRUPT):
                interrupts += 1
                continue
            if d.get("isMeta") or d.get("promptSource") == "system":
                continue
            st = text.lstrip()
            if st.startswith(SYSTEM_PREFIXES):
                continue
            if len(st) > 2500 and st.startswith("#"):
                continue  # expanded command/skill template, not typed by a human
            images += len(IMAGE_RE.findall(text))
            n_paste = len(PASTE_RE.findall(text))
            pastes += n_paste
            clean = IMAGE_RE.sub("", PASTE_RE.sub(" ", text)).strip()
            if not clean:
                continue
            key = (d.get("timestamp", "")[:16], clean[:200])
            if key in seen_prompt:
                continue
            seen_prompt.add(key)
            prompts.append((when, clean, sid, project_name(cwd) or proj_dir))
            session_span[sid].append(when)

    if not prompts:
        print(json.dumps({"error": "사람이 보낸 메시지를 찾지 못했습니다. ~/.claude/projects 를 확인하세요."}, ensure_ascii=False))
        sys.exit(1)

    # machine-generated prompts (scripts calling claude -p) repeat one long template
    heads = collections.Counter(p[1][:60] for p in prompts if len(p[1]) > 200)
    prompts = [p for p in prompts if not (len(p[1]) > 200 and heads[p[1][:60]] >= 3)]
    prompts.sort(key=lambda p: p[0])
    n = len(prompts)
    lens = [len(p[1]) for p in prompts]

    # ---- time ----
    hour = [0] * 24
    wday = [0] * 7
    days = collections.Counter()
    for when, *_ in prompts:
        hour[when.hour] += 1
        wday[when.weekday()] += 1
        days[when.date()] += 1
    active = sorted(days)
    streak = best = 1
    for i in range(1, len(active)):
        streak = streak + 1 if (active[i] - active[i - 1]).days == 1 else 1
        best = max(best, streak)
    busiest_day, busiest_cnt = days.most_common(1)[0]
    night = sum(hour[h] for h in range(0, 6))
    late = sum(hour[h] for h in (22, 23, 0, 1, 2, 3))
    morning = sum(hour[h] for h in range(5, 10))
    # latest-night prompt (closest to 4am)
    def night_score(w):
        return (w.hour - 4) % 24  # 3:59 → 23 (latest)
    night_prompts = [p for p in prompts if p[0].hour < 6]
    latest_night = max(night_prompts, key=lambda p: night_score(p[0]), default=None)
    # focus bursts: consecutive prompts in one session with gaps < 45 min
    bursts = []
    for times in session_span.values():
        times.sort()
        start = prev = times[0]
        for t in times[1:]:
            if (t - prev).total_seconds() > 45 * 60:
                bursts.append(((prev - start).total_seconds() / 3600, start))
                start = t
            prev = t
        bursts.append(((prev - start).total_seconds() / 3600, start))
    longest_burst = max(bursts, key=lambda b: b[0])

    # ---- talk style ----
    cat_tot = collections.Counter()
    polite = banmal = q = ex = laugh = ell = emoji = thanks = short = short25 = long100 = 0
    words = collections.Counter()
    bigr = collections.Counter()
    shorts = collections.Counter()
    for _, t, *_ in prompts:
        for k, v in classify(t).items():
            cat_tot[k] += v
        last = t.strip().splitlines()[-1] if t.strip() else ""
        if POLITE_END.search(last):
            polite += 1
        elif BANMAL_END.search(last):
            banmal += 1
        q += "?" in t
        ex += "!" in t
        laugh += bool(LAUGH.search(t))
        ell += (".." in t or "…" in t)
        emoji += bool(EMOJI.search(t))
        if len(t) <= 25:
            short25 += 1
        elif len(t) >= 100:
            long100 += 1
        if len(t) <= 12:
            short += 1
            shorts[t.strip()] += 1
        toks = [w for w in TOKEN.findall(MASKS[0][0].sub(" ", t)) if w.lower() not in STOP]
        words.update(w.lower() if w.isascii() else w for w in toks)
        bigr.update(" ".join(toks[i : i + 2]) for i in range(len(toks) - 1))

    per100 = {k: round(v * 100 / n, 1) for k, v in cat_tot.items()}
    type_inputs = {"short": short25, "long": long100, "multi_ratio": round(multi_ratio(prompts), 3),
                   "median_hour": round(median_hour(prompts), 3)}

    # ---- facets / session-meta (from /insights cache, optional) ----
    facets = collections.defaultdict(collections.Counter)
    summaries, frictions = [], []
    fdir = os.path.join(a.root, "usage-data", "facets")
    for fp in glob.glob(os.path.join(fdir, "*.json")):
        try:
            f = json.load(open(fp))
        except Exception:
            continue
        for key in ("outcome", "claude_helpfulness", "session_type", "primary_success"):
            if f.get(key):
                facets[key][f[key]] += 1
        for key in ("goal_categories", "friction_counts", "user_satisfaction_counts"):
            for k, v in (f.get(key) or {}).items():
                facets[key][k] += v
        if f.get("brief_summary"):
            summaries.append(mask(f["brief_summary"], 240))
        if f.get("friction_detail"):
            frictions.append(mask(f["friction_detail"], 200))
    resp_times = []
    langs = collections.Counter()
    for fp in glob.glob(os.path.join(a.root, "usage-data", "session-meta", "*.json")):
        try:
            sm = json.load(open(fp))
        except Exception:
            continue
        resp_times += [x for x in sm.get("user_response_times", []) if isinstance(x, (int, float)) and x < 3600]
        langs.update(sm.get("languages") or {})

    # ---- samples ----
    rnd = random.Random(a.seed)
    pool = [p for p in prompts if 4 <= len(p[1])]
    sample = rnd.sample(pool, min(90, len(pool)))
    sample.sort(key=lambda p: p[0])
    longest = sorted(prompts, key=lambda p: len(p[1]), reverse=True)[:3]
    proj = collections.Counter(p[3] for p in prompts)

    def fmt(p, limit=160):
        return {"when": p[0].strftime("%Y-%m-%d %a %H:%M"), "text": mask(p[1], limit)}

    phrase_counts = {}
    for ph in [x.strip() for x in a.phrases.split(",") if x.strip()]:
        hits = [p for p in prompts if ph.lower() in p[1].lower()]
        phrase_counts[ph] = {"prompts": len(hits), "example": fmt(hits[-1], 100) if hits else None}

    out = {
        "type_inputs": type_inputs,
        "type_code": dev_type(None, **type_inputs),
        "phrase_counts": phrase_counts,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "window_days": a.days or "all",
        "period": {"from": prompts[0][0].date().isoformat(), "to": prompts[-1][0].date().isoformat()},
        "totals": {
            "my_prompts": n,
            "sessions": len(session_span),
            "projects": len(proj),
            "active_days": len(active),
            "claude_tool_calls": sum(tools.values()),
            "claude_output_tokens": out_tokens,
            "tool_calls_per_prompt": round(sum(tools.values()) / n, 1),
            "interrupts": interrupts,
            "images_pasted": images,
            "text_pastes": pastes,
            "tool_error_rate": round(tool_errors / tool_results, 3) if tool_results else None,
        },
        "time": {
            "hour_hist": hour,
            "weekday_hist_mon_first": wday,
            "busiest_hour": hour.index(max(hour)),
            "night_0_6_ratio": round(night / n, 3),
            "late_22_4_ratio": round(late / n, 3),
            "morning_5_10_ratio": round(morning / n, 3),
            "weekend_ratio": round((wday[5] + wday[6]) / n, 3),
            "busiest_day": {"date": busiest_day.isoformat(), "prompts": busiest_cnt},
            "longest_streak_days": best,
            "longest_focus_burst_hours": round(longest_burst[0], 1),
            "longest_focus_burst_date": longest_burst[1].strftime("%Y-%m-%d %a %H:%M"),
            "focus_bursts_over_3h": sum(1 for b in bursts if b[0] >= 3),
            "latest_night_prompt": fmt(latest_night, 80) if latest_night else None,
            "median_reply_seconds": round(statistics.median(resp_times)) if resp_times else None,
        },
        "talk": {
            "median_len": statistics.median(lens),
            "mean_len": round(statistics.mean(lens)),
            "longest_len": max(lens),
            "short_reply_ratio_le12": round(short / n, 3),
            "polite_ending_ratio": round(polite / n, 3),
            "banmal_ending_ratio": round(banmal / n, 3),
            "question_ratio": round(q / n, 3),
            "exclaim_ratio": round(ex / n, 3),
            "laugh_ratio": round(laugh / n, 3),
            "ellipsis_ratio": round(ell / n, 3),
            "emoji_ratio": round(emoji / n, 3),
            "category_per_100_prompts": per100,
            "top_short_messages": shorts.most_common(15),
            "top_words": words.most_common(40),
            "top_bigrams": bigr.most_common(20),
        },
        "claude_side": {
            "top_tools": tools.most_common(15),
            "mcp_servers": mcp.most_common(10),
            "skills_invoked": skills.most_common(12),
            "slash_commands": slash.most_common(15),
            "subagents": agents.most_common(8),
            "models": models.most_common(5),
            "git": dict(git),
        },
        "projects_top": proj.most_common(10),
        "languages_touched": langs.most_common(8),
        "insights_facets": {k: dict(v.most_common(8)) for k, v in facets.items()},
        "insights_summaries": summaries[:12],
        "insights_frictions": frictions[:8],
        "samples": {
            "first_ever": fmt(prompts[0]),
            "latest": [fmt(p) for p in prompts[-5:]],
            "longest_heads": [dict(fmt(p, 120), length=len(p[1])) for p in longest],
            "random": [fmt(p) for p in sample],
        },
    }
    path = a.out or os.path.join(os.path.expanduser("~/내캐릭터"), "stats.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(path)


if __name__ == "__main__":
    main()
