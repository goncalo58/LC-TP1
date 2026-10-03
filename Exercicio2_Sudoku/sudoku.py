# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "marimo>=0.24.2",
#     "ortools",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import random
    from ortools.sat.python import cp_model

    return cp_model, mo, random


@app.cell
def _(mo):
    mo.md(r"""
    # Trabalho Prático: Sudoku Genérico como CSP

    ## Implementação

    Este trabalho implementa um gerador e resolvedor de Sudoku genérico
    de dimensão $n^2 \times n^2$, modelado como um Problema de
    Satisfação de Restrições (CSP).

    Para a resolução foi utilizado o **CP-SAT do OR-Tools**.

    Esta abordagem é adequada porque cada célula pode ser representada
    por uma variável inteira com domínio $[1,n^2]$ e as regras do Sudoku
    podem ser representadas através da restrição `AllDifferent`.

    Assim, a mesma restrição pode ser aplicada de forma genérica a
    linhas, colunas, blocos e outros grupos de células.
    """)
    return


@app.cell
def _():

    class Box:
        """
        R1: Grupo genérico de células.

        Um Box representa qualquer conjunto de células da grelha.
        Cada célula pode estar livre (None) ou ter um valor fixo.

        Esta classe não sabe se o grupo representa uma linha,
        coluna, bloco ou pistas.
        """

        def __init__(self, n, initial_cells=None):

            self.n = n
            self.n2 = n * n

            # Dicionário:
            # (linha, coluna) -> valor
            #
            # None significa que a célula não tem valor fixo.
            self.cells = {}

            # Permite criar o Box já com células.
            if initial_cells:

                for (i, j), val in initial_cells.items():

                    self.add(i, j, val)


        def add(self, i, j, val=None):
            """
            Adiciona uma célula ao grupo.

            Se val for diferente de None, a célula fica
            fixa nesse valor.
            """

            # Verificar se as coordenadas pertencem à grelha.
            if not (
                0 <= i < self.n2
                and
                0 <= j < self.n2
            ):

                raise ValueError(
                    f"Coordenadas ({i}, {j}) estão fora da grelha!"
                )

            # Verificar se o valor é permitido.
            if val is not None:

                if not (1 <= val <= self.n2):

                    raise ValueError(
                        f"Valor {val} tem de estar entre "
                        f"1 e {self.n2}."
                    )

            # Adicionar a célula.
            self.cells[(i, j)] = val

            return self


        def to_matrix(self):
            """
            Converte o grupo para uma matriz n² x n².

            As células que não têm valor fixo aparecem como 0.
            """

            mat = [
                [0] * self.n2
                for _ in range(self.n2)
            ]

            for (i, j), val in self.cells.items():

                if val is not None:

                    mat[i][j] = val

            return mat


    class Cube(Box):
        """
        R2: Grupo correspondente a um bloco n x n.
        """

        def __init__(self, n, block_i, block_j):

            # Os índices dos blocos têm de estar entre 0 e n-1.
            if not (
                0 <= block_i < n
                and
                0 <= block_j < n
            ):

                raise ValueError(
                    "Índice de bloco inválido."
                )

            # Inicializar primeiro o Box.
            super().__init__(n)

            # Canto superior esquerdo do bloco.
            start_i = block_i * n
            start_j = block_j * n

            # Adicionar todas as células do bloco.
            for di in range(n):

                for dj in range(n):

                    self.add(
                        start_i + di,
                        start_j + dj
                    )


    class Path(Box):
        """
        R3: Grupo correspondente a um troço reto.

        Pode ser horizontal ou vertical e funciona
        nos dois sentidos.
        """

        def __init__(self, n, start, end):

            super().__init__(n)

            i1, j1 = start
            i2, j2 = end

            # Um Path só pode ser horizontal ou vertical.
            if i1 != i2 and j1 != j2:

                raise ValueError(
                    "Path tem de ser horizontal ou vertical."
                )

            # Determinar o sentido vertical.
            if i2 > i1:
                di = 1

            elif i2 < i1:
                di = -1

            else:
                di = 0

            # Determinar o sentido horizontal.
            if j2 > j1:
                dj = 1

            elif j2 < j1:
                dj = -1

            else:
                dj = 0

            # Começar na primeira coordenada.
            i = i1
            j = j1

            while True:

                self.add(i, j)

                # Quando chegamos ao fim, terminamos.
                if i == i2 and j == j2:
                    break

                i += di
                j += dj


    return Box, Cube, Path


