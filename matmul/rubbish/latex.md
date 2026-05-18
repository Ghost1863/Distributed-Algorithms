$\documentclass[tikz,border=5pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{automata, positioning, arrows.meta}

\begin{document}

\begin{tikzpicture}[
    node distance=3.5cm,
    every state/.style={draw, circle, minimum size=0.8cm, font=\large},
    >=Stealth,
    thick
]

\node[state] (0) {0};
\node[state, right=of 0] (1) {1};
\node[state, right=of 1] (2) {2};

% Стрелка 0 -> 1 (верхняя) с метками НАД ней
\draw[->] (0) -- node[above, align=center] {$c_i?j_i$} (1);

% Стрелка 1 -> 0 (нижняя, обратная) с метками ПОД ней
\draw[->] (1) -- node[below, align=center] {$\{j_i \neq 0\}$ \\ $c_0!(AB_{j_i}, i, j_i)$}  (0);

% Стрелка 1 -> 2 с меткой {j_i = 0} НАД ней
\draw[->] (1) -- node[above] {$\{j_i = 0\}$} (2);

\end{tikzpicture}

\end{document}$
