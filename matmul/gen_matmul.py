#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


def parse_matrix_file(path: Path):
    raw = path.read_text(encoding="utf-8").splitlines()

    cleaned = []
    for line in raw:
        stripped = line.strip()
        if stripped.startswith("#"):
            cleaned.append("")
        else:
            cleaned.append(stripped)

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
    n = len(A)
    C = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = 0
            for k in range(n):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C


def gen_pml(A, B, P, n):
    assigns_A = "\n".join(
        f"    A[{i}*N + {kk}] = {A[i][kk]};"
        for i in range(n) for kk in range(n)
    )
    assigns_B = "\n".join(
        f"    B[{i}*N + {kk}] = {B[i][kk]};"
        for i in range(n) for kk in range(n)
    )

    return f"""#define N    {n}
#define P    {P}
#define STOP 0

typedef Col {{ byte v[N] }};

chan task[P] = [1] of {{ byte }};

chan result  = [P] of {{ byte, byte, Col }};

bit  done = 0;
byte k = 0;

inline print_matrix(M)
{{
    byte pi = 0;
    do
    :: (pi < N) ->
        byte pj = 0;
        do
        :: (pj < N) -> printf("%d ", M[pi*N + pj]); pj++
        :: (pj == N) -> break
        od;
        printf("\\n");
        pi++
    :: (pi == N) -> break
    od
}}

inline init_AB(A, B)
{{
{assigns_A}

{assigns_B}
}}

proctype Worker(byte id)
{{
    byte A[N*N];
    byte B[N*N];
    byte column_number, i, j, s;
    Col  col;

    init_AB(A, B);

    do
    :: task[id] ? column_number ->
        if
        :: (column_number == STOP) -> break
        :: else ->
            i = 0;
            do
            :: (i < N) ->
                s = 0;
                j = 0;
                do
                :: (j < N) ->
                    s = s + A[i*N + j] * B[j*N + (column_number - 1)];
                    j++
                :: (j == N) -> break
                od;
                col.v[i] = s;
                i++
            :: (i == N) -> break
            od;
            result ! id, column_number, col
        fi
    od
}}

init {{
    byte A[N*N];
    byte B[N*N];
    byte C[N*N];

    byte l;
    byte rid;
    byte rj;
    Col  col;

    init_AB(A, B);

    byte w = 0;
    do
    :: (w < P) -> run Worker(w); w++
    :: (w == P) -> break
    od;

    l = 1;
    do
    :: (l <= P) && (l <= N) -> task[l - 1] ! l; l++
    :: else -> break
    od;

    k = 0;
    byte i;
    do
    :: (k < N) ->
        result ? rid, rj, col;
        i = 0;
        do
        :: (i < N) -> C[i*N + (rj - 1)] = col.v[i]; i++
        :: (i == N) -> break
        od;
        k++;
        if
        :: (l <= N) -> task[rid] ! l; l++
        :: else     -> skip
        fi
    :: (k == N) -> break
    od;

    byte q = 0;
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

ltl safety_bounded   {{ [] (k <= N) }}

ltl done_after_all   {{ [] (done == 1 -> k == N) }}

ltl cols_stable      {{ [] (k == N -> [] (k == N)) }}

ltl liveness_done    {{ <> (done == 1) }}

ltl progress_collect {{ [] (k < N -> <> (k == N)) }}

ltl cols_then_done   {{ [] (k == N -> <> (done == 1)) }}
"""


def main():
    ap = argparse.ArgumentParser(description="Генерация matmul_custom.pml из matrix.txt")
    ap.add_argument("-i", "--input",  default="matrix.txt")
    ap.add_argument("-o", "--output", default="matmul_custom.pml")
    ap.add_argument("-p", "--workers", type=int, default=None)
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
