#define N    4
#define P    4
#define STOP 0

// Разделяемая память. Нет каналов, нет atomic/d_step, нет Петерсона.
// Дисциплина: на каждую ячейку приходится ровно один писатель,
// кроме двух флагов-рукопожатий, где писатели чередуются по протоколу
// и никогда не пишут одновременно.

// Входные матрицы. Пишет init один раз до запуска работников,
// дальше только читают (Worker'ы) -> гонок нет.
byte A[N*N];
byte B[N*N];

// Результат. На каждый столбец пишет ровно один Worker
// (которому менеджер назначил этот столбец), читает init для печати.
byte C[N*N];

// Слот задачи менеджер -> Worker i.
// task_col[i]: пишет только менеджер; читает только Worker i.
// task_ready[i]: handshake — менеджер ставит 0->1 (после записи task_col),
//                Worker i ставит 1->0 (после чтения task_col).
//                Никогда не пишут одновременно: менеджер пишет 1 только когда
//                видит 0; Worker пишет 0 только когда видит 1.
byte task_col[P];
bit  task_ready[P];

// Слот результата Worker i -> менеджер.
// result_col_data[i*N + r]: пишет только Worker i; читает только менеджер.
// result_ready[i]: handshake — Worker ставит 0->1 после записи всех N значений,
//                  менеджер ставит 1->0 после чтения.
byte result_col_data[P*N];
bit  result_ready[P];

// LTL-наблюдаемые: пишет только менеджер.
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

// A[i,k] = i*N+k+1, B = единичная -> C = A*B = A. Вызывается ОДИН РАЗ
// из init до запуска Worker'ов, поэтому записи в A,B безопасны.
inline init_AB()
{
    byte ii = 0;
    byte kk;
    do
    :: (ii < N) ->
        kk = 0;
        do
        :: (kk < N) ->
            A[ii*N + kk] = ii*N + kk + 1;
            if
            :: (ii == kk) -> B[ii*N + kk] = 1
            :: else       -> B[ii*N + kk] = 0
            fi;
            kk++
        :: (kk == N) -> break
        od;
        ii++
    :: (ii == N) -> break
    od
}

proctype Worker(byte id)
{
    byte my_col, i, j, s;

    do
    // Ждём, пока менеджер выставит флаг готовности задачи.
    // Это блокирующее ожидание выражения, аналог приёма из канала.
    :: (task_ready[id] == 1) ->
        // Порядок важен: сначала читаем данные, потом квитируем флаг.
        my_col = task_col[id];
        task_ready[id] = 0;
        if
        :: (my_col == STOP) -> break
        :: else ->
            // Вычисляем столбец и пишем его в свой слот result_col_data.
            i = 0;
            do
            :: (i < N) ->
                s = 0;
                j = 0;
                do
                :: (j < N) ->
                    s = s + A[i*N + j] * B[j*N + (my_col - 1)];
                    j++
                :: (j == N) -> break
                od;
                result_col_data[id*N + i] = s;
                i++
            :: (i == N) -> break
            od;
            // Только ПОСЛЕ записи всех N значений выставляем флаг.
            // Менеджер увидит ready=1 уже с консистентными данными.
            result_ready[id] = 1
        fi
    od
}

init {
    byte C_local[N*N];   // только для печати
    byte l;              // следующий назначаемый номер столбца, 1..N
    byte assigned[P];    // assigned[i] = столбец, который сейчас считает Worker i (0 если не считает)
    byte rid;            // выбранный работник на этой итерации
    byte i;

    init_AB();

    byte w = 0;
    do
    :: (w < P) -> run Worker(w); w++
    :: (w == P) -> break
    od;

    // Первичная раздача: min(P, N) задач.
    // Порядок важен: сначала пишем данные (task_col, assigned), потом флаг.
    l = 1;
    do
    :: (l <= P) && (l <= N) ->
        task_col[l - 1] = l;
        assigned[l - 1] = l;
        task_ready[l - 1] = 1;
        l++
    :: else -> break
    od;

    // Основной цикл: ждём любого работника с готовым результатом,
    // забираем его столбец в C, выдаём ему новую задачу (если есть).
    k = 0;
    do
    :: (k < N) ->
        // Нондетерминированный выбор первого готового Worker'а.
        // Spin блокируется, пока ни один guard не истинен, и нондетерминированно
        // выбирает среди истинных. Это аналог "ждать любое сообщение".
        if
        :: (result_ready[0] == 1) -> rid = 0
        :: (result_ready[1] == 1) -> rid = 1
        :: (result_ready[2] == 1) -> rid = 2
        :: (result_ready[3] == 1) -> rid = 3
        fi;

        // Сначала читаем данные, потом сбрасываем флаг.
        i = 0;
        do
        :: (i < N) -> C[i*N + (assigned[rid] - 1)] = result_col_data[rid*N + i]; i++
        :: (i == N) -> break
        od;
        result_ready[rid] = 0;
        k++;

        // Если есть ещё столбцы, выдаём этому же работнику новый.
        // task_ready[rid] здесь гарантированно 0: Worker сбросил его,
        // когда брал предыдущую задачу.
        if
        :: (l <= N) ->
            task_col[rid] = l;
            assigned[rid] = l;
            task_ready[rid] = 1;
            l++
        :: else -> skip
        fi
    :: (k == N) -> break
    od;

    // Рассылка STOP всем P работникам. task_ready[q] здесь точно 0:
    // - кто работал, сбросил его при последнем взятии задачи;
    // - кто не работал (случай P > N), никогда не получал task_ready=1.
    byte q = 0;
    do
    :: (q < P) ->
        task_col[q] = STOP;
        task_ready[q] = 1;
        q++
    :: (q == P) -> break
    od;

    // Печать.
    i = 0;
    do
    :: (i < N*N) -> C_local[i] = C[i]; i++
    :: (i == N*N) -> break
    od;
    printf("Matrix A:\n");
    print_matrix(A);
    printf("Matrix B:\n");
    print_matrix(B);
    printf("Result matrix C = A * B:\n");
    print_matrix(C_local);

    done = 1
}

// LTL — наблюдаемые те же, что и в канальной версии.
ltl safety_bounded   { [] (k <= N) }
ltl done_after_all   { [] (done == 1 -> k == N) }
ltl cols_stable      { [] (k == N -> [] (k == N)) }
ltl liveness_done    { <> (done == 1) }
ltl progress_collect { [] (k < N -> <> (k == N)) }
ltl cols_then_done   { [] (k == N -> <> (done == 1)) }
