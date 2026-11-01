#!/usr/bin/env python3
"""减脂精算教练 —— 确定性计算工具(纯标准库)。

所有热量 / 宏量 / 配餐数字都走这里,不要心算。

用法:
  # 1) 算消耗与每日目标(训练日 / 休息日分开)
  python calc.py targets --sex m --age 30 --height 175 --weight 72 \
      --lift-days 3 --cardio-days 5 --cardio-min 30 --incline 15 --speed 4.5 \
      --deficit 0.25
  #   或者直接指定一周平均摄入:  --avg-kcal 1600

  # 2) 算一份菜单 / 一天吃了多少,并和目标比
  python calc.py menu "鸡胸生:400,鸡蛋:100,西兰花:400,米饭熟:300,油:12" \
      --weight 72 --day train
  #   未知食物可写成  名字:克数:kcal/P/F/C(每100g),例如  炸鸡块:200:280/15/18/14

  # 3) 体重趋势(读日志,看两周平均)
  python calc.py trend --log ~/.cut-coach/weight-log.md

  # 4) 列出食物库
  python calc.py foods
"""
import argparse
import io
import sys

# 每 100g 可食部:kcal, 蛋白, 脂肪, 碳水。肉类为【生重】;"生米"按生米,"米饭熟"按熟饭。
# 来源:USDA FoodData Central / 中国食物成分表常用值;调料按常见包装标签估。
FOODS = {
    # 蛋白质
    "鸡胸生": (120, 22.5, 2.6, 0), "鸡腿丁生": (121, 19.7, 4.1, 0),
    "瘦牛肉生": (106, 20.2, 2.3, 1.2), "瘦猪肉生": (143, 20.3, 6.2, 1.5),
    "虾仁生": (85, 18.6, 0.8, 0), "巴沙鱼生": (90, 15.0, 3.0, 0),
    "兔肉生": (102, 19.7, 2.2, 0.9), "牛腱子生": (120, 21.0, 3.0, 0), "猪里脊生": (120, 20.9, 3.5, 0), "北豆腐": (98, 12.2, 4.8, 1.5),
    "鸡蛋": (143, 12.6, 9.5, 0.7),  # 1 个蛋约 50g 可食
    "全脂奶": (65, 3.2, 3.6, 4.8), "脱脂奶": (35, 3.4, 0.2, 5.0), "低脂奶": (45, 3.2, 1.3, 5.0),
    "无糖酸奶": (70, 3.5, 3.0, 7.0), "乳清蛋白粉": (383, 80, 3, 7),  # 以包装为准
    # 碳水
    "米饭熟": (116, 2.6, 0.3, 25.9), "生米": (346, 7.4, 0.8, 77.0), "土豆生": (77, 2.0, 0.1, 17.5), "红薯生": (86, 1.6, 0.1, 20.1),
    "燕麦": (380, 13, 7, 66), "面条熟": (110, 3.5, 0.6, 23), "馒头": (223, 7.0, 1.1, 47),
    "香蕉": (93, 1.1, 0.3, 23), "苹果": (52, 0.3, 0.2, 13.8),
    "熟豌豆": (84, 5.4, 0.2, 15.6),
    # 蔬菜(生重)
    "青菜": (25, 2.8, 0.5, 4.0), "菜心": (25, 2.8, 0.5, 4.0), "上海青": (15, 1.5, 0.3, 2.4),
    "包菜": (25, 1.3, 0.1, 5.8), "番茄": (18, 0.9, 0.2, 3.9), "青椒": (22, 1.0, 0.2, 5.4),
    "花菜": (25, 1.9, 0.3, 5.0), "西兰花": (34, 2.8, 0.4, 6.6), "黄瓜": (15, 0.7, 0.1, 3.6),
    # 油与调料
    "油": (900, 0, 100, 0), "生抽": (60, 5.6, 0.1, 10), "蚝油": (115, 1.4, 0.3, 26),
    "淀粉": (350, 0.2, 0.1, 85), "豆瓣酱": (180, 13.6, 6.8, 15.6), "糖": (400, 0, 0, 100),
}

ALIASES = {"大米": "生米", "里脊": "猪里脊生", "鸡胸": "鸡胸生", "鸡腿丁": "鸡腿丁生", "牛肉": "瘦牛肉生", "米饭": "米饭熟",
           "土豆": "土豆生", "蛋": "鸡蛋", "蛋白粉": "乳清蛋白粉", "牛奶": "全脂奶"}


def bmr_mifflin(sex, age, h, w):
    return 10 * w + 6.25 * h - 5 * age + (5 if sex == "m" else -161)


