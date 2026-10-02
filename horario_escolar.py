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

    return Path, mo, pd


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


if __name__ == "__main__":
    app.run(



