# QMT 策略文件体检器（在电脑上运行，不要放进QMT）
# 用法: python QMT代码体检器.py 文件1.py 文件2.py ...  （不带参数=体检整个目录）
# 体检项: 1) 无BOM  2) 真GBK可解码  3) 首行#encoding:gbk  4) Python语法可编译
#         5) 有init/handlebar  6) 无tabs混用  7) 无全角空格缩进
import sys, os, ast

def check(path):
    problems = []
    warns = []
    b = open(path, 'rb').read()
    if any(x > 127 for x in b):
        warns.append('含非ASCII字符(中文)。QMT编辑器可能显示乱码, 建议源码纯ASCII')
    if b.startswith(b'\xef\xbb\xbf'):
        problems.append('UTF-8 BOM头(QMT读会乱码)')
    try:
        b.decode('gbk')
    except Exception:
        problems.append('存在GBK以外的字节(乱码根源)')
    if not b.startswith(b'#encoding:gbk'):
        problems.append('首行不是 #encoding:gbk')
    txt = None
    try:
        txt = b.decode('gbk')
    except Exception:
        pass
    if txt is not None:
        try:
            ast.parse(txt)
        except SyntaxError as e:
            problems.append(f'语法错误 line{e.lineno}: {e.msg}')
        has_init = 'def init(' in txt
        has_bar = 'def handlebar(' in txt or 'def init(' in txt and 'PTrade' in path
        if 'def handlebar(' not in txt and 'def initialize(' not in txt:
            problems.append('缺少 handlebar/initialize 入口')
        for i, ln in enumerate(txt.split('\n'), 1):
            st = ln[:len(ln) - len(ln.lstrip())]
            if '\t' in st:
                problems.append(f'line{i}: 缩进用了Tab'); break
            if '\u3000' in st:
                problems.append(f'line{i}: 缩进用了全角空格'); break
    return problems, warns

def main():
    targets = sys.argv[1:]
    files = []
    if not targets:
        d = os.path.dirname(os.path.abspath(__file__))
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.py') and f != os.path.basename(__file__)]
    else:
        files = targets
    bad = 0
    for f in files:
        if not os.path.isfile(f):
            continue
        ps, ws = check(f)
        if ps:
            mark = 'FAIL'; bad += 1
        elif ws:
            mark = 'WARN'
        else:
            mark = 'PASS'
        print(f'[{mark}] {os.path.basename(f)}')
        for p in ps:
            print(f'      - {p}')
        for w in ws:
            print(f'      [警告] {w}')
    print(f'\n结论: {len(files) - bad} 通过 / {bad} 不通过')
    sys.exit(1 if bad else 0)

main()
