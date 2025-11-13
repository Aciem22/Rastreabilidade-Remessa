import re
import sys
import requests
import streamlit as st
import datetime
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import tempfile
import pandas as pd
from utils.api_omie import ListarRemessas, ConsultarRemessas,ListarClientes,ConsultarProduto,AlterarRemessa
from utils.sheets import carregar_lotes_validade

st.set_page_config(page_title="Cadastro de Lotes", layout="wide")

# --- Carrega planilha apenas uma vez ---
if "df_lotes" not in st.session_state:
    st.session_state.df_lotes = carregar_lotes_validade()

# --- Botão manual pra recarregar ---
if st.button("🔄 Recarregar Planilha"):
    st.cache_data.clear()
    st.session_state.df_lotes = carregar_lotes_validade()
    st.success("Planilha recarregada com sucesso!")

st.link_button("📦 Rastreabilidade Pedido Venda","https://rastreabilidadelenvie.streamlit.app/")

# --- Usa os dados do session_state ---
df_lotes = st.session_state.df_lotes
# Usa os dados sempre do session_state
df_lotes = st.session_state.df_lotes

# Carrega os dados da planilha uma vez só
df_lotes = carregar_lotes_validade()

st.title("🔍 Cadastro de Rastreabilidade - Remessas")

# antes das colunas, inicializa pra garantir que existe
lista_remessas = {}
lista_clientes = None
numero_remessa= None

# --- Cria duas colunas: número da remessa e data ---
col1, col2 = st.columns([2, 1])

with col1:
    cnpj_input = st.text_input("CNPJ do cliente:", max_chars=20)

    if cnpj_input:
        lista_clientes = ListarClientes(cnpj_input) or []

        #print(lista_clientes)
        if lista_clientes:

            codigo_cliente=lista_clientes[0]
            st.session_state["codigo_cliente"] = codigo_cliente

            lista_remessas = ListarRemessas(codigo_cliente) or {}
            st.session_state["lista_remessas"] = lista_remessas
        
        else:
            st.error("Cliente não encontrado para o CNPJ informado!")

with col2:
    if "lista_remessas" in st.session_state and st.session_state["lista_remessas"]:
         numero_remessa = st.selectbox(
            "Escolha a remessa:",
            options=list(st.session_state["lista_remessas"].keys()),
            index=None,  # <- deixa vazio até o usuário escolher
            placeholder="Selecione uma remessa",
        )
    else:
        numero_remessa = st.selectbox("Digite o CNPJ do cliente para listar as remessas",options=None)

