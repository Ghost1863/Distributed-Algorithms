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
    """Генерирует текст matmul_custom.pml — структурно повторяет matmul.pml,
       но с матрицами, вшитыми из matrix.txt вместо формульной инициализации."""
    C = matmul(A, B)

    # Строки присваиваний для inline init_AB
    assigns_A = "\n".join(
        f"    A[{i}*N + {kk}] = {A[i][kk]};"
        for i in range(n) for kk in range(n)
    )
    assigns_B = "\n".join(
        f"    B[{i}*N + {kk}] = {B[i][kk]};"
        for i in range(n) for kk in range(n)
    )

    return f"""/*
 * АВТОСГЕНЕРИРОВАННЫЙ файл (gen_matmul.py).
 * Структура совпадает с matmul.pml; отличается только тело inline init_AB —
 * матрицы A и B вшиты из matrix.txt.
 *
 * Эталонный результат C = A * B (для проверки):
{fmt_matrix_comment(C, indent=' *   ')}
 */

#define N    {n}      /* размер матриц N x N            */
#define P    {P}     /* число работников  */
#define STOP 0      /* "конец работы" в канале task   */

/* Тип "столбец" — массив длины N в одном сообщении */
typedef Col {{ byte v[N] }};

/* P адресных каналов "менеджер -> работник i".
   Буфер 1 достаточен: в любой момент у работника не более одной
   назначенной, но ещё не прочитанной задачи. */
chan task[P] = [1] of {{ byte }};

/* Общий канал "работник -> менеджер": (worker_id, j, column).
   Буфер P достаточен: в любой момент в полёте не более P результатов
   (по одному от каждого работника), потому что новый task ему пошлют
   только после приёма его result. */
chan result  = [P] of {{ byte, byte, Col }};

/* Глобальные observable-переменные (только для LTL!).
   Пишет в них исключительно менеджер; работники их не трогают.
   Никакой разделяемой памяти для алгоритмических данных нет. */
bit  done = 0;
byte k = 0;          /* число принятых менеджером столбцов-результатов */

/* ---- Печать матрицы N x N (inline-макро) ---- */
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

/* ---- Локальная инициализация матриц A, B ---- */
/* Значения вшиты из matrix.txt. Каждый процесс инициализирует СВОИ
   локальные копии — никакой разделяемой памяти. */
inline init_AB(A, B)
{{
{assigns_A}

{assigns_B}
}}

/* ====================================================================
 *                          Работник P_i
 * ==================================================================== */
proctype Worker(byte id)
{{
    /* СВОИ копии A и B — никакой shared memory */
    byte A[N*N];
    byte B[N*N];
    byte column_number, i, j, s;
    Col  col;

    init_AB(A, B);

    /* Цикл "получить задачу — выполнить — вернуть результат" */
    do
    :: task[id] ? column_number ->
        if
        :: (column_number == STOP) -> break                 /* состояние 2: конец */
        :: else ->                              /* column_number ∈ {{1..N}}: задача */
            /* col[i] = sum_k A[i,k] * B[k, column_number-1]   (column_number 1-индексное) */
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

/* ====================================================================
 *                          Менеджер P_0 (init)
 * ==================================================================== */
init {{
    /* Локальные копии A и B — нужны только для печати (нет shared) */
    byte A[N*N];
    byte B[N*N];
    byte C[N*N];

    /* Переменные алгоритма (как в книге) */
    byte l;        /* следующий назначаемый номер столбца, 1..N      */
    byte rid;      /* id работника, приславшего результат            */
    byte rj;       /* номер столбца, который он считал               */
    Col  col;

    init_AB(A, B);

    /* Запуск P работников */
    atomic {{
        byte w = 0;
        do
        :: (w < P) -> run Worker(w); w++
        :: (w == P) -> break
        od
    }}

    /* ---- Состояние 0 -> 0: первичная раздача задач ----
       Посылаем работникам по очереди номера столбцов 1..min(P, N). */
    l = 1;
    do
    :: (l <= P) && (l <= N) -> task[l - 1] ! l; l++
    :: else -> break
    od;
    /* теперь l = min(P, N) + 1 */

    /* ---- Состояния 1 -> 2 -> 1: приём результатов и довыдача задач ----
       Принимаем ровно N результатов; после каждого — выдаём новую
       задачу тому же работнику, если ещё есть, иначе пропускаем. */
    k = 0;
    byte i;
    do
    :: (k < N) ->
        result ? rid, rj, col;
        /* Раскладываем столбец col в (rj-1)-й столбец C */
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

    /* ---- Состояние 3 -> 3: рассылка сигнала окончания работы ----
       STOP отправляется ВСЕМ P работникам, включая тех, кто никогда
       не получал реальной задачи (случай P > N). */
    byte q = 0;
    do
    :: (q < P) -> task[q] ! STOP; q++
    :: (q == P) -> break
    od;

    /* ---- Печать A, B, C ---- */
    printf("Matrix A:\\n");
    print_matrix(A);
    printf("Matrix B:\\n");
    print_matrix(B);
    printf("Result matrix C = A * B:\\n");
    print_matrix(C);

    done = 1
}}

/* =====================================================================
 *                  СВОЙСТВА АЛГОРИТМА НА ЯЗЫКЕ LTL
 *
 * Используемые наблюдаемые переменные:
 *   k    — число принятых менеджером столбцов-результатов (0..N)
 *   done — 1 ровно после того, как все столбцы собраны и
 *          STOP разослан всем работникам
 *
 * --- БЕЗОПАСНОСТЬ (safety): «плохого никогда не случится» ---
 *
 * G ¬(ready_cols > N): счётчик результатов никогда не переполняется.
 * Менеджер ждёт ровно N ответов → ready_cols ∈ {{0..N}} всегда.
 */
ltl safety_bounded   {{ [] (k <= N) }}

/* G(done=1 → k=N): флаг завершения выставляется ТОЛЬКО после
 * того, как все N столбцов собраны.  Нарушение означало бы, что done
 * выставлен преждевременно.
 */
ltl done_after_all   {{ [] (done == 1 -> k == N) }}

/* G(k=N → G k=N): счётчик монотонен — достигнув N,
 * он никогда не убывает. Это фундаментальнее, чем стабильность done,
 * т.к. done является производным от k.
 */
ltl cols_stable      {{ [] (k == N -> [] (k == N)) }}

/* --- ЖИВОСТЬ (liveness): «хорошее рано или поздно наступит» ---
 *
 * F(done=1): алгоритм всегда завершается.
 * Нарушение означало бы взаимную блокировку или голодание.
 */
ltl liveness_done    {{ <> (done == 1) }}

/* G(k<N → F k=N): прогресс гарантирован из ЛЮБОГО
 * промежуточного состояния, не только из начального.
 * Это строже, чем простая живость: даже если к моменту проверки
 * уже собрана часть столбцов, оставшиеся будут собраны.
 */
ltl progress_collect {{ [] (k < N -> <> (k == N)) }}

/* G(k=N → F done=1): как только все столбцы собраны,
 * менеджер ОБЯЗАТЕЛЬНО выставит done=1 (разошлёт STOP и завершится).
 * Это «обратная» сторона done_after_all.
 */
ltl cols_then_done   {{ [] (k == N -> <> (done == 1)) }}
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
