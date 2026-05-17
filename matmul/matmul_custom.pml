#define N    4
#define P    4
#define STOP 0

typedef Col { byte v[N] };

chan task[P] = [1] of { byte };

chan result  = [P] of { byte, byte, Col };

bit  done = 0;
byte k = 0;

inline print_matrix(M)
{
    byte pi = 0;
    do
    :: (pi < N) ->
        byte pj = 0;
        do
        :: (pj < N) -> printf("%d ", M[pi*N + pj]); pj++
        :: (pj == N) -> break
        od;
        printf("\n");
        pi++
    :: (pi == N) -> break
    od
}

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
}

init {
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

    printf("Matrix A:\n");
    print_matrix(A);
    printf("Matrix B:\n");
    print_matrix(B);
    printf("Result matrix C = A * B:\n");
    print_matrix(C);

    done = 1
}

ltl safety_bounded   { [] (k <= N) }

ltl done_after_all   { [] (done == 1 -> k == N) }

ltl cols_stable      { [] (k == N -> [] (k == N)) }

ltl liveness_done    { <> (done == 1) }

ltl progress_collect { [] (k < N -> <> (k == N)) }

ltl cols_then_done   { [] (k == N -> <> (done == 1)) }
