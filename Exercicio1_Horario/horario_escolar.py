# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "marimo>=0.25.1",
#     "pandas",
#     "ortools",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path
    import time
    from ortools.sat.python import cp_model

    return Path, cp_model, mo, pd, time


@app.cell
def _(Path, mo, pd):
    view_r8 = mo.md(
        r"""
        ## 1. Importação de Dados (Regra R8)

        **O que fizemos:** O professor pediu para não escrevermos o nome das turmas ou professores diretamente no código (nada de dados "hardcoded"). O código tem de funcionar para qualquer escola.
        Por isso, criámos uma função genérica usando a biblioteca `pandas`. Ela vai à pasta, lê os ficheiros CSV e guarda tudo em tabelas virtuais chamadas DataFrames. Se o ficheiro CSV mudar, o modelo adapta-se logo.
        """
    )

    def carregar_dados(pasta_dados: str):
        caminho = Path(__file__).resolve().parent / pasta_dados
        # O pd.read_csv simplesmente lê o ficheiro de texto e transforma numa tabela fácil de usar
        turmas_df = pd.read_csv(caminho / "turmas.csv")
        disciplinas_df = pd.read_csv(caminho / "disciplinas.csv")
        salas_df = pd.read_csv(caminho / "salas.csv")
        excecoes_df = pd.read_csv(caminho / "disponibilidade_excecoes.csv")
        return turmas_df, disciplinas_df, salas_df, excecoes_df

    turmas, disciplinas, salas, excecoes = carregar_dados("dados")
    return carregar_dados, disciplinas, excecoes, salas, turmas, view_r8


