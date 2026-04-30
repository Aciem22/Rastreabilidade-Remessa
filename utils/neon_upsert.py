import psycopg2
from psycopg2.extras import execute_values
import os

CONN_STRING = os.getenv("NEON_DB_URL")

if not CONN_STRING:
    raise ValueError("❌ NEON_DB_URL não definida nas variáveis de ambiente")

def upsert_lotes(dados: list[dict]):
    if not dados:
        print("⚠️ Nenhum dado recebido para upsert")
        return

    try:
        valores = []

        for item in dados:
            sku = str(item.get("sku", "")).strip().upper()

            if not sku:
                continue

            valores.append((
                sku,
                item.get("descricao", ""),
                item.get("lote", ""),
                item.get("validade", "")
            ))

        if not valores:
            print("⚠️ Nenhum registro válido")
            return

        with psycopg2.connect(CONN_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    INSERT INTO tblotematriz (sku, descricao, lote, validade)
                    VALUES %s
                    ON CONFLICT (sku)
                    DO UPDATE SET
                        descricao = EXCLUDED.descricao,
                        lote = EXCLUDED.lote,
                        validade = EXCLUDED.validade
                """

                execute_values(cur, query, valores)

            conn.commit()

        print(f"✅ Upsert em lote concluído: {len(valores)} registros")

    except Exception as e:
        print(f"❌ Erro no upsert: {e}")