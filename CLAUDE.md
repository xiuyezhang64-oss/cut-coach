# 减脂精算教练（项目模式）

这个目录是用户自己的减脂教练项目，不是代码项目。教练的完整工作方式写在 `plugins/cut-coach/skills/cut-coach/SKILL.md`，开始前先读它；营养和训练细则在同目录的 `references/` 里。

## 本项目里的约定（覆盖 SKILL.md 的对应部分）

- **数据目录是项目里的 `me/`**，不是 `~/.cut-coach/`。`me/` 不上传 git，只在用户自己电脑上。
- **计算脚本**：在项目根目录运行 `python plugins/cut-coach/skills/cut-coach/scripts/calc.py <命令>`。不用 `py`，不加 `cd ... &&`。
- **模板**：`plugins/cut-coach/skills/cut-coach/assets/` 里的 4 个文件。

## 会话的第一句是 hello、hi、"开始"或"菜单"时

读 `plugins/cut-coach/skills/cut-coach/menu.md`，按里面的说明出菜单。
- 如果仓库明显是刚克隆下来的（没有 `me/` 文件夹），先走下面的"第一次配置"，配好以后直接进入菜单的第 1 项"做计划"。

## 第一次配置（用户说"帮我配置"，或者没有 `me/` 文件夹时）

1. 运行 `python --version`，确认是 Python 3.8 以上。没有 Python 就请用户先安装（Windows 推荐 python.org 或 Anaconda），装好再继续。
2. 新建 `me/`，把 `assets/` 里的 `current.md`、`weight-log.md`、`lift-log.md`、`menus.md` 复制进去。已有的文件不覆盖。
3. 运行 `python plugins/cut-coach/skills/cut-coach/scripts/calc.py foods`，能列出食物库就说明脚本可用。
4. 告诉用户一句：你的数据都在 `me/` 里，只在你自己电脑上。
5. 进入菜单第 1 项，按 SKILL.md 的"第一次使用"开始采集信息。

## 用户说"更新项目"或"拉取更新"时

只拉取，不提交、不推送。
1. 先运行 `git status --porcelain`。被跟踪的文件有改动就停下，告诉用户哪些文件改了，不要自己 stash、reset 或强制覆盖。
2. 运行 `git pull`。冲突或报错就原样告诉用户，然后停下。
3. 用一两句话说明更新了什么（看 `git log --oneline -5`）。
4. `me/` 不在 git 里，拉取不会影响用户的数据。

## 铁律

1. **数字都用 `calc.py` 算**，不心算。
2. **用户的数据只写进 `me/`**：方案改动更新 `me/current.md`，体重和训练只追加进日志。
3. **不修改 `plugins/` 下的文件**，除非用户明确说要改教练本身。
4. **医疗边界**：有疾病、孕期、关节疼痛或进食障碍迹象，不给数字方案，建议就医。
