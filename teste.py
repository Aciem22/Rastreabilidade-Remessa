import psycopg2
import streamlit as st
from utils.neon_upsert import upsert_lotes


st.title("Teste conexão Neon")

try:
    dados_teste = [
    {
        "sku": "TESTE123",
        "descricao": "Produto Teste",
        "lote": "LOTE100",
        "validade": "12/30"
    }
]

    upsert_lotes(dados_teste)

except Exception as e:
    st.error(f"Erro na conexão: {e}")