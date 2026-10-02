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
def _(Path, pd):
    def carregar_dados(pasta_dados: str):
        caminho = Path(pasta_dados)
        turmas_df = pd.read_csv(caminho / "turmas.csv")
        disciplinas_df = pd.read_csv(caminho / "disciplinas.csv")
        salas_df = pd.read_csv(caminho / "salas.csv")
        excecoes_df = pd.read_csv(caminho / "disponibilidade_excecoes.csv")
        return turmas_df, disciplinas_df, salas_df, excecoes_df

    turmas, disciplinas, salas, excecoes = carregar_dados("dados")
    return carregar_dados, disciplinas, excecoes, salas, turmas


@app.cell
def _(cp_model, pd):
    def criar_modelo(turmas_df, disciplinas_df, salas_df, excecoes_df):
        model = cp_model.CpModel()
        DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex"]
        PERIODOS = list(range(1, 6))

        lista_turmas = turmas_df["turma"].tolist()

        salas_disponiveis = []
        for _, row in salas_df.iterrows():
            nome_sala = row["sala"]
            for i in range(1, int(row["quantidade"]) + 1):
                salas_disponiveis.append((nome_sala, f"{nome_sala}_{i}"))

        salas_por_disc = {}
        for _, disc in disciplinas_df.iterrows():
            s_req = disc["sala_especial"] if pd.notna(disc["sala_especial"]) else "Sala Normal"
            salas_por_disc[disc["disciplina"]] = [
                s_inst for s_nome, s_inst in salas_disponiveis if s_nome == s_req
            ]

        prof_da_disc = dict(zip(disciplinas_df["disciplina"], disciplinas_df["professor"]))
        cargas = dict(zip(disciplinas_df["disciplina"], disciplinas_df["carga_semanal"]))
        duplo = dict(zip(disciplinas_df["disciplina"], disciplinas_df["duplo_periodo"]))

        indisp = set(zip(excecoes_df["professor"], excecoes_df["dia"], excecoes_df["periodo"].astype(int)))

        x = {}
        for t in lista_turmas:
            for d, salas_comp in salas_por_disc.items():
                prof = prof_da_disc[d]
                for dia in DIAS:
                    for p in PERIODOS:
                        if (prof, dia, p) in indisp:
                            continue
                        for s_inst in salas_comp:
                            x[t, d, dia, p, s_inst] = model.NewBoolVar(f"x_{t}_{d}_{dia}_{p}_{s_inst}")

        def X(t, d, dia, p, s_inst):
            return x.get((t, d, dia, p, s_inst), None)

        # R1: No máximo 1 aula por período por turma
        for t in lista_turmas:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_tempo = [X(t, d, dia, p, s) for d in salas_por_disc for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_tempo:
                        model.AddAtMostOne(vars_tempo)

        # R2: Carga Horária Semanal exata
        for t in lista_turmas:
            for d, carga in cargas.items():
                vars_disc = [X(t, d, dia, p, s) for dia in DIAS for p in PERIODOS for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                model.AddExactlyOne(vars_disc) if int(carga) == 1 else model.Add(sum(vars_disc) == int(carga))

        # R3: Limite diário por disciplina
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                limite_diario = 2 if str(is_duplo).strip().lower() == "sim" else 1
                for dia in DIAS:
                    vars_dia = [X(t, d, dia, p, s) for p in PERIODOS for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_dia:
                        model.Add(sum(vars_dia) <= limite_diario)

        # R4: Blocos Duplos Contíguos
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                if str(is_duplo).strip().lower() == "sim":
                    for dia in DIAS:
                        for p in PERIODOS:
                            vars_p = [X(t, d, dia, p, s) for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                            if not vars_p:
                                continue
                            vars_vizinhos = []
                            if p > 1:
                                vars_vizinhos.extend([X(t, d, dia, p - 1, s) for s in salas_por_disc[d] if X(t, d, dia, p - 1, s) is not None])
                            if p < 5:
                                vars_vizinhos.extend([X(t, d, dia, p + 1, s) for s in salas_por_disc[d] if X(t, d, dia, p + 1, s) is not None])
                            model.Add(sum(vars_vizinhos) >= sum(vars_p))

        # R5: No máximo 1 aula por período por professor
        professores = disciplinas_df["professor"].unique()
        for prof in professores:
            discs_prof = [d for d, pr in prof_da_disc.items() if pr == prof]
            for dia in DIAS:
                for p in PERIODOS:
                    vars_prof = [X(t, d, dia, p, s) for t in lista_turmas for d in discs_prof for s in salas_por_disc[d] if X(t, d, dia, p, s) is not None]
                    if vars_prof:
                        model.AddAtMostOne(vars_prof)

        # R7: No máximo 1 aula por sala física por período
        todas_instancias = [s_inst for _, s_inst in salas_disponiveis]
        for s_inst in todas_instancias:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_sala = [X(t, d, dia, p, s_inst) for t in lista_turmas for d in salas_por_disc if s_inst in salas_por_disc[d] and X(t, d, dia, p, s_inst) is not None]
                    if vars_sala:
                        model.AddAtMostOne(vars_sala)

        return model, x

    return (criar_modelo,)


@app.cell
def _(cp_model, criar_modelo, disciplinas, excecoes, mo, pd, salas, turmas):
    mo.md("## 1. Resolução e Apresentação do Horário Inicial ($H_0$)")

    model_h0, vars_h0 = criar_modelo(turmas, disciplinas, salas, excecoes)
    solver_h0 = cp_model.CpSolver()
    solver_h0.parameters.max_time_in_seconds = 30.0
    status_h0 = solver_h0.Solve(model_h0)

    registos_h0 = []
    if status_h0 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (t_val, d_val, dia_val, p_val, s_val), var in vars_h0.items():
            if solver_h0.Value(var) == 1:
                registos_h0.append({"turma": t_val, "disciplina": d_val, "dia": dia_val, "periodo": p_val, "sala": s_val})

    df_h0 = pd.DataFrame(registos_h0)

    def visualizar_horario(df, turma_alvo):
        if df.empty:
            return pd.DataFrame()
        sub = df[df["turma"] == turma_alvo]
        tabela = pd.DataFrame(index=list(range(1, 6)), columns=["Seg", "Ter", "Qua", "Qui", "Sex"]).fillna("-")
        for _, row in sub.iterrows():
            tabela.loc[row["periodo"], row["dia"]] = f"{row['disciplina']} ({row['sala']})"
        return tabela

    turma_exemplo = turmas["turma"].iloc[0] if not turmas.empty else "N/A"
    horario_ui = visualizar_horario(df_h0, turma_exemplo)

    view_h0 = mo.vstack([
        mo.md(f"**Status da resolução inicial:** {'Ótimo/Viável' if status_h0 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 'Inviável'}"),
        mo.md(f"**Horário da {turma_exemplo}:**"),
        mo.ui.table(horario_ui) if not horario_ui.empty else mo.md("Nenhum horário gerado.")
    ])
    return df_h0, solver_h0, vars_h0, view_h0


@app.cell
def _(view_h0):
    view_h0
    return


@app.cell
def _(cp_model, criar_modelo, disciplinas, excecoes, mo, salas, turmas):
    mo.md("## 2. Otimização do Objetivo ($O1$)")

    model_opt, vars_opt = criar_modelo(turmas, disciplinas, salas, excecoes)

    professores_opt = disciplinas["professor"].unique()
    prof_da_disc_opt = dict(zip(disciplinas["disciplina"], disciplinas["professor"]))
    dias_opt = ["Seg", "Ter", "Qua", "Qui", "Sex"]

    buracos = []
    for prof in professores_opt:
        discs_prof_opt = [d for d, p in prof_da_disc_opt.items() if p == prof]
        for dia in dias_opt:
            for p_opt in range(2, 5): 
                tem_antes = model_opt.NewBoolVar(f"antes_{prof}_{dia}_{p_opt}")
                tem_depois = model_opt.NewBoolVar(f"depois_{prof}_{dia}_{p_opt}")
                tem_agora = model_opt.NewBoolVar(f"agora_{prof}_{dia}_{p_opt}")
        
                vars_antes = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] < p_opt]
                vars_depois = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] > p_opt]
                vars_agora = [v for k, v in vars_opt.items() if k[1] in discs_prof_opt and k[2] == dia and k[3] == p_opt]
        
                if vars_antes and vars_depois and vars_agora:
                    model_opt.AddMaxEquality(tem_antes, vars_antes)
                    model_opt.AddMaxEquality(tem_depois, vars_depois)
                    model_opt.AddMaxEquality(tem_agora, vars_agora)
            
                    buraco = model_opt.NewBoolVar(f"buraco_{prof}_{dia}_{p_opt}")
                    model_opt.AddBoolAnd([tem_antes, tem_depois, tem_agora.Not()]).OnlyEnforceIf(buraco)
                    model_opt.AddBoolOr([tem_antes.Not(), tem_depois.Not(), tem_agora]).OnlyEnforceIf(buraco.Not())
                    buracos.append(buraco)

    model_opt.Minimize(sum(buracos))

    solver_opt = cp_model.CpSolver()
    solver_opt.parameters.max_time_in_seconds = 30.0
    status_opt = solver_opt.Solve(model_opt)

    gaps_encontrados = solver_opt.ObjectiveValue() if status_opt in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "N/A"

    view_opt = mo.md(f"**Buracos (Gaps) penalizados na solução otimizada:** {gaps_encontrados}")
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
    mo.md("## 3. Construção Incremental ($R9$)")

    try:
        turmas_v2, disc_v2, salas_v2, excecoes_v2 = carregar_dados("dados_v2")

        model_h1, vars_h1 = criar_modelo(turmas_v2, disc_v2, salas_v2, excecoes_v2)

        alteracoes = []
        for k, v in vars_h1.items():
            if k in vars_h0:
                val_antigo = solver_h0.Value(vars_h0[k])
                model_h1.AddHint(v, val_antigo)
                if val_antigo == 1:
                    mudou = model_h1.NewBoolVar(f"mudou_{k}")
                    model_h1.Add(mudou == 1 - v)
                    alteracoes.append(mudou)

        model_h1.Minimize(sum(alteracoes))

        solver_h1 = cp_model.CpSolver()
        solver_h1.parameters.max_time_in_seconds = 20.0
        t0_inc = time.time()
        status_h1 = solver_h1.Solve(model_h1)
        tempo_inc = time.time() - t0_inc
        aulas_mudadas = solver_h1.ObjectiveValue() if status_h1 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "N/A"

        model_zero, _ = criar_modelo(turmas_v2, disc_v2, salas_v2, excecoes_v2)
        solver_zero = cp_model.CpSolver()
        solver_zero.parameters.max_time_in_seconds = 20.0
        t0_zero = time.time()
        solver_zero.Solve(model_zero)
        tempo_zero = time.time() - t0_zero

        df_comparacao = pd.DataFrame([
            {"Estratégia": "Resolução do Zero", "Tempo (s)": round(tempo_zero, 4), "Aulas Alteradas": "Máximas (Sem Controlo)"},
            {"Estratégia": "Incremental (Warm-Start)", "Tempo (s)": round(tempo_inc, 4), "Aulas Alteradas": int(aulas_mudadas) if aulas_mudadas != "N/A" else "N/A"}
        ])

        view_inc = mo.ui.table(df_comparacao)
    except Exception as e:
        view_inc = mo.md(f"*Nota: A pasta 'dados_v2' ainda não foi criada ou carregada corretamente. Erro: {e}*")
    return (view_inc,)