@app.cell
def _(Box, random):

    def generate_random_clues(n, k=None):
        """
        Gera k pistas aleatórias.

        O resultado continua a ser simplesmente um Box.
        """

        n2 = n * n

        # Valor por omissão.
        if k is None:
            k = n * 2

        # Não podemos pedir mais pistas do que células.
        if k < 0 or k > n2 * n2:

            raise ValueError(
                f"k deve estar entre 0 e {n2 * n2}."
            )

        clues = Box(n)

        # Criar todas as coordenadas possíveis.
        coordinates = []

        for i in range(n2):

            for j in range(n2):

                coordinates.append(
                    (i, j)
                )

        # Escolher k posições sem repetição.
        chosen = random.sample(
            coordinates,
            k
        )

        # Atribuir um valor aleatório a cada posição.
        for i, j in chosen:

            value = random.randint(
                1,
                n2
            )

            clues.add(
                i,
                j,
                value
            )

        return clues


    return (generate_random_clues,)


@app.cell
def _(Cube, Path, cp_model):

    def solve_sudoku_csp(n, groups):
        """
        Cria e resolve o modelo CSP.

        Recebe grupos sem distinguir se são linhas,
        colunas, blocos ou pistas.
        """

        n2 = n * n

        model = cp_model.CpModel()

        # ----------------------------------------------------
        # 1. Variáveis
        # ----------------------------------------------------

        grid_vars = {}

        for i in range(n2):

            for j in range(n2):

                grid_vars[(i, j)] = model.NewIntVar(
                    1,
                    n2,
                    f"Celula_{i}_{j}"
                )

        # ----------------------------------------------------
        # 2. Restrições
        # ----------------------------------------------------

        for group in groups:

            group_vars = []

            for (i, j), fixed_value in group.cells.items():

                var = grid_vars[(i, j)]

                group_vars.append(var)

                # Se existir valor fixo, aplicar a pista.
                if fixed_value is not None:

                    model.Add(
                        var == fixed_value
                    )

            # Todas as células do grupo têm valores diferentes.
            if len(group_vars) > 1:

                model.AddAllDifferent(
                    group_vars
                )

        # ----------------------------------------------------
        # 3. Resolver
        # ----------------------------------------------------

        solver = cp_model.CpSolver()

        status = solver.Solve(model)

        # ----------------------------------------------------
        # 4. Construir a solução
        # ----------------------------------------------------

        if status in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE
        ):

            solution = []

            for i in range(n2):

                row = []

                for j in range(n2):

                    value = solver.Value(
                        grid_vars[(i, j)]
                    )

                    row.append(value)

                solution.append(row)

            return solution

        # None permite distinguir claramente
        # o caso em que não existe solução.
        return None


    # ========================================================
    # R6 - CONSTRUÇÃO DO SUDOKU
    # ========================================================

    def build_and_solve_sudoku(n, clues_box):
        """
        Constrói todas as linhas, colunas e blocos
        e adiciona também as pistas.
        """

        n2 = n * n

        # O primeiro grupo contém as pistas.
        groups = [clues_box]

        # ----------------------------------------------------
        # Linhas
        # ----------------------------------------------------

        for i in range(n2):

            row = Path(
                n,
                start=(i, 0),
                end=(i, n2 - 1)
            )

            groups.append(row)

        # ----------------------------------------------------
        # Colunas
        # ----------------------------------------------------

        for j in range(n2):

            column = Path(
                n,
                start=(0, j),
                end=(n2 - 1, j)
            )

            groups.append(column)

        # ----------------------------------------------------
        # Blocos
        # ----------------------------------------------------

        for block_i in range(n):

            for block_j in range(n):

                block = Cube(
                    n,
                    block_i,
                    block_j
                )

                groups.append(block)

        # Resolver o CSP completo.
        return solve_sudoku_csp(
            n,
            groups
        )


    return (build_and_solve_sudoku,)


