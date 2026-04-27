import psycopg2
import streamlit as st
import os

CONN_STRING = os.getenv("NEON_DB_URL")

def upsert_lotes(dados: list[dict]):
    if not dados:
        print("⚠️ Nenhum dado recebido para upsert")
        return
    
    try:
        with psycopg2.connect(CONN_STRING) as conn:
            with conn.cursor() as cur:

                for item in dados:
                    sku = str(item.get("sku", "")).strip().upper()

                    if not sku:
                        continue

                    descricao = item.get("descricao", "")
                    lote = item.get("lote", "")
                    validade = item.get("validade","")

                    cur.execute("""
                        INSERT INTO tblotematriz (sku,descricao,lote,validade)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (sku)
                        DO UPDATE SET
                            descricao = EXCLUDED.descricao,
                            lote = EXCLUDED.lote,
                            validade = EXCLUDED.validade""", (sku,descricao,lote,validade))
                    
            conn.commit()

        print(f"✅ Upsert concluído: {len(dados)} registros")

    except Exception as e:
        print(f"❌ Erro no upsert: {e}")