if numero_remessa:
    # Evita duplicação e salva session_state
    if (
        "dados_remessa" not in st.session_state
        or st.session_state.get("remessa_atual") != numero_remessa
    ):
        with st.spinner("Consultando remessa..."):
            # retorna apenas o código da remessa
            codigo_remessa = lista_remessas.get(numero_remessa)
            st.session_state["codigo_remessa"] = codigo_remessa

            # agora busca os detalhes completos da remessa
            dados_remessa = ConsultarRemessas(codigo_remessa)
            st.session_state["dados_remessa"] = dados_remessa  # salva os dados completos

    cabecalho = st.session_state["dados_remessa"].get("cabec", {})
    nCodCli = cabecalho.get("nCodCli")
    nCodRem = cabecalho.get("nCodRem")
            
    produtos = dados_remessa.get("produtos", [])

    for item in produtos:
        codigo_item = item.get("nCodProd")
        quantidade = item.get("nQtde")

    qtd_skus = len(produtos)
    total_qtde = sum(item.get("nQtde",0) for item in produtos)

    st.markdown(f"### Pedido Nº {numero_remessa} — {qtd_skus} SKU(s) | {total_qtde} item(ns)")

    with st.form("form_rastreabilidade"):
        valores_digitados = {}

        for idx, item in enumerate(produtos):
            codigo_item = item.get("nCodProd", "")

            dados_item = ConsultarProduto(codigo_item)

            descricao_item=dados_item[0]
            sku_item=dados_item[1]

            quantidade = item.get("nQtde", 0)

            with st.expander(f"{descricao_item}", expanded=True):
                col1, col2, col3 = st.columns([4, 3, 2])

                linha_lote = df_lotes[df_lotes["Código do Produto"] == sku_item]

                lote_existente = linha_lote["LOTE"].iloc[0] if not linha_lote.empty else ""
                if isinstance(lote_existente,str):
                    lote_existente = lote_existente.strip().lstrip("'")
                validade_existente = linha_lote["VALIDADE"].iloc[0] if not linha_lote.empty else None

                with col1:
                    st.text(f"SKU: {sku_item}")
                with col2:
                    lote = st.text_input("Lote",value=lote_existente, key=f"lote_{idx}_{numero_remessa}")
                    valores_digitados[f"lote_{idx}_{numero_remessa}"] = lote
                with col3:
                    validade = st.text_input("Validade",value=validade_existente, key=f"validade_{idx}_{numero_remessa}")
                    valores_digitados[f"validade_{idx}_{numero_remessa}"] = validade

                st.markdown(f"**Quantidade:** {quantidade}")

        st.markdown("<hr style='border: none; height: 1px; background-color: #5e5e5e;'>", unsafe_allow_html=True)

        frete = st.session_state["dados_remessa"].get("frete", {})
        quantidade_caixas = st.number_input("Quantidade de caixas", value=frete.get("nQtdVol", 0), step=1)

        if st.form_submit_button("💾 Salvar Dados"):
            produtos_finalizados = []

            for idx, item in enumerate(produtos):
                sku = item.get("nCodProd", "")
                descricao = item.get("cDescricao", "")
                nCodIt = item.get("nCodIt", 0)
                nQtde = item.get("nQtde",0)
                nValUnit = item.get("nValUnit",0)

                # pega os dados digitados no form
                lote = valores_digitados.get(f"lote_{idx}_{numero_remessa}", "")
                validade = valores_digitados.get(f"validade_{idx}_{numero_remessa}", "")

                if(lote == "S/L" or lote=="-"):
                    lote=""

                if validade and validade != "S/V":
                    try:
                        # validade vem como string 'MM/YY' ou 'DD/MM/YYYY'
                        if len(validade.split("/")) == 2:  # formato MM/YY
                            mes, ano = validade.split("/")
                            mes = int(mes)
                            ano = int(ano)
                            if ano < 100:
                                ano += 2000
                            validade_dt = date(ano, mes, 1)
                        else:
                            validade_dt = datetime.strptime(validade, "%d/%m/%Y").date()

                        fabricacao_dt = date(validade_dt.year - 3, validade_dt.month, validade_dt.day)
                        validade_str = validade_dt.strftime("%d/%m/%Y")
                        fabricacao_str = fabricacao_dt.strftime("%d/%m/%Y")
                    except Exception as e:
                        st.warning(f"Erro ao converter validade do produto {sku}: {e}")
                        validade_str = ""
                        fabricacao_str = ""
                else:
                    validade_str = ""
                    fabricacao_str = ""


                rastreabilidade = {
                    "numeroLote": lote,
                    "dataFabricacaoLote": fabricacao_str,
                    "dataValidadeLote": validade_str,
                    "qtdeProdutoLote": nQtde
                }

                produtos_finalizados.append({
                    "nCodProd": sku,
                    "rastreabilidade": rastreabilidade,
                    "nCodIt":nCodIt,
                    "nQtde":nQtde,
                    "nValUnit":nValUnit
                })

            # mostra o JSON montado pra debug
            #st.json(produtos_finalizados)

            # chama a função de envio
            resultado = AlterarRemessa(nCodRem, quantidade_caixas, produtos_finalizados,nCodCli)
            st.success("✅ Remessa enviada com sucesso!")

                    