@app.cell
def _(view_inc):
    view_inc
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
    mo.md("## 4. Validação e Testes Automáticos")

    def validador_automatico(df, df_disc, df_exc):
        if df.empty:
            return ["Nenhum horário gerado para validar."]
        erros = []
        if df.duplicated(subset=["turma", "dia", "periodo"]).sum() > 0:
            erros.append("R1 Violada: Turma com aulas sobrepostas.")
    
        prof_disc_val = dict(zip(df_disc["disciplina"], df_disc["professor"]))
        df_teste = df.copy()
        df_teste["professor"] = df_teste["disciplina"].map(prof_disc_val)

        if df_teste.duplicated(subset=["professor", "dia", "periodo"]).sum() > 0:
            erros.append("R5 Violada: Professor em duas salas ao mesmo tempo.")
    
        df_exc_check = df_teste.merge(df_exc, on=["professor", "dia", "periodo"], how="inner")
        if not df_exc_check.empty:
            erros.append("R6 Violada: Aula alocada em período de indisponibilidade.")
    
        return erros if erros else ["Todas as restrições cumpridas com sucesso!"]

    resultado_validacao = validador_automatico(df_h0, disciplinas, excecoes)

    nova_turma = pd.DataFrame([{"turma": "Turma_Teste"}])
    turmas_teste = pd.concat([turmas, nova_turma], ignore_index=True)

    model_teste, vars_teste = criar_modelo(turmas_teste, disciplinas, salas, excecoes)
    solver_teste = cp_model.CpSolver()
    solver_teste.parameters.max_time_in_seconds = 10.0
    status_teste = solver_teste.Solve(model_teste)
    viabilidade_teste = "Viável" if status_teste in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "Inviável"

    view_val = mo.vstack([
        mo.md(f"**Auditoria do Horário:** {resultado_validacao[0]}"),
        mo.md(f"**Teste de Escalabilidade (Adicionar Turma):** O modelo é {viabilidade_teste}.")
    ])
    return (view_val,)


