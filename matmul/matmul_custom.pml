/*
 * АВТОСГЕНЕРИРОВАННЫЙ файл (gen_matmul.py).
 * Не редактируй вручную — измени matrix.txt и перегенерируй.
 *
 * Параллельное умножение матриц C = A * B по столбцам.
 * Схема "менеджер–работники" из учебника (раздел 6.4), без shared memory.
 *
 * Эталонный результат C = A * B (для проверки):
 *    2  4  6  9
 *    5  7  9 21
 *    8 10 12 33
 *    3  5  7  6
 */

#define N    4      /* размер матриц N x N           */
#define P    4      /* число работников              */
#define STOP 0      /* "конец работы" в канале task   */

typedef Col { byte v[N] };

chan task[P] = [1] of { byte };
chan result  = [P] of { byte, byte, Col };

bit  done = 0;
byte ready_cols = 0;

inline print_matrix(M)
{
    pi = 0;
    do
    :: (pi < N) ->
        pj = 0;
        do
        :: (pj < N) -> printf("%d ", M[pi*N + pj]); pj++
        :: (pj == N) -> break
        od;
        printf("\n");
        pi++
    :: (pi == N) -> break
    od
}

/* Значения матриц A и B вшиты из matrix.txt. Каждый процесс
   инициализирует СВОИ локальные копии — никакой shared memory. */
inline init_AB(A, B)
{
    A[0*N + 0] = 1;
    A[0*N + 1] = 2;
    A[0*N + 2] = 3;
    A[0*N + 3] = 1;
    A[1*N + 0] = 4;
    A[1*N + 1] = 5;
    A[1*N + 2] = 6;
    A[1*N + 3] = 1;
    A[2*N + 0] = 7;
    A[2*N + 1] = 8;
    A[2*N + 2] = 9;
    A[2*N + 3] = 1;
    A[3*N + 0] = 1;
    A[3*N + 1] = 1;
    A[3*N + 2] = 1;
    A[3*N + 3] = 2;

    B[0*N + 0] = 1;
    B[0*N + 1] = 0;
    B[0*N + 2] = 0;
    B[0*N + 3] = 1;
    B[1*N + 0] = 0;
    B[1*N + 1] = 1;
    B[1*N + 2] = 0;
    B[1*N + 3] = 2;
    B[2*N + 0] = 0;
    B[2*N + 1] = 0;
    B[2*N + 2] = 1;
    B[2*N + 3] = 1;
    B[3*N + 0] = 1;
    B[3*N + 1] = 2;
    B[3*N + 2] = 3;
    B[3*N + 3] = 1;
}

proctype Worker(byte id)
{
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
}

init {
    byte A[N*N];
    byte B[N*N];
    byte C[N*N];

    byte l, k, rid, rj;
    Col  col;
    byte pi, pj, w, i, q;

    init_AB(A, B);

    atomic {
        w = 0;
        do
        :: (w < P) -> run Worker(w); w++
        :: (w == P) -> break
        od
    }

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

    printf("Matrix A:\n");
    print_matrix(A);
    printf("Matrix B:\n");
    print_matrix(B);
    printf("Result matrix C = A * B:\n");
    print_matrix(C);

    done = 1
}

ltl safety_bounded   { [] (ready_cols <= N) }
ltl liveness_done    { <> (done == 1) }
ltl done_after_all   { [] (done == 1 -> ready_cols == N) }
ltl progress_collect { [] (ready_cols < N -> <> (ready_cols == N)) }
