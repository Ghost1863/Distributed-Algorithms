#!/usr/bin/env python3
"""
Генератор matmul_custom.pml из matrix.txt.

Использование:
    python3 gen_matmul.py                    # P берётся равным N
    python3 gen_matmul.py -p 4               # P = 4
    python3 gen_matmul.py -i my.txt -o out.pml -p 2

Формат matrix.txt:
    - строки матрицы A (числа через пробел/таб),
    - одна пустая строка-разделитель,
    - строки матрицы B,
    - комментарии (строки с '#') и пустые строки в начале/конце игнорируются.

Размер N определяется автоматически как число строк A.
Обе матрицы должны быть квадратными N x N.
"""

import argparse
import sys
from pathlib import Path


def parse_matrix_file(path: Path):
    """Возвращает (A, B) — два списка списков int. Бросает ValueError при ошибке."""
    raw = path.read_text(encoding="utf-8").splitlines()

    # Убираем комментарии в каждой строке
    cleaned = []
    for line in raw:
        stripped = line.strip()
        if stripped.startswith("#"):
            cleaned.append("")
        else:
            cleaned.append(stripped)

    # Разбиваем по группам непустых строк, разделённых пустыми
    blocks = []
    current = []
    for line in cleaned:
        if line:
            current.append(line)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    if len(blocks) != 2:
        raise ValueError(
            f"Ожидалось ровно 2 блока (A и B), найдено {len(blocks)}. "
            f"Разделяй матрицы пустой строкой."
        )

    def parse_block(block, name):
        rows = []
        for ln in block:
            try:
                rows.append([int(x) for x in ln.split()])
            except ValueError as e:
                raise ValueError(f"Матрица {name}: некорректное число в строке '{ln}'") from e
        n = len(rows)
        for i, row in enumerate(rows):
            if len(row) != n:
                raise ValueError(
                    f"Матрица {name}: строка {i + 1} имеет {len(row)} элементов, "
                    f"ожидалось {n} (квадратная матрица)."
                )
        return rows

    A = parse_block(blocks[0], "A")
    B = parse_block(blocks[1], "B")

    if len(A) != len(B):
        raise ValueError(f"Размеры A ({len(A)}x{len(A)}) и B ({len(B)}x{len(B)}) различаются.")

    return A, B


def matmul(A, B):
    """Эталонное произведение C = A * B (для печати в комментарий)."""
    n = len(A)
    C = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = 0
            for k in range(n):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C


def fmt_matrix_comment(M, indent="   "):
    """Печать матрицы в комментарий .pml."""
    width = max(len(str(v)) for row in M for v in row)
    return "\n".join(indent + " ".join(str(v).rjust(width) for v in row) for row in M)


