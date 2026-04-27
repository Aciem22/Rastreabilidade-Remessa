import psycopg2
import streamlit as st

CONN_STRING = st.secrets["NEON_DB_URL"]

@st.cache_data
def carregar_mapa_lotes():
    with psycopg2.connect(CONN_STRING) as conn:
        with conn.cursor() as cur:
            cur.execute(""" SELECT sku, lote, validade FROM tblotematriz""")
            dados = cur.fetchall()

    mapa = {}

    for sku, lote, validade in dados:
        if sku:
            sku_norm = str(sku).strip().upper()

            mapa[sku_norm] = {
                "lote": (lote or "").strip(),
                "validade": (validade or "").strip()
            }

    return mapa