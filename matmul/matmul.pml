#define N    4      
#define P    2   
#define STOP 0     

// Тип столбец: массив длины N в одном сообщении 
typedef Col { byte v[N] };

// P адресных каналов менеджер -> работник i // размер 1, тк если рабочий занят ему новая задача не придёт
chan task[P] = [1] of { byte };

// Общий канал работник -> менеджер (worker_id, j, column).
chan result  = [P] of { byte, byte, Col };

// переменные для LTL в них пишет p0
bit  done = 0;
byte k = 0;          // число принятых менеджером столбцов-результатов 


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

// Локальная инициализация матриц A, B 
// A[i,k] = i*N + k + 1, B = единичная матрица, чтобы C = A*B = A. */

inline init_AB(A, B)
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

//Работник P_i
proctype Worker(byte id)
{
    byte A[N*N];
    byte B[N*N];
    byte column_number, i, j, s;
    Col  col;

    init_AB(A, B);

    // Цикл получить задачу, выполнить, вернуть результат 
    do
    :: task[id] ? column_number ->
        if
        :: (column_number == STOP) -> break                 // состояние 2: конец работы
        :: else ->                              // column_number ∈ {1..N}: задача
            // col[i] = sum_k A[i,k] * B[k, column_number-1]  
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

// Менеджер P_0 
init {
    // Локальные копии A и B нужны только для печати
    byte A[N*N];
    byte B[N*N];
    byte C[N*N];

    // Переменные алгоритма  
    byte l;        // следующий назначаемый номер столбца, 1..N      
    byte rid;      // id работника, приславшего результат            
    byte rj;       // номер столбца, который он считал               
    Col  col;

    init_AB(A, B);

    // Запуск P работников 
    byte w = 0;
    do
    :: (w < P) -> run Worker(w); w++
    :: (w == P) -> break
    od;

    // Состояние 0 -> 0: первичная раздача задач 
    // Посылаем работникам по очереди номера столбцов 1..min(P, N). 
    l = 1;
    do
    :: (l <= P) && (l <= N) -> task[l - 1] ! l; l++
    :: else -> break
    od;
    // теперь l = min(P, N) + 1 

    // Состояния 1 -> 2 -> 1: приём результатов и довыдача задач 
    // Принимаем ровно N результатов; после каждого выдаём новую
    // задачу тому же работнику, если ещё есть, иначе пропускаем.
    k = 0;
    byte i;
    do
    :: (k < N) ->
        result ? rid, rj, col;
        // Раскладываем столбец col в (rj-1)-й столбец C 
		if
        :: (l <= N) -> task[rid] ! l; l++
        :: else     -> skip
        fi
        i = 0;
        do
        :: (i < N) -> C[i*N + (rj - 1)] = col.v[i]; i++
        :: (i == N) -> break
        od;
        k++;
    :: (k == N) -> break
    od;

    // Состояние 3 -> 3: рассылка сигнала окончания работы 
    // STOP отправляется ВСЕМ P работникам, включая тех, кто никогда
    // не получал реальной задачи (случай P > N). */
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

//k число принятых менеджером столбцов-результатов (0..N)
//done = 1 ровно после того, как все столбцы собраны и STOP разослан всем работникам
 
//безопасность (плохого никогда не случится)
//счётчик результатов никогда не переполняется. Менеджер ждёт ровно N ответов,ready_cols ∈ {0..N} всегда.
ltl safety_bounded   { [] (k <= N) } // G ¬(ready_cols > N):

//флаг завершения выставляется только после того, как все N столбцов собраны. 
// Нарушение означало бы, что done выставлен преждевременно.
ltl done_after_all   { [] (done == 1 -> k == N) } //G(done=1 → k=N)

// счётчик достигнув N никогда не убывает. 
ltl cols_stable      { [] (k == N -> [] (k == N)) } //G(k=N → G k=N)

//  живость  хорошее рано или поздно наступит 

//алгоритм всегда завершается.
//Нарушение означало бы взаимную блокировку или голодание.
ltl liveness_done    { <> (done == 1) } //F(done=1)

//прогресс гарантирован из любого промежуточного состояния, не только из начального.
// даже если к моменту проверки уже собрана часть столбцов, оставшиеся будут собраны.
ltl progress_collect { [] (k < N -> <> (k == N)) } //G(k<N → F k=N)

//  как только все столбцы собраны менеджер  выставит done=1 (разошлёт STOP и завершится).
ltl cols_then_done   { [] (k == N -> <> (done == 1)) } //G(k=N → F done=1)