@app.cell
def _(view_r8):
    view_r8
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Modelação do Problema (Regras R1 a R7)


    ### Variáveis e Exceções (R6)
    **A nossa ideia:** O solver precisa de variáveis booleanas (0 ou 1) que cruzam: Turma + Disciplina + Dia + Período + Sala. Se for 1, a aula acontece ali. Se for 0, não acontece.
    Para a regra **R6** (professores indisponíveis), em vez de criarmos milhares de variáveis que dão zero, otimizámos o processo: o código vê a lista de exceções e **nem sequer cria** as variáveis nessas horas. O solver fica muito mais rápido assim.

    ### Regra R1: Limite de turmas
    **A nossa ideia:** Uma turma não se pode dividir ao meio. Fixamos uma turma, um dia e uma hora. A soma de todas as aulas possíveis nesse momento não pode passar de 1 (no máximo têm uma aula).

    ### Regra R2: Carga Horária Semanal
    **A nossa ideia:** A tabela diz que a turma tem X horas de Matemática por semana. Fomos buscar todas as variáveis de Matemática dessa turma na semana toda e dissemos ao solver: a soma disto tudo tem de ser estritamente igual àquele número X.

    ### Regra R3: Espalhar as aulas (Limite diário)
    **A nossa ideia:** Ninguém quer ter 4 horas de Português no mesmo dia. Então, se a disciplina for "normal", o limite diário é 1 aula. Se a tabela disser que tem `duplo_periodo`, o limite passa a 2 aulas por dia. Isto espalha as aulas pela semana.

    ### Regra R4: Blocos Duplos
    **A nossa ideia:** Algumas disciplinas práticas precisam de 2 tempos seguidos (ex: Físico-Química). Um tempo solto não serve. Dissemos ao modelo: "Se meteres uma aula no período P, és obrigado a meter outra colar a ela, ou no P-1 ou no P+1".

    ### Regra R5: Professores
    **A nossa ideia:** Um professor só pode estar numa sala. Num determinado dia e período, somamos todas as aulas que aquele professor pode dar a todas as turmas. A soma final não pode passar de 1.

    ### Regra R7: As Salas
    **A nossa ideia:** Para a tipologia (só Ginásio para Educação Física), resolvemos isso filtrando logo no início. Para a lotação física, somamos todas as turmas que tentam entrar na mesma sala à mesma hora, e limitamos a 1.
    """)
    return


@app.cell
def _(cp_model, pd):
    def criar_modelo(turmas_df, disciplinas_df, salas_df, excecoes_df):
        model = cp_model.CpModel()
        DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex"]
        PERIODOS = list(range(1, 6)) # Cria uma lista de 1 a 5 (os 5 tempos letivos)

        lista_turmas = turmas_df["turma"].tolist()

        # O iterrows() é um comando do Pandas que lê a tabela linha a linha.
        # Aqui estamos a desdobrar salas. Se diz Laboratório com quantidade 2, 
        # criamos "Laboratório_1" e "Laboratório_2" para o solver conseguir distingui-las.
        salas_disponiveis = []
        for _, row in salas_df.iterrows():
            nome_sala = row["sala"]
            for i in range(1, int(row["quantidade"]) + 1):
                salas_disponiveis.append((nome_sala, f"{nome_sala}_{i}"))

        # Aqui guardamos num dicionário as salas certas para cada disciplina
        salas_por_disc = {}
        for _, disc in disciplinas_df.iterrows():
            # O pd.notna() verifica se a célula tem texto. Se não tiver (NaN), usa "Sala Normal"
            s_req = disc["sala_especial"] if pd.notna(disc["sala_especial"]) else "Sala Normal"
            salas_por_disc[disc["disciplina"]] = [
                s_inst for s_nome, s_inst in salas_disponiveis if s_nome == s_req
            ]

        # O comando zip() junta duas colunas. Aqui juntamos a coluna das disciplinas 
        # à coluna dos professores, criando um dicionário {disciplina: professor}
        prof_da_disc = dict(zip(disciplinas_df["disciplina"], disciplinas_df["professor"]))
        cargas = dict(zip(disciplinas_df["disciplina"], disciplinas_df["carga_semanal"]))
        duplo = dict(zip(disciplinas_df["disciplina"], disciplinas_df["duplo_periodo"]))

        # Guardamos as exceções num 'set'  porque as pesquisas nele são muito rápidas
        indisp = set(zip(excecoes_df["professor"], excecoes_df["dia"], excecoes_df["periodo"].astype(int)))

        # CRIAÇÃO DAS VARIÁVEIS (E aplicação da Regra 6)
        x = {}
        for t in lista_turmas:
            for d, salas_comp in salas_por_disc.items():
                prof = prof_da_disc[d]
                for dia in DIAS:
                    for p in PERIODOS:
                        # Regra 6: Se o trio (professor, dia, periodo) estiver na lista de exceções,
                        # fazemos 'continue', ou seja, saltamos para a próxima e não criamos variável.
                        if (prof, dia, p) in indisp:
                            continue
                        for s_inst in salas_comp:
                            x[t, d, dia, p, s_inst] = model.NewBoolVar(f"x_{t}_{d}_{dia}_{p}_{s_inst}")

        # Uma função simples para procurar variáveis. Se ela não existir (foi cortada na R6), devolve 'None'
        def X(t, d, dia, p, s_inst):
            return x.get((t, d, dia, p, s_inst), None)

        # Regra 1: Uma turma não pode ter 2 aulas ao mesmo tempo
        for t in lista_turmas:
            for dia in DIAS:
                for p in PERIODOS:
                    # Esta sintaxe [x for y in z se ...] constrói uma lista de forma rápida.
                    # Filtramos com 'is not None' para evitar que o solver dê erro com as variáveis que cortámos.
                    vars_tempo = [X(t, d, dia, p, s) for d in salas_por_disc for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_tempo:
                        # AddAtMostOne é uma função própria do solver que significa "a soma disto tem de dar 0 ou 1"
                        model.AddAtMostOne(vars_tempo)

        # Regra 2: Cumprir as horas semanais exatas
        for t in lista_turmas:
            for d, carga in cargas.items():
                vars_disc = [X(t, d, dia, p, s) for dia in DIAS for p in PERIODOS for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                # Se for 1 aula, o AddExactlyOne é mais rápido. Se for mais, fazemos a soma normal matemática.
                model.AddExactlyOne(vars_disc) if int(carga) == 1 else model.Add(sum(vars_disc) == int(carga))

        # Regra 3: Limite de aulas por dia (para espalhar as aulas pela semana)
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                limite_diario = 2 if str(is_duplo).strip().lower() == "sim" else 1
                for dia in DIAS:
                    vars_dia = [X(t, d, dia, p, s) for p in PERIODOS for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_dia:
                        model.Add(sum(vars_dia) <= limite_diario)

        # Regra 4: Blocos Duplos (aulas práticas seguidas). Nesta parte foi utilizado o auxilio de um LLM
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                if str(is_duplo).strip().lower() == "sim":
                    for dia in DIAS:
                        for p in PERIODOS:
                            vars_p = [X(t, d, dia, p, s) for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                            if not vars_p:
                                continue
                            vars_vizinhos = []
                            # Usamos p>1 e p<5 para não tentar pesquisar os períodos 0 ou 6 (que não existem)
                            if p > 1:
                                vars_vizinhos.extend([X(t, d, dia, p - 1, s) for s in salas_por_disc[d] if X(t, d, dia, p - 1, s) is not None])
                            if p < 5:
                                vars_vizinhos.extend([X(t, d, dia, p + 1, s) for s in salas_por_disc[d] if X(t, d, dia, p + 1, s) is not None])
                            # Obriga a ter uma aula no período vizinho se houver aula no período atual
                            model.Add(sum(vars_vizinhos) >= sum(vars_p))

        # Regra 5: O professor só tem o dom de estar numa sala de cada vez
        professores = disciplinas_df["professor"].unique()
        for prof in professores:
            discs_prof = [d for d, pr in prof_da_disc.items() if pr == prof]
            for dia in DIAS:
                for p in PERIODOS:
                    vars_prof = [X(t, d, dia, p, s) for t in lista_turmas for d in discs_prof for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_prof:
                        model.AddAtMostOne(vars_prof)

        # Regra 7: Uma sala física real só aguenta com 1 turma lá dentro
        todas_instancias = [s_inst for _, s_inst in salas_disponiveis]
        for s_inst in todas_instancias:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_sala = [X(t, d, dia, p, s_inst) for t in lista_turmas for d in salas_por_disc if s_inst in salas_por_disc[d] and X(t, d, dia, p, s_inst) is not None]
                    if vars_sala:
                        model.AddAtMostOne(vars_sala)

        # No final, devolvemos a "fábrica" do modelo montada e a lista de variáveis
        return model, x

    return (criar_modelo,)


@app.cell
def _(cp_model, criar_modelo, disciplinas, excecoes, mo, pd, salas, turmas):
    mo.md("### Resolução e Apresentação do Horário Inicial ($H_0$)")

    model_h0, vars_h0 = criar_modelo(turmas, disciplinas, salas, excecoes)
    solver_h0 = cp_model.CpSolver()
    solver_h0.parameters.max_time_in_seconds = 30.0
    status_h0 = solver_h0.Solve(model_h0)

    # Se o solver encontrar um horário viável, guardamos apenas as variáveis que ficaram a 1 (as aulas que vão acontecer)
    registos_h0 = []
    if status_h0 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (t_val, d_val, dia_val, p_val, s_val), var in vars_h0.items():
            if solver_h0.Value(var) == 1:
                registos_h0.append({"turma": t_val, "disciplina": d_val, "dia": dia_val, "periodo": p_val, "sala": s_val})

    df_h0 = pd.DataFrame(registos_h0)

    # Função para desenhar a tabela bonita do horário
    def visualizar_horario(df, turma_alvo):
        if df.empty:
            return pd.DataFrame()
        sub = df[df["turma"] == turma_alvo]
        # Cria uma grelha vazia só com os dias e períodos, preenchida com "-"
        tabela = pd.DataFrame(index=list(range(1, 6)), columns=["Seg", "Ter", "Qua", "Qui", "Sex"]).fillna("-")
        for _, row in sub.iterrows():
            tabela.loc[row["periodo"], row["dia"]] = f"{row['disciplina']} ({row['sala']})"
        return tabela

    turma_exemplo = turmas["turma"].iloc[0] if not turmas.empty else "N/A"
    horario_ui = visualizar_horario(df_h0, turma_exemplo)

    view_h0 = mo.vstack([
        mo.md(f"**Status da resolução inicial:** {'Ótimo/Viável' if status_h0 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 'Inviável'}"),
        mo.md(f"**Demonstração - Horário da {turma_exemplo}:**"),
        mo.ui.table(horario_ui) if not horario_ui.empty else mo.md("Nenhum horário gerado.")
    ])
    return df_h0, solver_h0, vars_h0, view_h0


@app.cell
def _(view_h0):
    view_h0
    return


@app.cell
def _(cp_model, criar_modelo, disciplinas, excecoes, mo, salas, turmas):
    view_opt_md = mo.md(
        r"""
        ## 3. Otimização (O1) - Minimizar Buracos dos Professores

        **A nossa ideia:** Para evitar que os professores fiquem a apanhar secas (tempos livres no meio do horário), criámos variáveis falsas para detetar isso. Se o professor tiver aula antes e depois do período X, mas no período X não tiver nada, isso conta como "1 buraco". Depois mandamos o solver tentar que essa conta dê o valor mais perto de zero possível.
        Nesta parte foi utilizado o auxilio de um LLM
        """
    )

    model_opt, vars_opt = criar_modelo(turmas, disciplinas, salas, excecoes)

    professores_opt = disciplinas["professor"].unique()
    prof_da_disc_opt = dict(zip(disciplinas["disciplina"], disciplinas["professor"]))
    dias_opt = ["Seg", "Ter", "Qua", "Qui", "Sex"]

    buracos = []
    for prof in professores_opt:
        discs_prof_opt = [d for d, p in prof_da_disc_opt.items() if p == prof]
        for dia in dias_opt:
            for p_opt in range(2, 5): 

                vars_antes = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] < p_opt]
                vars_depois = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] > p_opt]
                vars_agora = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] == p_opt]

                # 1. Se não pode ter aulas antes OU depois, é impossível ser buraco. Saltamos.
                if not vars_antes or not vars_depois:
                    continue

                tem_antes = model_opt.NewBoolVar(f"antes_{prof}_{dia}_{p_opt}")
                tem_depois = model_opt.NewBoolVar(f"depois_{prof}_{dia}_{p_opt}")
                tem_agora = model_opt.NewBoolVar(f"agora_{prof}_{dia}_{p_opt}")

                model_opt.AddMaxEquality(tem_antes, vars_antes)
                model_opt.AddMaxEquality(tem_depois, vars_depois)

                # 2. Se a lista 'agora' estiver vazia, significa que ele não pode dar aula neste período.
                # Logo, tem_agora é obrigatoriamente 0. Mas continuamos a testar o buraco!
                if vars_agora:
                    model_opt.AddMaxEquality(tem_agora, vars_agora)
                else:
                    model_opt.Add(tem_agora == 0)

                # 3. A tua lógica original mantida intacta
                buraco = model_opt.NewBoolVar(f"buraco_{prof}_{dia}_{p_opt}")
                model_opt.AddBoolAnd([tem_antes, tem_depois, tem_agora.Not()]).OnlyEnforceIf(buraco)
                model_opt.AddBoolOr([tem_antes.Not(), tem_depois.Not(), tem_agora]).OnlyEnforceIf(buraco.Not())
                buracos.append(buraco)

    model_opt.Minimize(sum(buracos))
    solver_opt = cp_model.CpSolver()
    solver_opt.parameters.max_time_in_seconds = 30.0
    status_opt = solver_opt.Solve(model_opt)

    gaps_encontrados = solver_opt.ObjectiveValue() if status_opt in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "N/A"

    view_opt = mo.vstack([
        view_opt_md,
        mo.md(f"**Resultado:** Buracos (Gaps) penalizados no horário: {gaps_encontrados}")
    ])
    return (view_opt,)


@app.cell
def _(view_opt):
    view_opt
    return


@app.cell
def _(
    carregar_dados,
    cp_model,
    criar_modelo,
    mo,
    pd,
    solver_h0,
    time,
    vars_h0,
):
    view_inc_md = mo.md(
        r"""
        ## 4. Construção Incremental (Regra R9)

        **A nossa ideia:** Se um professor ficar doente a meio do ano, não podemos deitar o horário todo da escola para o lixo e refazer do zero (isso seria um caos para os alunos). O que fizemos foi ler os dados novos (`dados_v2`) e usar o horário antigo como uma pista/palpite (*Warm-Start*). Dissemos ao solver: "tenta arranjar a confusão alterando o mínimo de aulas possível".
        Nesta parte foi utilizado o auxilio de um LLM
        """
    )

    try:
        turmas_v2, disc_v2, salas_v2, excecoes_v2 = carregar_dados("dados_v2")

        model_h1, vars_h1 = criar_modelo(turmas_v2, disc_v2, salas_v2, excecoes_v2)

        alteracoes = []
        for k, v in vars_h1.items():
            if k in vars_h0:
                # Vamos ver como estava esta aula no horário antigo
                val_antigo = solver_h0.Value(vars_h0[k])

                # AddHint dá uma "pista" ao solver para tentar usar a solução antiga
                model_h1.AddHint(v, val_antigo)

                # Se a aula estava marcada (1), criamos uma variável "mudou" que dispara 
                # e fica a 1 caso o solver seja forçado a movê-la para resolver o conflito
                if val_antigo == 1:
                    mudou = model_h1.NewBoolVar(f"mudou_{k}")
                    model_h1.Add(mudou == 1 - v)
                    alteracoes.append(mudou)

        # Pedimos para manter o número de alterações o mais perto do zero possível
        model_h1.Minimize(sum(alteracoes))

        solver_h1 = cp_model.CpSolver()
        solver_h1.parameters.max_time_in_seconds = 20.0
        t0_inc = time.time()
        status_h1 = solver_h1.Solve(model_h1)
        tempo_inc = time.time() - t0_inc
        aulas_mudadas = solver_h1.ObjectiveValue() if status_h1 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "N/A"

        # Agora comparamos com resolver do zero, para provar que a nossa ideia é melhor
        model_zero, _ = criar_modelo(turmas_v2, disc_v2, salas_v2, excecoes_v2)
        solver_zero = cp_model.CpSolver()
        solver_zero.parameters.max_time_in_seconds = 20.0
        t0_zero = time.time()
        solver_zero.Solve(model_zero)
        tempo_zero = time.time() - t0_zero

        df_comparacao = pd.DataFrame([
            {"Estratégia": "Resolver do Zero (Mau)", "Tempo (s)": round(tempo_zero, 4), "Aulas Alteradas": "Máximas (Sem Controlo)"},
            {"Estratégia": "Usar a Solução Antiga (Bom)", "Tempo (s)": round(tempo_inc, 4), "Aulas Alteradas": int(aulas_mudadas) if aulas_mudadas != "N/A" else "N/A"}
        ])

        view_inc = mo.vstack([
            view_inc_md,
            mo.md("### Comparação de Desempenho"),
            mo.ui.table(df_comparacao)
        ])

    except Exception as e:
        view_inc = mo.vstack([view_inc_md, mo.md(f"**Aviso:** O teste falhou. Confirma se tens a pasta 'dados_v2' criada. Erro: {e}")])
    return (view_inc,)


@app.cell
def _(view_inc):
    view_inc
    return


@app.cell
def _():
    return


@app.cell
def _(
    cp_model,
    criar_modelo,
    df_h0,
    disciplinas,
    excecoes,
    mo,
    pd,
    salas,
    turmas,
):
    view_val_md = mo.md(
        r"""
        ## 5. Conjunto de testes sob cada regra e Validação Automática

        **O que fazemos aqui:** Não vamos confiar cegamente no computador. Criámos um "auditor" que pega no horário final e verifica, regra a regra, se há algum erro. Se o modelo falhar em alguma coisa, este teste vai apitá-lo. Também adicionamos uma turma fantasma para provar que o código aguenta crescer.
        """
    )

    def validador_automatico(df, df_disc, df_exc):
        if df.empty:
            return ["Não há horário para validar."]
        erros = []

        # TESTE R1: A turma está em duas aulas ao mesmo tempo?
        # O duplicated() procura linhas repetidas para a mesma turma, no mesmo dia e período.
        if df.duplicated(subset=["turma", "dia", "periodo"]).sum() > 0:
            erros.append("Falha na R1: Turma com aulas sobrepostas ao mesmo tempo.")

        # TESTE R2: A carga semanal está certa?
        cargas = dict(zip(df_disc["disciplina"], df_disc["carga_semanal"]))
        for (t, d), grupo in df.groupby(["turma", "disciplina"]):
            if len(grupo) != int(cargas.get(d, 0)):
                erros.append(f"Falha na R2: A turma {t} tem um número errado de aulas a {d}.")

        # TESTE R3: O limite de aulas por dia foi respeitado?
        duplo = dict(zip(df_disc["disciplina"], df_disc["duplo_periodo"]))
        for (t, d, dia), grupo in df.groupby(["turma", "disciplina", "dia"]):
            limite = 2 if str(duplo.get(d, "nao")).strip().lower() == "sim" else 1
            if len(grupo) > limite:
                erros.append(f"Falha na R3: A turma {t} ultrapassou o limite diário de {d} à {dia}.")

        # TESTE R4: Os blocos duplos estão juntos (contíguos)?
        for (t, d, dia), grupo in df.groupby(["turma", "disciplina", "dia"]):
            is_duplo = str(duplo.get(d, "nao")).strip().lower() == "sim"
            if is_duplo and len(grupo) == 2:
                # Ordena os períodos. Ex: se tem aula no 2 e no 3, 3-2 = 1 (estão colados).
                periodos = sorted(grupo["periodo"].tolist())
                if periodos[1] - periodos[0] != 1:
                    erros.append(f"Falha na R4: A turma {t} tem {d} num bloco separado à {dia}.")
            # Se for bloco duplo e só tiver 1 aula nesse dia, também está errado.
            elif is_duplo and len(grupo) == 1:
                erros.append(f"Falha na R4: A turma {t} tem um tempo isolado de {d} à {dia}.")

        # Prepara uma tabela virtual para conseguir testar os professores
        prof_disc_val = dict(zip(df_disc["disciplina"], df_disc["professor"]))
        df_teste = df.copy()
        df_teste["professor"] = df_teste["disciplina"].map(prof_disc_val)

        # TESTE R5: O professor está em duas salas ao mesmo tempo?
        if df_teste.duplicated(subset=["professor", "dia", "periodo"]).sum() > 0:
            erros.append("Falha na R5: Professor tem duas aulas marcadas para a mesma hora.")

        # TESTE R6: Marcaram aulas na hora de folga do professor?
        # O merge() cruza o nosso horário com o ficheiro de exceções. Se houver cruzamento, é erro.
        df_exc_check = df_teste.merge(df_exc, on=["professor", "dia", "periodo"], how="inner")
        if not df_exc_check.empty:
            erros.append("Falha na R6: Aula marcada na hora de indisponibilidade de um professor.")

        # TESTE R7: Puseram duas turmas na mesma sala física à mesma hora?
        if df.duplicated(subset=["sala", "dia", "periodo"]).sum() > 0:
            erros.append("Falha na R7: Duas turmas foram alocadas exatamente à mesma sala.")

        # Se a lista de erros estiver vazia, passámos em tudo!
        return erros if erros else ["✅ A auditoria testou as regras R1 a R7 com sucesso. Nenhum erro encontrado! O horário está perfeito."]

    # Executar a bateria de testes
    resultado_validacao = validador_automatico(df_h0, disciplinas, excecoes)
    texto_auditoria = "\n\n".join(resultado_validacao)

    # Adicionar uma turma fictícia para testar a escalabilidade (o código não quebra se a escola crescer)
    nova_turma = pd.DataFrame([{"turma": "Turma_Teste_Inventada"}])
    turmas_teste = pd.concat([turmas, nova_turma], ignore_index=True)

    model_teste, vars_teste = criar_modelo(turmas_teste, disciplinas, salas, excecoes)
    solver_teste = cp_model.CpSolver()
    solver_teste.parameters.max_time_in_seconds = 10.0
    status_teste = solver_teste.Solve(model_teste)
    viabilidade_teste = "Viável (Funcionou)" if status_teste in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "Inviável"

    view_val = mo.vstack([
        view_val_md,
        mo.md(f"**Resultado da Auditoria:**\n{texto_auditoria}"),
        mo.md(f"**Teste de Crescimento (Mais 1 Turma):** O modelo adaptou-se automaticamente e a resolução deu {viabilidade_teste}.")
    ])
    return (view_val,)


@app.cell
def _(view_val):
    view_val
    return


@app.cell
def _(df_h0, mo, pd, turmas):
    mo.md("## 6. Visualização Completa dos Horários")
    visuais = []

    # Aqui fazemos um ciclo FOR por todas as turmas que o modelo encontrou.
    # Por cada turma, filtramos a tabela geral e desenhamos a grelha bonitinha.
    for turma_nome in turmas["turma"]:
        sub = df_h0[df_h0["turma"] == turma_nome]

        tabela = pd.DataFrame(
            index=list(range(1, 6)), 
            columns=["Seg", "Ter", "Qua", "Qui", "Sex"]
        ).fillna("-")

        for _, row in sub.iterrows():
            tabela.loc[row["periodo"], row["dia"]] = f"{row['disciplina']} ({row['sala']})"

        visuais.append(mo.md(f"### Horário da {turma_nome}"))
        visuais.append(mo.ui.table(tabela))
        visuais.append(mo.md("---")) 

    # O vstack simplesmente empilha os horários uns por cima dos outros para mostrar no ecrã
    ver_todos = mo.vstack(visuais)
    return (ver_todos,)


@app.cell
def _(ver_todos):
    ver_todos
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 7. Documentação e Entrega

    ### Porque escolhemos o OR-Tools (CP-SAT)?
    Decidimos usar a biblioteca **CP-SAT Solver da Google OR-Tools** para resolver este trabalho prático de *Timetabling*. A Programação por Restrições (CP) foi a melhor opção porque nos deixou escrever regras de negócio diretas e lógicas (como obrigar aos blocos duplos contíguos na R4 e impedir furos temporais na R6) sem termos de usar matemática muito complicada. Além disso, ligou-se de forma muito fácil às tabelas de dados do Pandas que usámos.

    ### Porque é que a Estratégia Incremental é importante (R9)?
    No mundo real das escolas, há imprevistos. Se o programa refizesse o horário todo a partir do zero sempre que um professor ficasse de baixa de tarde, isso seria um pesadelo: os alunos viam as suas rotinas completamente baralhadas.
    Ao dizermos ao solver para olhar para o horário antigo como uma pista ("Warm-Start") e ao pedirmos para ele alterar o mínimo de aulas possível, conseguimos consertar o conflito como uma operação cirúrgica, afetando apenas as pessoas estritamente necessárias.

    ### Uso de Ferramentas LLM (Registo de Diálogo)
    O link para o diálogo integral com o LLM está disponível aqui: **https://share.gemini.google/bO0gYMhPdudN**

    Durante o desenvolvimento, o uso do LLM focou-se em dois pilares avaliados:

    1. **Adequação e Flexibilidade:** O LLM foi usado não para reescrever a lógica de negócio do zero, mas para integrar a lógica de CP-SAT (Warm-Start para $H_1$) dentro da arquitetura do Marimo. Ajudou-nos a adaptar a leitura dinâmica de duas fontes de dados diferentes (`dados/` e `dados_v2/`), provando a flexibilidade do sistema a novos requisitos.

    2. **Resolução de Problemas Específicos do Framework:** Devido à natureza reativa do Marimo, deparámo-nos com erros de redefinição de variáveis entre células (`NameError`). O LLM foi crucial para identificar o problema de âmbito (*scope*) das variáveis e reestruturar os ciclos de extração de dados sem comprometer a integridade do modelo matemático.

    3. **O modelo de linguagem (LLM) foi utilizado como ferramenta de suporte à depuração (debugging). A partir da explicação estrutural dos erros lógicos identificados na versão inicial do código, a solução final foi formulada e implementada de forma autónoma
    """)
    return


if __name__ == "__main__":
    app.run()
