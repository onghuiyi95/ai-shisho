"""AI 师匠端到端冒烟测试：不依赖 Telegram，直接测 Shisho 生成管线。
覆盖：寒暄 / 困境深问 / 跨语言(日文) / 检索降级。
用法：venv python tools/smoke_test.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator.shisho import Shisho

CASES = [
    ("寒暄", "你好"),
    ("短回应", "还行"),
    ("困境深问", "我很迷茫，不知道该往哪走"),
    ("情绪", "我好孤独，没人懂我"),
    ("青年主题", "青年如何面对失败"),
    ("存在主义", "如果我明天不在了，你会对我说什么"),
    ("日文输入", "悩んでいます。どうすればいいですか"),
    ("具体困境", "工作和信仰怎么平衡"),
]

def main():
    s = Shisho()
    print(f"retriever ready={s.retriever.ready()}")
    ok = 0
    for label, q in CASES:
        t0 = time.time()
        try:
            ans = s.answer(q)
            dt = time.time() - t0
            head = ans[:60].replace("\n", " ")
            flag = "OK" if len(ans) > 20 else "SHORT"
            ok += 1 if flag == "OK" else 0
            print(f"[{flag}] {label:<8} ({dt:.1f}s) {head}")
        except Exception as e:
            print(f"[ERR] {label:<8} {repr(e)}")
    print(f"\n通过 {ok}/{len(CASES)}")

if __name__ == "__main__":
    main()
