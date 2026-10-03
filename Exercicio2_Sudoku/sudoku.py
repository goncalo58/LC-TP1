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
    # Trabalho Prático: Sudoku (Explicado de Forma Simples)

    Neste trabalho, vamos construir um Sudoku inteligente. Em vez de escrevermos código super complexo para o computador adivinhar os números, vamos usar uma ferramenta da Google (o OR-Tools).

    A nossa única tarefa é explicar ao computador as regras do jogo. A regra de ouro do Sudoku é muito simples: **num grupo de células, os números não se podem repetir**. A ferramenta da Google percebe esta regra perfeitamente se a modelarmos como um problema de lógica.

    ---

    ## 1. O Saco Genérico (Regra R1)

    A classe `Box` é como se fosse um saco vazio. Nós podemos atirar células lá para dentro.

    Este saco não quer saber se as células vão formar uma linha, uma coluna ou um quadrado. Ele só serve para duas coisas:
    1. Guardar a posição (linha e coluna) e o número que lá está.
    2. Dar um estalo (erro) se tentarmos meter lá dentro uma coordenada ou um número que não existe no tabuleiro de Sudoku.
    """)
    return


@app.class_definition
class Box:
    def __init__(self, n, initial_cells=None):
        self.n = n
        self.n2 = n * n # Numa grelha normal (n=3), isto dá 9.
        
        # Aqui guardamos as coisas no formato (linha, coluna): valor
        self.cells = {}

        if initial_cells:
            for (i, j), val in initial_cells.items():
                self.add(i, j, val)

    def add(self, i, j, val=None):
        """Tenta adicionar uma célula. Se for inventada (fora do tabuleiro), dá erro."""
        if not (0 <= i < self.n2 and 0 <= j < self.n2):
            raise ValueError(f"As coordenadas ({i}, {j}) não existem no tabuleiro!")

        if val is not None and not (1 <= val <= self.n2):
            raise ValueError(f"O número {val} é inválido. Tem de ser de 1 a {self.n2}.")

        self.cells[(i, j)] = val
        return self

    def to_matrix(self):
        """Pega nas células que estão no saco e desenha-as numa grelha visual."""
        mat = [[0] * self.n2 for _ in range(self.n2)]
        for (i, j), val in self.cells.items():
            if val is not None:
                mat[i][j] = val
        return mat


@app.cell
def _(mo):
    mo.md(r"""
    ---
    ## 2. Linhas, Colunas e Quadrados (Regras R2 e R3)

    Como já temos o nosso saco genérico (`Box`), não precisamos de inventar a roda. Vamos criar dois sacos especiais que sabem preencher-se sozinhos:

    *   **O Quadrado (`Cube`):** Se lhe dissermos qual é o bloco que queremos (ex: o bloco do canto superior esquerdo), ele faz as contas e mete as 9 células desse quadrado lá para dentro.
    *   **A Reta (`Path`):** Nós dizemos onde começa e onde acaba, e ele vai a andar em linha reta (na horizontal ou na vertical) a apanhar as células todas pelo caminho. É assim que fazemos as linhas e as colunas do jogo!
    """)
    return


@app.cell
def _():
    class Cube(Box):
        def __init__(self, n, block_i, block_j):
            if not (0 <= block_i < n and 0 <= block_j < n):
                raise ValueError("Esse bloco não existe.")

            super().__init__(n) # Cria o saco base

            # Faz as contas para saber onde o quadrado começa
            start_i = block_i * n
            start_j = block_j * n

            # Varre o quadrado (3x3) e mete tudo no saco
            for di in range(n):
                for dj in range(n):
                    self.add(start_i + di, start_j + dj)


    class Path(Box):
        def __init__(self, n, start, end):
            super().__init__(n)

            i1, j1 = start
            i2, j2 = end

            if i1 != i2 and j1 != j2:
                raise ValueError("O caminho tem de ser uma linha reta (horizontal ou vertical).")

            # Truque para saber para que lado andar (passo de +1, -1 ou 0)
            di = 1 if i2 > i1 else (-1 if i2 < i1 else 0)
            dj = 1 if j2 > j1 else (-1 if j2 < j1 else 0)

            i, j = i1, j1
            while True:
                self.add(i, j)
                if i == i2 and j == j2: # Chegou ao destino, para de andar.
                    break
                i += di
                j += dj

    return Cube, Path


@app.cell
def _(mo):
    mo.md(r"""
    ---
    ## 3. Sortear as Pistas (Regra R4)

    Ninguém joga Sudoku com um tabuleiro totalmente vazio. Precisamos de alguns números para começar.

    Esta função espalha alguns números (pistas) à sorte pelo tabuleiro. Para garantir que não tenta colocar dois números no mesmo buraco, usamos uma função do Python que sorteia posições sem as repetir. O resultado final é devolvido num saco simples (`Box`).
    """)
    return


@app.cell
def _(random):
    def generate_random_clues(n, k=None):
        n2 = n * n
        if k is None:
            k = n * 2 # Se não nos disserem quantas pistas querem, damos algumas por defeito.

        if k < 0 or k > n2 * n2:
            raise ValueError(f"O número de pistas não faz sentido.")

        clues = Box(n)
        coordinates = []

        # Faz uma lista com todos os buraquinhos do tabuleiro
        for i in range(n2):
            for j in range(n2):
                coordinates.append((i, j))

        # Escolhe 'k' buracos à sorte (sem repetir o mesmo buraco)
        chosen = random.sample(coordinates, k)

        # Para cada buraco escolhido, atira um número lá para dentro (de 1 a 9)
        for i, j in chosen:
            value = random.randint(1, n2)
            clues.add(i, j, value)

        return clues

    return (generate_random_clues,)


@app.cell
def _(mo):
    mo.md(r"""
    ---
    ## 4. O Cérebro e a Fábrica (Regras R5 e R6)

    A função **`solve_sudoku_csp`** é o nosso **cérebro** (R5).
    Ela recebe os sacos todos cheios de células e diz ao computador: *"Olha, em cada um destes sacos, os números não se podem repetir. As pistas têm de ficar onde estão. Agora, preenche o resto e descobre a solução!"*.

    A função **`build_and_solve_sudoku`** é a nossa **fábrica** (R6).
    Ela cria as 9 linhas, as 9 colunas e os 9 quadrados, atira as pistas lá para o meio, e manda esse molho todo de regras para o cérebro resolver.
    """)
    return


@app.cell
def _(Cube, Path, cp_model):
    def solve_sudoku_csp(n, groups):
        n2 = n * n
        model = cp_model.CpModel()
        grid_vars = {}

        # 1. Cria as incógnitas (buracos vazios que o pc tem de descobrir)
        for i in range(n2):
            for j in range(n2):
                grid_vars[(i, j)] = model.NewIntVar(1, n2, f"Celula_{i}_{j}")

        # 2. Aplica as regras da Google
        for group in groups:
            group_vars = []

            for (i, j), fixed_value in group.cells.items():
                var = grid_vars[(i, j)]
                group_vars.append(var)

                # Se for uma pista (número já preenchido), tranca-o lá!
                if fixed_value is not None:
                    model.Add(var == fixed_value)

            # A regra mágica: obriga todos os elementos deste grupo a serem diferentes
            if len(group_vars) > 1:
                model.AddAllDifferent(group_vars)

        # 3. Pede ao PC para pensar e resolver
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # 4. Devolve o tabuleiro resolvido
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            solution = []
            for i in range(n2):
                row = []
                for j in range(n2):
                    value = solver.Value(grid_vars[(i, j)])
                    row.append(value)
                solution.append(row)
            return solution

        return None # Se o puzzle não tiver solução possível

    def build_and_solve_sudoku(n, clues_box):
        n2 = n * n
        groups = [clues_box] # Começa com as pistas

        # Cria as Linhas e Colunas
        for i in range(n2):
            groups.append(Path(n, start=(i, 0), end=(i, n2 - 1))) # Linha
            groups.append(Path(n, start=(0, i), end=(n2 - 1, i))) # Coluna

        # Cria os Quadrados
        for block_i in range(n):
            for block_j in range(n):
                groups.append(Cube(n, block_i, block_j))

        # Manda para o cérebro!
        return solve_sudoku_csp(n, groups)

    return (build_and_solve_sudoku,)


@app.cell
def _(mo):
    mo.md(r"""
    ---
    ## 5. Prova dos 9 (Testes)

    Como sorteamos os números iniciais completamente às cegas, o gerador pode ter o azar de meter um '5' na mesma linha que outro '5', tornando o jogo impossível logo de início.

    Para que os testes funcionem sem encravar, pedimos ao computador para tentar inventar jogos repetidamente até encontrar um que tenha lógica. Quando encontrar, passamos o jogo resolvido a pente fino: vemos se alguma regra falhou ou se as pistas foram roubadas do sítio.
    """)
    return


@app.cell
def _(build_and_solve_sudoku, generate_random_clues, mo):
    def validate_solution(n, solution, clues):
        """Passa o tabuleiro a pente fino para ver se o computador não nos enganou."""
        n2 = n * n
        expected = set(range(1, n2 + 1)) # O conjunto perfeito: {1, 2, 3, 4, 5, 6, 7, 8, 9}

        # Verifica se as linhas e colunas têm os números todos corretos
        for i in range(n2):
            row = set(solution[i])
            assert row == expected, f"As contas falharam na linha {i}."

        for j in range(n2):
            column = set(solution[i][j] for i in range(n2))
            assert column == expected, f"As contas falharam na coluna {j}."

        # Verifica se o computador não nos roubou as pistas do sítio onde as pusemos
        for (i, j), value in clues.cells.items():
            assert solution[i][j] == value, f"O PC apagou a nossa pista ({i},{j})."

    def generate_solvable(n, k):
        # Tenta 100 vezes até encontrar um jogo que faça sentido
        for _ in range(100):
            clues = generate_random_clues(n, k)
            solution = build_and_solve_sudoku(n, clues)
            if solution is not None:
                return clues, solution
        return None, None

    def run_tests():
        log = ["**A provar que tudo funciona:**\n"]

        # TESTE 1: Obrigar o saco a rejeitar lixo
        try:
            b = Box(3).add(10, 0)
            log.append("❌ O saco deixou meter uma célula na linha 10!")
        except ValueError:
            log.append("✅ Teste 1 (Limites): Passou! Rejeitou coordenadas que não existem.")

        # TESTE 2: Resolver e auditar um Sudoku 9x9 inteiro
        clues3, solution3 = generate_solvable(n=3, k=5)
        if solution3 is None:
            log.append("❌ Muito azar! O PC não gerou nenhum tabuleiro possível.")
            return mo.md("  \n".join(log))
        
        validate_solution(3, solution3, clues3)
        log.append("✅ Teste 2 (Resolver Sudoku): Passou! Verificámos as linhas e colunas todas e a matemática está perfeita.")

        # Imprime a Grelha Final para a podermos ver
        grid = ["", "### O Tabuleiro Final:", "```text"]
        for row in solution3:
            grid.append(str(row))
        grid.append("```")

        return mo.md("  \n".join(log) + "\n\n" + "\n".join(grid))

    resultado_testes = run_tests()
    return (resultado_testes,)


@app.cell
def _(resultado_testes):
    resultado_testes
    return


if __name__ == "__main__":
    app.run()
