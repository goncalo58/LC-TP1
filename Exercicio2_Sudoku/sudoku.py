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
    mo.md("""
    # Trabalho Prático: Sudoku Genérico como CSP
    Implementação das regras R1 a R6.
    """)
    return


@app.cell
def _():
    class Box:
        """
        R1: Grupo genérico de células.
        Esta é a classe base. Não sabe se é linha, coluna ou bloco.
        Apenas guarda células e sabe que todas têm de ter valores diferentes.
        """
        def __init__(self, n, initial_cells=None):
            self.n = n
            self.n2 = n * n # Se n=3, a grelha é 9x9, logo n2=9
        
            # O dicionário 'cells' guarda as células que pertencem a este grupo.
            # Formato: {(linha, coluna): valor}. Se não tiver valor fixo, guarda None.
            self.cells = {} 
        
            if initial_cells:
                for (i, j), val in initial_cells.items():
                    self.add(i, j, val)

        def add(self, i, j, val=None):
            # DECISÃO: Validação rigorosa pedida pelo professor.
            # Rejeita imediatamente se as coordenadas estiverem fora do tabuleiro.
            if not (0 <= i < self.n2 and 0 <= j < self.n2):
                raise ValueError(f"Coordenadas ({i}, {j}) estão fora da grelha!")
        
            # Rejeita se o valor for inválido (tem de ser entre 1 e n^2, ex: 1 a 9)
            if val is not None and not (1 <= val <= self.n2):
                raise ValueError(f"Valor {val} tem de estar entre 1 e {self.n2}.")
        
            # Adiciona ao dicionário de células deste grupo
            self.cells[(i, j)] = val
            return self

        def to_matrix(self):
            # Cria uma matriz (lista de listas) cheia de zeros
            mat = [[0] * self.n2 for _ in range(self.n2)]
        
            # Preenche a matriz apenas com as células que pertencem a este Box
            for (i, j), val in self.cells.items():
                if val is not None:
                    mat[i][j] = val
            return mat

    class Cube(Box):
        """
        R2: Grupo que representa um bloco n x n (os quadrados do Sudoku).
        Herda de Box (é um Box especializado).
        """
        def __init__(self, n, block_i, block_j):
            super().__init__(n) # Executa primeiro o construtor do Box original
        
            # Multiplicamos por n para saber a coordenada real de início do bloco na grelha
            start_i = block_i * n
            start_j = block_j * n
        
            # Percorre o quadrado n x n e adiciona essas coordenadas ao grupo
            for di in range(n):
                for dj in range(n):
                    self.add(start_i + di, start_j + dj)

    class Path(Box):
        """
        R3: Grupo que representa uma linha ou coluna inteira.
        Também herda de Box, mas calcula coordenadas em linha reta.
        """
        def __init__(self, n, start, end):
            super().__init__(n)
            i1, j1 = start
            i2, j2 = end
        
            # DECISÃO: Truque matemático para saber a direção (di, dj).
            # Se o fim é maior que o início, anda +1. Se menor, anda -1. Se igual, 0.
            di = 1 if i2 > i1 else (-1 if i2 < i1 else 0)
            dj = 1 if j2 > j1 else (-1 if j2 < j1 else 0)
        
            i, j = i1, j1
        
            # Ciclo que anda passo a passo até chegar à coordenada final
            while True:
                self.add(i, j)
                if i == i2 and j == j2: # Chegou ao fim, quebra o ciclo
                    break
                i += di
                j += dj
            

    return Box, Cube, Path


@app.cell
def _(Box, random):
    def generate_random_clues(n, k=None):
        """
        R4: Gera pistas (números iniciais) aleatórias.
        Devolve um Box simples contendo k células fixas.
        """
        if k is None:
            k = n * 2  # Se não pedirem k específico, assume n*2 pistas
        
        n2 = n * n
        clue_box = Box(n)
    
        # DECISÃO: Usar um 'set' (conjunto) porque não permite elementos repetidos.
        # Garante que não tentamos colocar duas pistas na mesma célula exata.
        added_coords = set()
    
        # Proteção contra ciclos infinitos se pedirem mais pistas do que células existem
        if k > n2 * n2:
            k = n2 * n2 
    
        # Sorteia até ter atingido o número de pistas desejadas
        while len(added_coords) < k:
            i = random.randint(0, n2 - 1)
            j = random.randint(0, n2 - 1)
        
            if (i, j) not in added_coords:
                val = random.randint(1, n2) 
                clue_box.add(i, j, val)
                added_coords.add((i, j))
            
        return clue_box

    return (generate_random_clues,)