def gen_pml(A, B, P, n):
    """Генерирует текст matmul_custom.pml."""
    C = matmul(A, B)

    # Строки присваиваний для inline init_AB
    assigns_A = "\n".join(
        f"    A[{i}*N + {k}] = {A[i][k]};"
        for i in range(n) for k in range(n)
    )
    assigns_B = "\n".join(
        f"    B[{i}*N + {k}] = {B[i][k]};"
        for i in range(n) for k in range(n)
    )

    return f"""/*
 * Эталонный результат C = A * B (для проверки):
{fmt_matrix_comment(C, indent=' *   ')}
 */

#define N    {n}      /* размер матриц N x N           */
#define P    {P}      /* число работников              */
#define STOP 0      /* "конец работы" в канале task   */

typedef Col {{ byte v[N] }};

chan task[P] = [1] of {{ byte }};
chan result  = [P] of {{ byte, byte, Col }};

bit  done = 0;
byte ready_cols = 0;

inline print_matrix(M)
{{
    pi = 0;
    do
    :: (pi < N) ->
        pj = 0;
        do
        :: (pj < N) -> printf("%d ", M[pi*N + pj]); pj++
        :: (pj == N) -> break
        od;
        printf("\\n");
        pi++
    :: (pi == N) -> break
    od
}}

/* Значения матриц A и B вшиты из matrix.txt. Каждый процесс
   инициализирует СВОИ локальные копии — никакой shared memory. */
inline init_AB(A, B)
{{
{assigns_A}

{assigns_B}
}}

proctype Worker(byte id)
{{
    byte A[N*N];
    byte B[N*N];
    byte j, i, k, s;
    Col  col;

    init_AB(A, B);

    do
    :: task[id] ? j ->
        if
        :: (j == STOP) -> break
        :: else ->
            i = 0;
            do
            :: (i < N) ->
                s = 0;
                k = 0;
                do
                :: (k < N) ->
                    s = s + A[i*N + k] * B[k*N + (j - 1)];
                    k++
                :: (k == N) -> break
                od;
                col.v[i] = s;
                i++
            :: (i == N) -> break
            od;
            result ! id, j, col
        fi
    od
}}

init {{
    byte A[N*N];
    byte B[N*N];
    byte C[N*N];

    byte l, k, rid, rj;
    Col  col;
    byte pi, pj, w, i, q;

    init_AB(A, B);

    atomic {{
        w = 0;
        do
        :: (w < P) -> run Worker(w); w++
        :: (w == P) -> break
        od
    }}

    /* Первичная раздача задач */
    l = 1;
    do
    :: (l <= P) && (l <= N) -> task[l - 1] ! l; l++
    :: else -> break
    od;

    /* Приём результатов и довыдача */
    k = 0;
    do
    :: (k < N) ->
        result ? rid, rj, col;
        i = 0;
        do
        :: (i < N) -> C[i*N + (rj - 1)] = col.v[i]; i++
        :: (i == N) -> break
        od;
        ready_cols++;
        k++;
        if
        :: (l <= N) -> task[rid] ! l; l++
        :: else     -> skip
        fi
    :: (k == N) -> break
    od;

    /* Рассылка STOP всем */
    q = 0;
    do
    :: (q < P) -> task[q] ! STOP; q++
    :: (q == P) -> break
    od;

    printf("Matrix A:\\n");
    print_matrix(A);
    printf("Matrix B:\\n");
    print_matrix(B);
    printf("Result matrix C = A * B:\\n");
    print_matrix(C);

    done = 1
}}

ltl safety_bounded   {{ [] (ready_cols <= N) }}
ltl liveness_done    {{ <> (done == 1) }}
ltl done_after_all   {{ [] (done == 1 -> ready_cols == N) }}
ltl progress_collect {{ [] (ready_cols < N -> <> (ready_cols == N)) }}
"""


def main():
    ap = argparse.ArgumentParser(description="Генерация matmul_custom.pml из matrix.txt")
    ap.add_argument("-i", "--input",  default="matrix.txt",
                    help="Файл с матрицами (по умолчанию matrix.txt)")
    ap.add_argument("-o", "--output", default="matmul_custom.pml",
                    help="Имя выходного .pml (по умолчанию matmul_custom.pml)")
    ap.add_argument("-p", "--workers", type=int, default=None,
                    help="Число работников P (по умолчанию равно N)")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"Не найден файл с матрицами: {in_path}")

    try:
        A, B = parse_matrix_file(in_path)
    except ValueError as e:
        sys.exit(f"Ошибка разбора {in_path}: {e}")

    n = len(A)
    P = args.workers if args.workers is not None else n
    if P < 1:
        sys.exit(f"P должно быть >= 1, дано {P}")
    if n < 1:
        sys.exit(f"N должно быть >= 1, в файле {n}")
    if P > 250 or n > 250:
        sys.exit(f"N={n}, P={P} слишком велики — упрутся в byte (0..255).")

    text = gen_pml(A, B, P, n)
    Path(args.output).write_text(text, encoding="utf-8")
    print(f"OK  → {args.output}   (N={n}, P={P})")


if __name__ == "__main__":
    main()
