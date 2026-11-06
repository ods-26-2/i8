"""Seleciona limiares provisórios somente a partir do split de calibração rastreável."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
from scripts.prepare_dataset import KNOWN_LABELS, file_hash, validate_manifest, validate_predictions


def select_thresholds(rows, *, known_confidence=0.8, uncertain_margin=0.05):
    for value in (known_confidence, uncertain_margin):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("parâmetro fixo deve ser finito e estar entre zero e um")
    if not rows or any(r.get("split") != "calibration" for r in rows):
        raise ValueError("calibração requer exclusivamente split calibration")
    for row in rows:
        value = row.get("similarity")
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("similaridade inválida para calibração")
        if row.get("label") not in {"CONFORMING", "ANOMALY", *KNOWN_LABELS}:
            raise ValueError("rótulo de calibração inválido")
    normal = [r["similarity"] for r in rows if r["label"] == "CONFORMING"]
    defective = [r["similarity"] for r in rows if r["label"] in KNOWN_LABELS]
    anomaly = [r["similarity"] for r in rows if r["label"] == "ANOMALY"]
    if not normal or not defective:
        raise ValueError("calibração requer normais e defeitos conhecidos")
    candidates = sorted(set(normal + defective))
    best = max(candidates, key=lambda t: sum(x >= t for x in normal) / len(normal)
               - sum(x >= t for x in defective) / len(defective))
    anomaly_threshold = min(anomaly if anomaly else defective)
    if anomaly_threshold >= best:
        raise ValueError("dados não permitem fronteiras ordenadas de anomalia e conformidade")
    return {
        "parameters": {"conforming_similarity": best, "known_confidence": known_confidence,
                       "anomaly_similarity": anomaly_threshold, "uncertain_margin": uncertain_margin},
        "status": "PROVISORIA_NAO_HOMOLOGADA",
        "samples": len(rows), "labels": dict(Counter(r["label"] for r in rows)),
        "justificativa": {
            "conforming_similarity": "máximo de TPR(normal)-FPR(defeito conhecido), empate pelo menor limiar",
            "anomaly_similarity": "mínimo das anomalias rotuladas" if anomaly else
                "heurística: mínimo dos defeitos conhecidos; SEM validação de anomalia desconhecida",
            "known_confidence": "fixado pelo operador; não calibrado por este comando",
            "uncertain_margin": "fixada pelo operador; não calibrada por este comando",
        },
        "bloqueios": [] if anomaly else ["Sem ANOMALY rotulada na calibração; detecção desconhecida não homologada."],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    for name in ("product", "normal-version", "classifier-version", "taxonomy-version"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--policy-version", default="policy-repro-001")
    p.add_argument("--known-confidence", type=float, default=0.8)
    p.add_argument("--uncertain-margin", type=float, default=0.05)
    a = p.parse_args()
    rows = [json.loads(line) for line in a.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    inventory = validate_manifest(a.manifest)
    validate_predictions(rows, inventory, "calibration")
    if any(r["product_id"] != a.product for r in rows):
        raise SystemExit("BLOQUEADO: produto das previsões diverge do solicitado")
    expected_versions = {"product_id": a.product, "normal_model_version": a.normal_version,
                         "classifier_version": a.classifier_version, "taxonomy_version": a.taxonomy_version}
    if any(rows[0]["artifact_versions"].get(k) != v for k, v in expected_versions.items()):
        raise SystemExit("BLOQUEADO: versões solicitadas divergem da inferência de calibração")
    report = select_thresholds(rows, known_confidence=a.known_confidence, uncertain_margin=a.uncertain_margin)
    # Importar ML somente depois de verificar os dados; nenhum mock substitui treino.
    from src.inference import DecisionPolicy
    policy = DecisionPolicy(**report["parameters"], version=a.policy_version)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    policy.save(a.output, product_id=a.product, normal_version=a.normal_version,
                classifier_version=a.classifier_version, taxonomy_version=a.taxonomy_version)
    report.update(input_sha256=file_hash(a.input), manifest_sha256=inventory["manifest_sha256"],
                  policy_sha256=file_hash(a.output), policy_version=a.policy_version,
                  artifacts_sha256=rows[0]["artifacts_sha256"], artifact_versions=expected_versions)
    a.output.with_suffix(".calibracao.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