@app.cell
def _(Box, build_and_solve_sudoku, generate_random_clues, mo):

    def validate_solution(n, solution, clues):
        """
        Verifica automaticamente se uma solução
        cumpre todas as regras do Sudoku.
        """

        n2 = n * n

        expected = set(
            range(1, n2 + 1)
        )

        # ----------------------------------------------------
        # Verificar linhas
        # ----------------------------------------------------

        for i in range(n2):

            row = set(
                solution[i]
            )

            assert row == expected, (
                f"Linha {i} inválida."
            )

        # ----------------------------------------------------
        # Verificar colunas
        # ----------------------------------------------------

        for j in range(n2):

            column = set()

            for i in range(n2):

                column.add(
                    solution[i][j]
                )

            assert column == expected, (
                f"Coluna {j} inválida."
            )

        # ----------------------------------------------------
        # Verificar blocos n x n
        # ----------------------------------------------------

        for block_i in range(n):

            for block_j in range(n):

                values = set()

                start_i = block_i * n
                start_j = block_j * n

                for di in range(n):

                    for dj in range(n):

                        values.add(
                            solution[
                                start_i + di
                            ][
                                start_j + dj
                            ]
                        )

                assert values == expected, (
                    f"Bloco ({block_i}, "
                    f"{block_j}) inválido."
                )

        # ----------------------------------------------------
        # Verificar pistas
        # ----------------------------------------------------

        for (i, j), value in clues.cells.items():

            assert solution[i][j] == value, (
                f"A pista ({i},{j}) foi alterada."
            )


    def generate_solvable(n, k):
        """
        Como as pistas são totalmente aleatórias,
        algumas combinações podem não ter solução.

        Nesse caso são geradas novas pistas.
        """

        for _ in range(100):

            clues = generate_random_clues(
                n,
                k
            )

            solution = build_and_solve_sudoku(
                n,
                clues
            )

            if solution is not None:

                return clues, solution

        return None, None


    def run_tests():

        log = [
            "**Testes automáticos:**"
        ]

        # ====================================================
        # TESTE 1
        # Coordenadas inválidas
        # ====================================================

        try:

            b = Box(3)

            b.add(
                10,
                0
            )

            log.append(
                " Coordenadas inválidas não foram rejeitadas."
            )

        except ValueError:

            log.append(
                " Coordenadas inválidas rejeitadas."
            )

        # ====================================================
        # TESTE 2
        # Valores inválidos
        # ====================================================

        try:

            b = Box(3)

            b.add(
                0,
                0,
                10
            )

            log.append(
                " Valor inválido não foi rejeitado."
            )

        except ValueError:

            log.append(
                " Valores inválidos rejeitados."
            )

        # ====================================================
        # TESTE 3
        # n = 3 -> Sudoku 9x9
        # ====================================================

        clues3, solution3 = generate_solvable(
            n=3,
            k=5
        )

        assert solution3 is not None, (
            "Não foi possível obter uma solução 9x9."
        )

        validate_solution(
            3,
            solution3,
            clues3
        )

        log.append(
            " Sudoku n=3 (9x9): "
            "linhas, colunas, blocos e pistas válidos."
        )

        # ====================================================
        # TESTE 4
        # n = 2 -> Sudoku 4x4
        # ====================================================

        clues2, solution2 = generate_solvable(
            n=2,
            k=2
        )

        assert solution2 is not None, (
            "Não foi possível obter uma solução 4x4."
        )

        validate_solution(
            2,
            solution2,
            clues2
        )

        log.append(
            " Sudoku n=2 (4x4): "
            "linhas, colunas, blocos e pistas válidos."
        )

        # ====================================================
        # Mostrar a grelha 9x9
        # ====================================================

        grid = [
            "",
            "## Grellha 9x9 resolvida",
            "",
            "```text"
        ]

        for row in solution3:

            grid.append(
                str(row)
            )

        grid.append(
            "```"
        )

        return mo.md(
            "  \n".join(log)
            + "\n\n"
            + "\n".join(grid)
        )


    resultado_testes = run_tests()
    return (resultado_testes,)


@app.cell
def _(resultado_testes):

    resultado_testes
    return


if __name__ == "__main__":
    app.run()
