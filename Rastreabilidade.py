import re
import sys
import requests
import streamlit as st
import datetime
from datetime import date, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import tempfile
import pandas as pd
from utils.neon_select import carregar_mapa_lotes

from utils.api_omie import (
    ListarRemessas,
    ConsultarRemessas,
    ListarClientes,
    ConsultarProduto,
    AlterarRemessa,
    limpar_cache
)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Cadastro de Lotes", layout="wide")

st.link_button(
    "📦 Rastreabilidade Pedido Venda",
    "https://rastreabilidadelenvie.streamlit.app/"
)

st.title("🔍 Cadastro de Rastreabilidade - Remessas")

# --------------------------------------------------
# PLANILHA (CACHE)
# --------------------------------------------------

if "mapa_lotes" not in st.session_state:
    st.session_state.mapa_lotes = carregar_mapa_lotes()

mapa_lotes = st.session_state.mapa_lotes

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🔄 Recarregar Base"):
        carregar_mapa_lotes.clear()

        if "mapa_lotes" in st.session_state:
            del st.session_state["mapa_lotes"]

        if "produtos_info_cache" in st.session_state:
            del st.session_state["produtos_info_cache"]

        st.success("Base recarregada com sucesso!")
        st.rerun()

with col_btn2:
    if st.button("🗑️ Limpar Cache API Omie"):
        limpar_cache()
        st.success("Cache da API Omie limpo! (TTL: 60s)")
        st.rerun()

# --------------------------------------------------
# INPUT CLIENTE
# --------------------------------------------------
col1, col_bt, col2 = st.columns([3, 1, 3])

with col1:
    cnpj_input = st.text_input(
        "CNPJ do cliente:",
        max_chars=20,
        key="cnpj_input"
    )

with col_bt:
    st.text("")
    st.text("")
    pesquisar = st.button("🔍 Pesquisar")

if pesquisar:
    # 🔥 limpa qualquer resíduo da pesquisa anterior
    for key in [
        "lista_remessas",
        "codigo_cliente",
        "dados_remessa",
        "remessa_atual",
        "codigo_remessa",
        "produtos_info_cache"
    ]:
        st.session_state.pop(key, None)

    if not cnpj_input:
        st.warning("Informe um CNPJ para pesquisar.")
        st.stop()

    with st.spinner("Consultando cliente..."):
        try:
            lista_clientes = ListarClientes(cnpj_input)
        except Exception:
            st.error("Erro de conexão com a Omie.")
            st.stop()

        if not lista_clientes:
            st.error("Cliente não encontrado para o CNPJ informado.")
            st.stop()

        codigo_cliente = lista_clientes[0]
        st.session_state["codigo_cliente"] = codigo_cliente

        st.session_state["lista_remessas"] = (
            ListarRemessas(codigo_cliente) or {}
        )

with col2:
    if st.session_state.get("lista_remessas"):
        numero_remessa = st.selectbox(
            "Escolha a remessa:",
            options=list(st.session_state["lista_remessas"].keys()),
            index=None,
            placeholder="Selecione uma remessa",
            key="select_remessa"
        )
    else:
        numero_remessa = None

