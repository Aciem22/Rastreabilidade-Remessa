from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from utils.neon_upsert import upsert_lotes

app=FastAPI()

# --------------------
# SCHEMA 
# --------------------

class LoteItem(BaseModel):
    sku:str
    descricao: str
    lote:str
    validade: str

# ------------------------
# ENDPOINT
# ------------------------

@app.get("/")
def health():
    return{"status": "ok"}


@app.post("/upsert-lotes")
def upsert_lotes_endpoint(dados:List[LoteItem]):
    try:
        # converte para dict (seu formato atual)
        payload = [item.dict() for item in dados]

        upsert_lotes(payload)

        return {"status":"ok", "registros":len(payload)}
    
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}