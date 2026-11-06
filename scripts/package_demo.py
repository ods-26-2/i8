"""Empacota exemplos rastreáveis; ausência de um resultado bloqueia a etapa 15."""
import argparse
import json
from pathlib import Path
from scripts.prepare_dataset import KNOWN_LABELS, file_hash, validate_manifest, validate_predictions

RESULTS = ("CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN")


def build_demo(rows, inventory, provenance):
    validate_predictions(rows, inventory, "test")
    if "policy" not in rows[0]["artifacts_sha256"]:
        raise ValueError("demonstração requer hash da política aplicada")
    for row in rows:
        expected = row["label"] if row["label"] in {"CONFORMING", "ANOMALY"} else "NON_CONFORMING"
        defect = row["label"] if row["label"] in KNOWN_LABELS else None
        if row.get("expected_result") != expected or row.get("expected_defect_class") != defect:
            raise ValueError("verdade de referência diverge do manifesto")
    if provenance.get("natureza") not in {"real_declarada", "sintetica_teste"}:
        raise ValueError("origem deve declarar natureza real_declarada ou sintetica_teste")
    if any(not str(provenance.get(k, "")).strip() for k in ("origem", "responsavel_rotulos", "licenca")):
        raise ValueError("origem, responsável pelos rótulos e licença são obrigatórios")
    if provenance.get("manifest_sha256") != inventory["manifest_sha256"]:
        raise ValueError("declaração de origem não corresponde ao manifesto")
    examples = {}
    for result in RESULTS:
        candidates = [r for r in rows if r.get("predicted_result") == result]
        if result == "ANOMALY":
            candidates = [r for r in candidates if r["label"] == "ANOMALY"]
        elif result == "CONFORMING":
            candidates = [r for r in candidates if r["label"] == "CONFORMING"]
        elif result == "NON_CONFORMING":
            candidates = [r for r in candidates if r["label"] in {"AMASSADO", "FURADO", "FURADO_AMASSADO"}
                          and r.get("predicted_defect_class") == r["label"]]
        if candidates:
            examples[result] = candidates[0]
    missing = [r for r in RESULTS if r not in examples]
    return {
        "status": "BLOQUEADA" if missing else
            ("QUATRO_RESULTADOS_ORIGEM_DECLARADA" if provenance["natureza"] == "real_declarada"
             else "SOMENTE_TESTE_SINTETICO"),
        "natureza": provenance["natureza"], "origem": provenance,
        "manifest_sha256": inventory["manifest_sha256"],
        "exemplos": examples, "resultados_ausentes": missing,
        "limite": "Hashes vinculam arquivos; origem/rótulos são declarações humanas, não prova automática de realidade.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--predictions", type=Path, required=True)
    p.add_argument("--provenance", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        inventory = validate_manifest(a.manifest)
        rows = [json.loads(x) for x in a.predictions.read_text(encoding="utf-8").splitlines() if x.strip()]
        report = build_demo(rows, inventory, json.loads(a.provenance.read_text(encoding="utf-8")))
        report["predictions_sha256"] = file_hash(a.predictions)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"BLOQUEADO: {exc}") from exc
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "resultados_ausentes": report["resultados_ausentes"]}, ensure_ascii=False))
    if report["status"] != "QUATRO_RESULTADOS_ORIGEM_DECLARADA":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
