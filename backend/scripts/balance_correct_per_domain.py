"""Balance correct_option per domain so each domain's 30 questions include A, B, C, D."""
import json
from pathlib import Path
from collections import Counter

# Per domain: 30 questions -> 8 A, 8 B, 7 C, 7 D
TARGETS = ['A'] * 8 + ['B'] * 8 + ['C'] * 7 + ['D'] * 7  # 30 total
OPTS = {'A': 'option_a', 'B': 'option_b', 'C': 'option_c', 'D': 'option_d'}


def main():
    base = Path(__file__).resolve().parent.parent
    path = base / 'data' / 'domain_questions.json'
    data = json.loads(path.read_text(encoding='utf-8'))

    for domain in data.get('domains', []):
        questions = domain.get('questions', [])
        n = len(questions)
        if n == 0:
            continue
        # Target counts: as close to n/4 each as possible
        q_per = n // 4
        remainder = n % 4
        targets = (
            ['A'] * (q_per + (1 if remainder >= 1 else 0)) +
            ['B'] * (q_per + (1 if remainder >= 2 else 0)) +
            ['C'] * (q_per + (1 if remainder >= 3 else 0)) +
            ['D'] * q_per
        )
        # Pad or trim to exactly n
        while len(targets) < n:
            targets.append(targets[len(targets) % 4])
        targets = targets[:n]

        for i, q in enumerate(questions):
            current = q.get('correct_option', 'A')
            target = targets[i]
            if current == target:
                continue
            cur_key = OPTS[current]
            tgt_key = OPTS[target]
            q[cur_key], q[tgt_key] = q[tgt_key], q[cur_key]
            q['correct_option'] = target

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    print('Per-domain correct_option distribution (sample):')
    for domain in data['domains'][:5]:
        c = Counter(q['correct_option'] for q in domain['questions'])
        print(f"  {domain['code']}: A={c.get('A',0)} B={c.get('B',0)} C={c.get('C',0)} D={c.get('D',0)}")
    print('...')
    last = data['domains'][-1]
    c = Counter(q['correct_option'] for q in last['questions'])
    print(f"  {last['code']}: A={c.get('A',0)} B={c.get('B',0)} C={c.get('C',0)} D={c.get('D',0)}")


if __name__ == '__main__':
    main()