def incline_walk_net_kcal(w, minutes, incline_pct, speed_kmh):
    """ACSM 步行公式:VO2 = 3.5 + 0.1*v + 1.8*v*坡度 (v: m/min)。返回净消耗。"""
    v = speed_kmh * 1000 / 60
    vo2 = 3.5 + 0.1 * v + 1.8 * v * incline_pct / 100
    met = vo2 / 3.5
    return (met - 1) * w * minutes / 60


def macros(weight, kcal, p_per_kg=2.3, f_per_kg=0.75):
    p = round(p_per_kg * weight)
    f = max(round(f_per_kg * weight), 40)
    c = round((kcal - p * 4 - f * 9) / 4)
    return p, f, c


def cmd_targets(a):
    bmr = bmr_mifflin(a.sex, a.age, a.height, a.weight)
    base = bmr * 1.2  # 久坐基础(含 BMR + 进食产热 + 极少活动)
    steps = a.steps_kcal
    cardio = incline_walk_net_kcal(a.weight, a.cardio_min, a.incline, a.speed) if a.cardio_days else 0
    lift = a.lift_kcal
    # 简化:训练日 = 基础 + 步行 + 力量 + 有氧(若当天有) ;按一周平均分摊有氧
    cardio_avg = cardio * a.cardio_days / 7
    rest_tdee = base + steps + cardio_avg
    train_tdee = rest_tdee + lift
    week_avg = (a.lift_days * train_tdee + (7 - a.lift_days) * rest_tdee) / 7

    if a.avg_kcal:
        avg_in = a.avg_kcal
    else:
        avg_in = week_avg * (1 - a.deficit)
    # 训练日比休息日多吃 ≈ 训练消耗(只加碳水)
    rest_in = avg_in - a.lift_days * lift / 7
    train_in = rest_in + lift

    pr, fr, cr = macros(a.weight, rest_in)
    pt, ft, ct = macros(a.weight, train_in)
    deficit = week_avg - avg_in
    print(f"BMR(Mifflin)            : {bmr:.0f} kcal")
    print(f"有氧单次净消耗           : {cardio:.0f} kcal  ({a.cardio_min}min 坡度{a.incline}% 速度{a.speed})")
    print(f"消耗估算  休息日 / 训练日 : {rest_tdee:.0f} / {train_tdee:.0f} kcal   周均 {week_avg:.0f}")
    print(f"摄入目标  休息日 / 训练日 : {rest_in:.0f} / {train_in:.0f} kcal   周均 {avg_in:.0f}")
    print(f"  休息日 P/F/C = {pr}/{fr}/{cr} g")
    print(f"  训练日 P/F/C = {pt}/{ft}/{ct} g")
    print(f"日均缺口 {deficit:.0f} kcal ≈ 预计 {deficit*7/7700:.2f} kg/周 "
          f"({deficit*7/7700/a.weight*100:.2f}% 体重/周)")
    warns = ["消耗是公式估计(误差约 ±200 kcal),用 14 天晨重 + 摄入记录校准。"]
    rate = deficit * 7 / 7700 / a.weight
    if rate > 0.01:
        warns.append("预计掉速 >1% 体重/周:偏激进,体脂较低者掉肌肉风险上升,建议只做 3–4 周短块并盯力量。")
    if rest_in < bmr:
        warns.append(f"休息日摄入低于 BMR({bmr:.0f})。可以短期,但不要长期。")
    if cr < 50:
        warns.append("休息日碳水 <50g:训练表现和情绪大概率受影响,考虑减小缺口。")
    for w in warns:
        print("⚠ " + w)


def parse_items(s):
    items = []
    for part in s.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        name, grams = bits[0].strip(), float(bits[1])
        if len(bits) >= 3:
            vals = tuple(float(x) for x in bits[2].split("/"))
            items.append((name, grams, vals))
            continue
        key = ALIASES.get(name, name)
        if key not in FOODS:
            sys.exit(f"未知食物「{name}」。用 名字:克数:kcal/P/F/C 自定义,或 `calc.py foods` 查看库。")
        items.append((key, grams, FOODS[key]))
    return items


def cmd_menu(a):
    items = parse_items(a.items)
    tot = [0.0] * 4
    print(f"{'食物':<10}{'克':>6}{'kcal':>7}{'P':>7}{'F':>7}{'C':>7}")
    for name, g, v in items:
        row = [v[i] * g / 100 for i in range(4)]
        tot = [t + r for t, r in zip(tot, row)]
        print(f"{name:<10}{g:>6.0f}{row[0]:>7.0f}{row[1]:>7.1f}{row[2]:>7.1f}{row[3]:>7.1f}")
    print(f"{'合计':<10}{'':>6}{tot[0]:>7.0f}{tot[1]:>7.1f}{tot[2]:>7.1f}{tot[3]:>7.1f}")
    if a.weight and a.day:
        # 目标按 g/kg:P 2.3 / F 0.75 / C 训练日 2.5 休息日 1.85
        cpk = 2.5 if a.day == "train" else 1.85
        tgt = (round(2.3 * a.weight), max(round(0.75 * a.weight), 40), round(cpk * a.weight))
        tk = tgt[0] * 4 + tgt[1] * 9 + tgt[2] * 4
        print(f"{'目标':<10}{'':>6}{tk:>7.0f}{tgt[0]:>7.0f}{tgt[1]:>7.0f}{tgt[2]:>7.0f}")
        print(f"{'还差':<10}{'':>6}{tk-tot[0]:>7.0f}{tgt[0]-tot[1]:>7.1f}{tgt[1]-tot[2]:>7.1f}{tgt[2]-tot[3]:>7.1f}")