# --------------------------------------------------
# CONSULTA REMESSA
# --------------------------------------------------
if numero_remessa:

    if (
        "remessa_atual" not in st.session_state
        or st.session_state["remessa_atual"] != numero_remessa
    ):
        with st.spinner("Consultando remessa..."):
            codigo_remessa = st.session_state["lista_remessas"][numero_remessa]
            st.session_state["codigo_remessa"] = codigo_remessa
            st.session_state["dados_remessa"] = ConsultarRemessas(codigo_remessa)
            st.session_state["remessa_atual"] = numero_remessa
            # Limpa cache de produtos ao trocar de remessa
            st.session_state.pop("produtos_info_cache", None)

    dados_remessa = st.session_state["dados_remessa"]

    cabecalho = dados_remessa.get("cabec", {})
    nCodCli = cabecalho.get("nCodCli")
    nCodRem = cabecalho.get("nCodRem")

    produtos = dados_remessa.get("produtos", [])

    qtd_skus = len(produtos)
    total_qtde = sum(item.get("nQtde", 0) for item in produtos)

    st.markdown(
        f"### Pedido Nº {numero_remessa} — {qtd_skus} SKU(s) | {total_qtde} item(ns)"
    )

    # --------------------------------------------------
    # CARREGAMENTO DOS DADOS (CACHE NO SESSION STATE)
    # --------------------------------------------------
    
    # 🔥 Carrega produtos apenas uma vez por remessa
    if "produtos_info_cache" not in st.session_state:
        with st.spinner("Carregando produtos..."):
            produtos_info = []
            
            print(f"\n{'='*80}")
            print(f"🚀 INICIANDO CARREGAMENTO DE {len(produtos)} PRODUTOS")
            print(f"{'='*80}")
            
            for idx, item in enumerate(produtos):
                codigo_item = item.get("nCodProd", "")
                quantidade = item.get("nQtde", 0)

                print(f"\n[{idx+1}/{len(produtos)}] Consultando produto {codigo_item}...")
                
                # Consulta produto (com cache interno de 60s da API)
                descricao_item, sku_item = ConsultarProduto(codigo_item)

                # Busca dados na planilha
                sku_norm = str(sku_item).strip().upper()

                info = mapa_lotes.get(sku_norm,{})

                lote_existente = info.get("lote" , "")
                validade_existente = info.get("validade", "")

                # Tratamento quando a API retorna None
                label_expander = (
                    str(descricao_item).strip() 
                    if descricao_item 
                    else f"Produto {sku_item if sku_item else codigo_item}"
                )

                produtos_info.append({
                    "idx": idx,
                    "codigo_item": codigo_item,
                    "quantidade": quantidade,
                    "descricao_item": descricao_item,
                    "sku_item": sku_item if sku_item else str(codigo_item),
                    "lote_existente": lote_existente,
                    "validade_existente": validade_existente,
                    "label_expander": label_expander
                })
            
            print(f"\n{'='*80}")
            print(f"✅ CARREGAMENTO CONCLUÍDO: {len(produtos_info)} produtos")
            print(f"{'='*80}\n")
            
            # Salva no session state para não recarregar
            st.session_state["produtos_info_cache"] = produtos_info
    else:
        produtos_info = st.session_state["produtos_info_cache"]
        print("💾 Usando produtos do cache do session_state")

    # --------------------------------------------------
    # FORM (RENDERIZAÇÃO)
    # --------------------------------------------------
    
    with st.form("form_rastreabilidade"):
        valores_digitados = {}

        for prod in produtos_info:
            with st.expander(prod["label_expander"], expanded=True):
                c1, c2, c3 = st.columns([4, 3, 2])

                with c1:
                    st.text(f"SKU: {prod['sku_item']}")

                with c2:
                    lote = st.text_input(
                        "Lote",
                        value=prod["lote_existente"],
                        key=f"lote_{prod['idx']}_{numero_remessa}"
                    )
                    valores_digitados[f"lote_{prod['idx']}_{numero_remessa}"] = lote

                with c3:
                    validade = st.text_input(
                        "Validade",
                        value=prod["validade_existente"],
                        key=f"validade_{prod['idx']}_{numero_remessa}"
                    )
                    valores_digitados[f"validade_{prod['idx']}_{numero_remessa}"] = validade

                st.markdown(f"**Quantidade:** {prod['quantidade']}")

        st.markdown("---")

        frete = dados_remessa.get("frete", {})
        quantidade_caixas = st.number_input(
            "Quantidade de caixas",
            value=frete.get("nQtdVol", 0),
            step=1
        )

        # --------------------------------------------------
        # SUBMIT
        # --------------------------------------------------
        if st.form_submit_button("💾 Salvar Dados"):
            produtos_finalizados = []

            for idx, item in enumerate(produtos):
                sku = item.get("nCodProd")
                nCodIt = item.get("nCodIt")
                nQtde = item.get("nQtde")
                nValUnit = item.get("nValUnit")

                lote = valores_digitados.get(f"lote_{idx}_{numero_remessa}", "")
                validade = valores_digitados.get(f"validade_{idx}_{numero_remessa}", "")

                if lote in ["S/L", "-"]:
                    lote = ""

                fabricacao_str = ""
                validade_str = ""

                if validade and validade != "S/V":
                    try:
                        if len(validade.split("/")) == 2:
                            mes, ano = validade.split("/")
                            mes = int(mes)
                            ano = int(ano) + 2000 if int(ano) < 100 else int(ano)
                            validade_dt = date(ano, mes, 1)
                        else:
                            validade_dt = datetime.strptime(validade, "%d/%m/%Y").date()

                        fabricacao_dt = date(
                            validade_dt.year - 3,
                            validade_dt.month,
                            validade_dt.day
                        )

                        validade_str = validade_dt.strftime("%d/%m/%Y")
                        fabricacao_str = fabricacao_dt.strftime("%d/%m/%Y")

                    except Exception as e:
                        st.warning(f"Erro na validade do SKU {sku}: {e}")

                produtos_finalizados.append({
                    "nCodProd": sku,
                    "nCodIt": nCodIt,
                    "nQtde": nQtde,
                    "nValUnit": nValUnit,
                    "rastreabilidade": {
                        "numeroLote": lote,
                        "dataFabricacaoLote": fabricacao_str,
                        "dataValidadeLote": validade_str,
                        "qtdeProdutoLote": nQtde
                    }
                })

            resultado = AlterarRemessa(
                nCodRem,
                quantidade_caixas,
                produtos_finalizados,
                nCodCli
            )

            if resultado is not None:
                st.session_state["remessa_salva"] = True
                # Limpa cache ao salvar
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("❌ Erro ao salvar remessa. Verifique os logs no terminal.")

    placeholder_sucesso = st.empty()

    if st.session_state.pop("remessa_salva", False):
        placeholder_sucesso.success("✅ Remessa alterada com sucesso!")