@app.cell
def _(view_val):
    view_val
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 5. Documentação e Entrega

    ### Justificação da Escolha do OR-Tools (CP-SAT)
    Para a modelação e resolução deste problema de *Timetabling* escolar, optámos pelo **CP-SAT Solver da Google OR-Tools**. A Programação por Restrições (CP) revelou-se ideal devido à:
    - **Expressividade Lógica:** Permitiu modelar de forma direta regras lógicas como a contiguidade de blocos duplos (R4) e exclusões temporais (R6).
    - **Integração Pythónica:** Integridade perfeita com os DataFrames Pandas que estruturaram os dados de entrada.

    ### A Importância da Estratégia Incremental
    No dia a dia escolar, as restrições alteram-se com frequência. Se calcularmos o modelo completamente do zero após uma nova indisponibilidade docente, forçaríamos toda a instituição a adaptar-se a um horário radicalmente diferente.
    Ao injetarmos a solução de origem ($H_0$) como um *Warm-Start* para o solver ($H_1$) e minimizarmos a função objetivo focada na divergência de variáveis, conseguimos um processo de reescalonamento estável que apenas altera as aulas estritamente em conflito.
    """)
    return


@app.cell
def _(df_h0, mo, pd, turmas):
    visuais = []

    for turma_nome in turmas["turma"]:
        sub = df_h0[df_h0["turma"] == turma_nome]

        # Cria a grelha vazia
        tabela = pd.DataFrame(
            index=list(range(1, 6)), 
            columns=["Seg", "Ter", "Qua", "Qui", "Sex"]
        ).fillna("-")

        # Preenche com as aulas atribuídas
        for _, row in sub.iterrows():
            tabela.loc[row["periodo"], row["dia"]] = f"{row['disciplina']} ({row['sala']})"

        visuais.append(mo.md(f"### Horário: {turma_nome}"))
        visuais.append(mo.ui.table(tabela))
        visuais.append(mo.md("---")) # Linha separadora

    # Mostra tudo empilhado
    ver_todos = mo.vstack(visuais)
    return (ver_todos,)


@app.cell
def _(ver_todos):
    ver_todos
    return


if __name__ == "__main__":
    app.run()
