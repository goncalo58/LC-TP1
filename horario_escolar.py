# /// script
# dependencies = ["marimo"]
# requires-python = ">=3.14"
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")

@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path
    from ortools.sat.python import cp_model

    return Path, mo, pd, cp_model


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

    return carregar_dados, disciplinas, excecoes, salas, turmas

@app.cell
def _(cp_model, disciplinas, excecoes, pd, salas, turmas):
    def criar_modelo(turmas_df, disciplinas_df, salas_df, excecoes_df):
        model = cp_model.CpModel()

        # 1. Parâmetros de Tempo
        DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex"]
        PERIODOS = list(range(1, 6))  # 1, 2, 3, 4, 5

        # Lista de turmas, professores, salas
        lista_turmas = turmas_df["turma"].tolist()
        
        # Mapeamento de salas por tipo e quantidade
        # Se normal quantidade=6, criamos salas virtuais: Normal_1, Normal_2, ...
        salas_disponiveis = []
        for _, row in salas_df.iterrows():
            nome_sala = row["sala"]
            qtd = row["quantidade"]
            for i in range(1, qtd + 1):
                salas_disponiveis.append((nome_sala, f"{nome_sala}_{i}", row["tipo"]))

        # 2. VARIÁVEIS DE DECISÃO: x[turma, disciplina, dia, periodo, sala_instancia]
        x = {}
        for t in lista_turmas:
            for _, disc in disciplinas_df.iterrows():
                d_nome = disc["disciplina"]
                s_req = disc["sala_especial"] if pd.notna(disc["sala_especial"]) else "Sala Normal"
                
                # Filtrar apenas salas compatíveis (R7)
                salas_comp = [s_inst for s_nome, s_inst, s_tipo in salas_disponiveis if s_nome == s_req]
                
                for dia in DIAS:
                    for p in PERIODOS:
                        for s_inst in salas_comp:
                            x[t, d_nome, dia, p, s_inst] = model.NewBoolVar(
                                f"x_{t}_{d_nome}_{dia}_{p}_{s_inst}"
                            )

        # -------------------------------------------------------------
        # RESTRIÇÕES OBRIGATÓRIAS (R1 - R8)
        # -------------------------------------------------------------

        # R2: Carga Horária Semanal exata por turma e disciplina
        for t in lista_turmas:
            for _, disc in disciplinas_df.iterrows():
                d_nome = disc["disciplina"]
                carga = disc["carga_semanal"]
                vars_disc = [v for k, v in x.items() if k[0] == t and k[1] == d_nome]
                model.Add(sum(vars_disc) == carga)

        # R1: Uma turma só pode ter no máximo 1 aula por período
        for t in lista_turmas:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_tempo = [v for k, v in x.items() if k[0] == t and k[2] == dia and k[3] == p]
                    model.Add(sum(vars_tempo) <= 1)

        # R5: Um professor não pode dar duas aulas no mesmo período
        professores = disciplinas_df["professor"].unique()
        for prof in professores:
            discs_prof = disciplinas_df[disciplinas_df["professor"] == prof]["disciplina"].tolist()
            for dia in DIAS:
                for p in PERIODOS:
                    vars_prof = [
                        v for k, v in x.items() 
                        if k[1] in discs_prof and k[2] == dia and k[3] == p
                    ]
                    model.Add(sum(vars_prof) <= 1)

        # R6: Respeitar Indisponibilidades dos Professores
        for _, exc in excecoes_df.iterrows():
            prof = exc["professor"]
            dia = exc["dia"]
            p = exc["periodo"]
            discs_prof = disciplinas_df[disciplinas_df["professor"] == prof]["disciplina"].tolist()
            for k, v in x.items():
                if k[1] in discs_prof and k[2] == dia and k[3] == p:
                    model.Add(v == 0)

        # R4: Blocos Duplos (disciplinas com duplo_periodo == 'sim')
        for t in lista_turmas:
            for _, disc in disciplinas_df.iterrows():
                if disc["duplo_periodo"] == "sim":
                    d_nome = disc["disciplina"]
                    for dia in DIAS:
                        # Em cada dia, se houver aula no período p, tem de haver no p-1 ou p+1
                        for p in PERIODOS:
                            vars_p = [v for k, v in x.items() if k[0] == t and k[1] == d_nome and k[2] == dia and k[3] == p]
                            vars_p_menos = [v for k, v in x.items() if k[0] == t and k[1] == d_nome and k[2] == dia and k[3] == p - 1]
                            vars_p_mais = [v for k, v in x.items() if k[0] == t and k[1] == d_nome and k[2] == dia and k[3] == p + 1]
                            
                            # Se dá no periodo p, obriga a dar no anterior ou posterior
                            model.Add(sum(vars_p_menos) + sum(vars_p_mais) >= sum(vars_p))

        # R7: Capacidade e Uso de Salas (No máximo 1 aula por instância de sala no mesmo período)
        todas_instancias_salas = [s_inst for _, s_inst, _ in salas_disponiveis]
        for s_inst in todas_instancias_salas:
            for dia in DIAS:
                for p in PERIODOS:
                    vars_sala = [v for k, v in x.items() if k[4] == s_inst and k[2] == dia and k[3] == p]
                    model.Add(sum(vars_sala) <= 1)

        return model, x

    model_h0, vars_h0 = criar_modelo(turmas, disciplinas, salas, excecoes)
    print("Modelo construído com sucesso!")
    return criar_modelo, model_h0, vars_h0


if __name__ == "__main__":
    app.run()