def cmd_trend(a):
    """读体重日志:| 日期 | 体重kg | 热量 | 备注 |。备注含"排除"的行不计入。"""
    import datetime as dt
    rows = []
    for line in io.open(a.log, encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        try:
            d = dt.date.fromisoformat(cells[0])
            w = float(cells[1])
        except ValueError:
            continue
        note = cells[3] if len(cells) > 3 else ""
        if "排除" in note:
            continue
        rows.append((d, w))
    rows.sort()
    if len(rows) < 7:
        print(f"只有 {len(rows)} 条有效记录,至少攒满 14 天再判断趋势。")
        return
    last = rows[-1][0]
    def avg(days_from, days_to):
        xs = [w for d, w in rows if days_from <= (last - d).days < days_to]
        return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)
    w1, n1 = avg(0, 7)
    w2, n2 = avg(7, 14)
    w3, n3 = avg(14, 21)
    print(f"最近 7 天均重 {w1:.2f} kg ({n1} 条)")
    if not w2:
        print("还不满两周,先继续记录。")
        return
    print(f"前 7 天均重 {w2:.2f} kg ({n2} 条)")
    print(f"单周变化 {w1 - w2:+.2f} kg ({(w1 - w2) / w2 * 100:+.2f}%,只作参考,不据此调整)")
    if not w3:
        print("还不满三周数据,算不出两周平均,先继续记录。")
        return
    # 规则看两周平均:最近 7 天均重 对比 14–21 天前的均重,再除以 2
    print(f"再往前 7 天均重 {w3:.2f} kg ({n3} 条)")
    rate = (w3 - w1) / 2
    pct = rate / w3 * 100
    lo, hi = 0.005 * w3, 0.01 * w3
    print(f"两周平均每周变化 {-rate:+.2f} kg ({-pct:+.2f}% 体重/周;合适是每周掉 0.5–1% = {lo:.2f}–{hi:.2f} kg)")
    if pct < 0.5:
        print("建议:掉得不到 0.5% → 每天碳水 -25g(约 33g 生米)。肌酸刚开始、盐多、生病等会干扰,先排除再动。")
    elif pct > 1:
        print("建议:掉得超过 1% → 每天碳水 +25g。")
    else:
        print("速度合适,不用调。")


def cmd_foods(_):
    for k, v in FOODS.items():
        print(f"{k:<8} kcal {v[0]:>4}  P {v[1]:>5}  F {v[2]:>5}  C {v[3]:>5}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("targets")
    t.add_argument("--sex", choices=["m", "f"], required=True)
    t.add_argument("--age", type=int, required=True)
    t.add_argument("--height", type=float, required=True)
    t.add_argument("--weight", type=float, required=True, help="晨起空腹 kg")
    t.add_argument("--lift-days", type=int, default=3)
    t.add_argument("--lift-kcal", type=float, default=150, help="单次力量训练净消耗,默认 150")
    t.add_argument("--steps-kcal", type=float, default=150, help="日常走路净消耗,默认 150(约 6000 步)")
    t.add_argument("--cardio-days", type=int, default=0)
    t.add_argument("--cardio-min", type=float, default=30)
    t.add_argument("--incline", type=float, default=15)
    t.add_argument("--speed", type=float, default=4.5)
    t.add_argument("--deficit", type=float, default=0.22, help="热量缺口比例,默认 0.22")
    t.add_argument("--avg-kcal", type=float, help="直接指定周均摄入,覆盖 --deficit")
    t.set_defaults(func=cmd_targets)

    m = sub.add_parser("menu")
    m.add_argument("items")
    m.add_argument("--weight", type=float)
    m.add_argument("--day", choices=["train", "rest"])
    m.set_defaults(func=cmd_menu)

    tr = sub.add_parser("trend")
    tr.add_argument("--log", required=True, help="体重日志路径,如 ~/.cut-coach/weight-log.md")
    tr.set_defaults(func=cmd_trend)

    f = sub.add_parser("foods")
    f.set_defaults(func=cmd_foods)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