@app.cell
def _(Cube, Path, cp_model):
    def solve_sudoku_csp(n, groups):
        """
        R5: O Cérebro. Transforma todos os grupos (linhas, colunas, blocos, pistas)
        num modelo de Problema de Satisfação de Restrições e resolve-o.
        """
        model = cp_model.CpModel() 
        n2 = n * n
    
        # Dicionário para guardar as "incógnitas" que o solver vai ter de descobrir
        grid_vars = {} 

        # 1. CRIAR AS VARIÁVEIS DO JOGO
        for i in range(n2):
            for j in range(n2):
                # Dizemos ao solver: "Esta célula só pode ter valores de 1 a n^2"
                grid_vars[(i, j)] = model.NewIntVar(1, n2, f'Celula_{i}_{j}')

        # 2. APLICAR AS REGRAS (RESTRIÇÕES) AOS GRUPOS
        for group in groups:
            group_vars = [] 
        
            for (i, j), fixed_val in group.cells.items():
                var = grid_vars[(i, j)]
                group_vars.append(var)
            
                # Se a célula tem um valor fixo (é uma pista), obrigamos a incógnita
                # a ser exatamente esse número.
                if fixed_val is not None:
                    model.Add(var == fixed_val)
        
            # A REGRA DE OURO: model.AddAllDifferent obriga a que todas as incógnitas
            # deste grupo tenham números diferentes. Isto resolve linhas, colunas e blocos de uma vez!
            if len(group_vars) > 0:
                model.AddAllDifferent(group_vars)

        # 3. PEDIR AO SOLVER PARA TRABALHAR
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Se encontrou uma solução possível
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            solution = []
            # Reconstrói a matriz com os números que o solver descobriu
            for i in range(n2):
                linha = []
                for j in range(n2):
                    valor_descoberto = solver.Value(grid_vars[(i, j)])
                    linha.append(valor_descoberto)
                solution.append(linha)
            return solution
        else:
            return None # Sinaliza que este conjunto de pistas não tem solução possível

    def build_and_solve_sudoku(n, clues_box):
        """
        R6: Junta as peças todas e cria um puzzle completo.
        Passa todas as instâncias de restrição para o cérebro (solver).
        """
        n2 = n * n
        all_groups = [clues_box] # Começamos a lista de grupos com as pistas geradas
    
        # Criar todas as Linhas e Colunas (usando a classe Path)
        for i in range(n2):
            all_groups.append(Path(n, start=(i, 0), end=(i, n2 - 1))) 
            all_groups.append(Path(n, start=(0, i), end=(n2 - 1, i))) 
        
        # Criar todos os Blocos n x n (usando a classe Cube)
        for block_i in range(n):
            for block_j in range(n):
                all_groups.append(Cube(n, block_i, block_j))
            
        # Mandar tudo para o solver
        return solve_sudoku_csp(n, all_groups)

    return (build_and_solve_sudoku,)


@app.cell
def _(Box, build_and_solve_sudoku, generate_random_clues, mo):
    def run_tests():
        """
        Validação e Testes automáticos exigidos no enunciado.
        Usa blocos 'try' e 'assert' para provar que a lógica não falha.
        Como isto é Marimo, guardamos o log em texto Markdown (mo.md) para renderizar bonito.
        """
        n = 3
        n2 = n * n
        log = ["**A iniciar testes de validação automática...**\n"]
    
        # TESTE 1: Limites (Garantir que a rejeição de coordenadas funciona)
        try:
            grupo_errado = Box(n)
            grupo_errado.add(10, 0) # 10 está fora de limites numa grelha 9x9
            log.append("❌ ERRO no Teste 1: Deixou adicionar célula fora do tabuleiro!")
        except ValueError:
            log.append("✅ Teste 1 (Limites da grelha): Passou com sucesso! Rejeitou coordenadas inválidas.")
        
       # TESTE 2: Geração de Solução
            solution = None
            clues = None
        
            # DECISÃO: Como geramos pistas 100% à sorte, podemos gerar um puzzle logicamente
            # impossível (ex: dois '5' na mesma linha). Por isso, tentamos até 100 vezes.
            for tentativa in range(100):
                # Reduzido para 5 pistas para diminuir a probabilidade de conflito
                clues = generate_random_clues(n, k=5) 
                solution = build_and_solve_sudoku(n, clues)
                if solution is not None:
                    break 
                
            if solution is None:
                log.append("❌ Azar! O gerador criou 100 puzzles logicamente impossíveis seguidos. Volta a correr a célula.")
                return mo.md("  \n".join(log))
        
        log.append("✅ Teste 2 (Encontrar Solução): Passou! Solver encontrou uma grelha válida.")
        
        # TESTE 3: Verificação de Regras Matemáticas
        # O conjunto 'expected_set' tem os números {1, 2, 3, 4, 5, 6, 7, 8, 9}
        expected_set = set(range(1, n2 + 1)) 
    
        # O 'assert' para o código se a afirmação for mentira.
        for i in range(n2):
            linha_atual = set(solution[i][j] for j in range(n2))
            coluna_atual = set(solution[j][i] for j in range(n2))
        
            assert linha_atual == expected_set, f"Erro: Linha {i} não tem os números todos diferentes!"
            assert coluna_atual == expected_set, f"Erro: Coluna {i} não tem os números todos diferentes!"
        
        for (i, j), val in clues.cells.items():
            assert solution[i][j] == val, f"Erro grave: Solver apagou ou alterou a pista ({i},{j})!"
        
        log.append("✅ Teste 3 (Verificar Regras e Pistas): Passou! Linhas, colunas e pistas mantiveram integridade.\n")
    
        # Desenhar Grelha Final para ser visualizada 
        grid_md = ["**Grelha Final Resolvida:**", "```text"]
        for linha in solution:
            grid_md.append(str(linha))
        grid_md.append("```")
    
        return mo.md("  \n".join(log) + "\n\n" + "\n".join(grid_md))

    resultado_testes = run_tests()
    return (resultado_testes,)


@app.cell
def _(resultado_testes):
    # Imprime o resultado dos testes na interface visual do Marimo
    resultado_testes
    return


if __name__ == "__main__":
    app.run()
