import json
import re
import sys
from collections import Counter

IN_PATH = "pipeline/output/regulations_with_files.json"
OUT_PATH = "pipeline/output/regulations_final_clean.json"

HANGUL = r'가-힣'
MIN_JOINED_COUNT = 15
MIN_JOINED_RATIO = 0.9

# Bigrams whose left character is a common standalone particle/ending are
# unreliable regardless of frequency: particles attach productively to almost
# any preceding word, so they coincidentally form real words with whatever
# follows (e.g. "위원장이 사고가" -> "위원장이사고가" via "이사", "문서에 서식"
# -> "문서에서식" via "에서"). Merging these risks corrupting real word
# boundaries, so bigrams starting with one of these characters are excluded
# wholesale rather than allow-listed one at a time.
PARTICLE_CHARS = set('이가을를은는의에와과도만며고지자나다라요께아어서로')

# Standalone modifiers/demonstratives ("본교" = this school, "동시행령" reads
# as if it starts with "동시"=simultaneous) are productive in the same way:
# they attach to almost any following noun, so they also produce misleading
# high-frequency junction bigrams.
MODIFIER_CHARS = set('본동각전총매신구현타그저')

# A few additional bigrams confirmed by manual review to cause bad merges for
# reasons the particle-prefix rule above doesn't catch (the left character
# isn't a particle itself, but is the tail of a different common word, or a
# standalone demonstrative):
BLOCKLIST = {
    '학교',  # "대학 교원업적평가" -> "대학교원업적평가" (학 = end of 대학, not part of 학교)
    '본교',  # "본 교육원" -> "본교육원" (본 = standalone "this", not part of 본교)
}


def collect_stats(data):
    joined_freq = Counter()
    split_freq = Counter()

    for r in data:
        for a in r.get('articles', []):
            body = a['body']
            for run in re.findall(f'[{HANGUL}]+', body):
                for i in range(len(run) - 1):
                    joined_freq[run[i:i + 2]] += 1
            for m in re.finditer(f'[{HANGUL}]+ [{HANGUL}]+', body):
                left, right = m.group(0).split(' ')
                split_freq[left[-1] + right[0]] += 1

    return joined_freq, split_freq


def find_candidates(joined_freq, split_freq):
    candidates = set()
    for bigram, scount in split_freq.items():
        if bigram in BLOCKLIST or bigram[0] in PARTICLE_CHARS or bigram[0] in MODIFIER_CHARS:
            continue
        jcount = joined_freq.get(bigram, 0)
        if jcount >= MIN_JOINED_COUNT and jcount / (jcount + scount) >= MIN_JOINED_RATIO:
            candidates.add(bigram)
    return candidates


def apply_fix(body, candidates, counters):
    def repl(m):
        left, right = m.group(0).split(' ')
        bigram = left[-1] + right[0]
        if bigram in candidates:
            counters[bigram] += 1
            return left + right
        return m.group(0)

    return re.sub(f'[{HANGUL}]+ [{HANGUL}]+', repl, body)


def main():
    with open(IN_PATH, encoding='utf-8') as f:
        data = json.load(f)

    joined_freq, split_freq = collect_stats(data)
    candidates = find_candidates(joined_freq, split_freq)

    counters = Counter()
    total_fixed = 0
    for r in data:
        for a in r.get('articles', []):
            body = a['body']
            for _ in range(4):  # fixed-point: chained single-syllable gaps need re-scanning
                new_body = apply_fix(body, candidates, counters)
                if new_body == body:
                    break
                body = new_body
            if body != a['body']:
                total_fixed += 1
                a['body'] = body

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'후보 바이그램 {len(candidates)}개, 수정된 조문 {total_fixed}건 -> {OUT_PATH}', file=sys.stderr)
    for bigram, n in counters.most_common(20):
        print(f'  {bigram}: {n}건 수정', file=sys.stderr)


if __name__ == '__main__':
    main()
