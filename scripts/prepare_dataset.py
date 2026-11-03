"""Validate a manifest with piece/session/hash disjoint splits."""
import argparse,csv,hashlib
from pathlib import Path
ALLOWED_SPLITS={"train","calibration","test"}; ALLOWED_LABELS={"CONFORMING","AMASSADO","FURADO","FURADO_AMASSADO"}
def main():
    p=argparse.ArgumentParser(); p.add_argument("manifest",type=Path); a=p.parse_args(); base=a.manifest.parent.resolve()
    with a.manifest.open(encoding="utf-8",newline="") as stream: rows=list(csv.DictReader(stream))
    required={"product_id","image","label","piece_id","session_id","split"}
    if not rows or not required.issubset(rows[0]): raise SystemExit(f"manifesto requer {sorted(required)}")
    piece_splits={}; session_splits={}; hashes={}; source_splits={}
    for row in rows:
        if any(not row.get(k," ").strip() for k in required): raise SystemExit("campos obrigatórios não podem ser vazios")
        if row["split"] not in ALLOWED_SPLITS or row["label"] not in ALLOWED_LABELS: raise SystemExit("split/rótulo inválido")
        path=(base/row["image"]).resolve()
        if not path.is_file(): raise SystemExit(f"imagem ausente: {path}")
        try: digest=hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc: raise SystemExit(f"imagem ilegível: {path}") from exc
        product=row["product_id"]; piece=(product,row["piece_id"]); session=(product,row["session_id"])
        if piece in piece_splits and piece_splits[piece]!=row["split"]: raise SystemExit(f"peça dividida entre splits: {piece}")
        if session in session_splits and session_splits[session]!=row["split"]: raise SystemExit(f"sessão dividida entre splits: {session}")
        if digest in hashes and hashes[digest]!=row["split"]: raise SystemExit("imagem duplicada entre splits")
        if row.get("source_image"):
            source=(base/row["source_image"]).resolve(); source_splits.setdefault(str(source),row["split"])
            if source_splits[str(source)]!=row["split"]: raise SystemExit("aumento e imagem de origem divididos entre splits")
        piece_splits[piece]=row["split"]; session_splits[session]=row["split"]; hashes[digest]=row["split"]
    print(f"manifesto válido: {len(rows)} amostras; splits={sorted({r['split'] for r in rows})}")
if __name__=="__main__": main()
