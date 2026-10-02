# /// script
# dependencies = ["marimo"]
# requires-python = ">=3.14"
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path
    from ortools.sat.python import cp_model

    return Path, cp_model, pd


@app.cell
def _(Path, pd):
    def carregar_dados(pasta_dados: str):
        """
        Carrega os ficheiros CSV de uma determinada pasta ('dados/' ou 'dados_v2/')
        e devolve os DataFrames correspondentes.
        """
        caminho = Path(pasta_dados)

        turmas_df = pd.read_csv(caminho / "turmas.csv")
        disciplinas_df = pd.read_csv(caminho / "disciplinas.csv")
        salas_df = pd.read_csv(caminho / "salas.csv")
        excecoes_df = pd.read_csv(caminho / "disponibilidade_excecoes.csv")

        return turmas_df, disciplinas_df, salas_df, excecoes_df

    # Teste de leitura dos dados iniciais
    turmas, disciplinas, salas, excecoes = carregar_dados("dados")

    print("Turmas carregadas:", len(turmas))
    print("Disciplinas carregadas:", len(disciplinas))
    print("Tipos de salas carregados:", len(salas))
    print("Exceções de disponibilidade carregadas:", len(excecoes))
    return disciplinas, excecoes, salas, turmas


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
            s_req = (
                disc["sala_especial"]
                if pd.notna(disc["sala_especial"])
                else "Sala Normal"
            )
            salas_por_disc[disc["disciplina"]] = [
                s_inst
                for s_nome, s_inst in salas_disponiveis
                if s_nome == s_req
            ]

        prof_da_disc = dict(
            zip(disciplinas_df["disciplina"], disciplinas_df["professor"])
        )
        cargas = dict(
            zip(disciplinas_df["disciplina"], disciplinas_df["carga_semanal"])
        )
        duplo = dict(
            zip(disciplinas_df["disciplina"], disciplinas_df["duplo_periodo"])
        )

        x = {}
        for t in lista_turmas:
            for d, salas_comp in salas_por_disc.items():
                for dia in DIAS:
                    for p in PERIODOS:
                        for s_inst in salas_comp:
                            x[t, d, dia, p, s_inst] = model.NewBoolVar(
                                f"x_{t}_{d}_{dia}_{p}_{s_inst}"
                            )

        def X(t, d, dia, p, s_inst):
            return x.get((t, d, dia, p, s_inst), None)

        # R1: No máximo 1 aula por período por turma
        for t in lista_turmas:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_tempo = [
                        X(t, d, dia, p, s)
                        for d in salas_por_disc
                        for s in salas_por_disc[d]
                        if X(t, d, dia, p, s) is not None
                    ]
                    if vars_tempo:
                        model.Add(sum(vars_tempo) <= 1)

        # R2: Carga Horária Semanal exata
        for t in lista_turmas:
            for d, carga in cargas.items():
                vars_disc = [
                    X(t, d, dia, p, s)
                    for dia in DIAS
                    for p in PERIODOS
                    for s in salas_por_disc[d]
                    if X(t, d, dia, p, s) is not None
                ]
                model.Add(sum(vars_disc) == int(carga))

        # R3: Limite diário por disciplina (2 se bloco duplo, senão 1)
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                limite_diario = 2 if is_duplo == "sim" else 1
                for dia in DIAS:
                    vars_dia = [
                        X(t, d, dia, p, s)
                        for p in PERIODOS
                        for s in salas_por_disc[d]
                        if X(t, d, dia, p, s) is not None
                    ]
                    if vars_dia:
                        model.Add(sum(vars_dia) <= limite_diario)

        # R4: Blocos Duplos Contíguos
        for t in lista_turmas:
            for d, is_duplo in duplo.items():
                if is_duplo == "sim":
                    for dia in DIAS:
                        for p in PERIODOS:
                            vars_p = [
                                X(t, d, dia, p, s)
                                for s in salas_por_disc[d]
                                if X(t, d, dia, p, s) is not None
                            ]
                            if not vars_p:
                                continue

                            vars_vizinhos = []
                            if p > 1:
                                vars_vizinhos.extend(
                                    [
                                        X(t, d, dia, p - 1, s)
                                        for s in salas_por_disc[d]
                                        if X(t, d, dia, p - 1, s) is not None
                                    ]
                                )
                            if p < 5:
                                vars_vizinhos.extend(
                                    [
                                        X(t, d, dia, p + 1, s)
                                        for s in salas_por_disc[d]
                                        if X(t, d, dia, p + 1, s) is not None
                                    ]
                                )

                            model.Add(sum(vars_vizinhos) >= sum(vars_p))

        # R5: No máximo 1 aula por período por professor
        professores = disciplinas_df["professor"].unique()
        for prof in professores:
            discs_prof = [d for d, pr in prof_da_disc.items() if pr == prof]
            for dia in DIAS:
                for p in PERIODOS:
                    vars_prof = [
                        X(t, d, dia, p, s)
                        for t in lista_turmas
                        for d in discs_prof
                        for s in salas_por_disc[d]
                        if X(t, d, dia, p, s) is not None
                    ]
                    if vars_prof:
                        model.Add(sum(vars_prof) <= 1)

        # R6: Respeito pelas Exceções de Indisponibilidade
        for _, exc in excecoes_df.iterrows():
            prof = exc["professor"]
            dia = exc["dia"]
            p = int(exc["periodo"])
            discs_prof = [d for d, pr in prof_da_disc.items() if pr == prof]
            for d in discs_prof:
                for t in lista_turmas:
                    for s in salas_por_disc[d]:
                        var = X(t, d, dia, p, s)
                        if var is not None:
                            model.Add(var == 0)

        # R7: No máximo 1 aula por sala física por período
        todas_instancias = [s_inst for _, s_inst in salas_disponiveis]
        for s_inst in todas_instancias:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_sala = [
                        X(t, d, dia, p, s_inst)
                        for t in lista_turmas
                        for d in salas_por_disc
                        if s_inst in salas_por_disc[d]
                        and X(t, d, dia, p, s_inst) is not None
                    ]
                    if vars_sala:
                        model.Add(sum(vars_sala) <= 1)

        return model, x

    

    return (criar_modelo,)


@app.cell
def _(cp_model, criar_modelo, disciplinas, excecoes, salas, turmas):
    model_h0, vars_h0 = criar_modelo(turmas, disciplinas, salas, excecoes)
    print(f"Modelo construído com {len(vars_h0)} variáveis!")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model_h0)

    resultado_str = (
        "Ótimo / Viável"
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else "Inviável"
    )
    print(f"Status da resolução: {resultado_str}")
    return


if __name__ == "__main__":
    app.run()
