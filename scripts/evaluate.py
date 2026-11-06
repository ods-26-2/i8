"""Evaluate complete result/class predictions with explicit denominators."""
import argparse,json
from collections import Counter
from pathlib import Path
from scripts.prepare_dataset import KNOWN_LABELS, file_hash, validate_manifest, validate_predictions
RESULTS=("CONFORMING","NON_CONFORMING","ANOMALY","UNCERTAIN")
KNOWN=("AMASSADO","FURADO","FURADO_AMASSADO")
def main():
    p=argparse.ArgumentParser(); p.add_argument("input",type=Path); p.add_argument("--output",type=Path); p.add_argument("--manifest",type=Path); a=p.parse_args(); rows=[json.loads(x) for x in a.input.open(encoding="utf-8") if x.strip()]
    if not rows:
        raise SystemExit("BLOQUEADO: avaliação sem amostras")
    if any(r.get("split", "test") != "test" for r in rows):
        raise SystemExit("BLOQUEADO: avaliação requer split test separado")
    inventory = validate_manifest(a.manifest) if a.manifest else None
    if inventory:
        validate_predictions(rows, inventory, "test")
        for row in rows:
            expected = row["label"] if row["label"] in {"CONFORMING", "ANOMALY"} else "NON_CONFORMING"
            defect = row["label"] if row["label"] in KNOWN_LABELS else None
            if row.get("expected_result") != expected or row.get("expected_defect_class") != defect:
                raise SystemExit("BLOQUEADO: verdade de referência diverge do manifesto")
        if "policy" not in rows[0]["artifacts_sha256"]:
            raise SystemExit("BLOQUEADO: avaliação sem hash da política aplicada")
    for row in rows:
        expected = row.get("expected_result", row.get("label"))
        predicted = row.get("predicted_result", row.get("result"))
        for result, defect in ((expected, row.get("expected_defect_class")),
                               (predicted, row.get("predicted_defect_class"))):
            if result == "NON_CONFORMING" and defect not in KNOWN_LABELS:
                raise SystemExit("BLOQUEADO: defeito conhecido deve indicar classe válida")
            if result != "NON_CONFORMING" and defect is not None:
                raise SystemExit("BLOQUEADO: classe só é permitida em NON_CONFORMING")
    actual=[r.get("expected_result",r.get("label")) for r in rows]; predicted=[r["predicted_result"] if "predicted_result" in r else r["result"] for r in rows]; matrix={x:{y:0 for y in RESULTS} for x in RESULTS}
    for x,y in zip(actual,predicted):
        if x not in matrix or y not in RESULTS: raise SystemExit("resultado inválido")
        matrix[x][y]+=1
    support=dict(Counter(actual)); metrics={}
    for label in RESULTS:
        tp=matrix[label][label]; fp=sum(matrix[other][label] for other in RESULTS if other!=label); fn=sum(matrix[label][other] for other in RESULTS if other!=label); precision=tp/(tp+fp) if tp+fp else 0; recall=tp/(tp+fn) if tp+fn else 0; metrics[label]={"support":support.get(label,0),"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0}
    expected_classes=[r.get("expected_defect_class") for r in rows]; predicted_classes=[r.get("predicted_defect_class") for r in rows]; class_support={label:sum(x==label for x in expected_classes) for label in KNOWN}; class_metrics={}
    for label in KNOWN:
        tp=sum(x==label and y==label for x,y in zip(expected_classes,predicted_classes)); fp=sum(x!=label and y==label for x,y in zip(expected_classes,predicted_classes)); fn=sum(x==label and y!=label for x,y in zip(expected_classes,predicted_classes)); precision=tp/(tp+fp) if tp+fp else 0; recall=tp/(tp+fn) if tp+fn else 0; class_metrics[label]={"support":class_support[label],"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0}
    anomaly_actual=sum(x=="ANOMALY" for x in actual); anomaly_tp=sum(x==y=="ANOMALY" for x,y in zip(actual,predicted)); uncertain=sum(y=="UNCERTAIN" for y in predicted); known_actual=sum(x in ("NON_CONFORMING","ANOMALY") for x in actual)
    report={"samples":len(rows),"confusion_matrix":matrix,"result_metrics":metrics,"defect_class_metrics":class_metrics,"false_positive_known_defect":sum(x=="CONFORMING" and y=="NON_CONFORMING" for x,y in zip(actual,predicted)),"false_negative_known_defect":sum(x=="NON_CONFORMING" and y=="CONFORMING" for x,y in zip(actual,predicted)),"anomaly":{"support":anomaly_actual,"detected":anomaly_tp,"recall":anomaly_tp/anomaly_actual if anomaly_actual else 0},"uncertain":{"count":uncertain,"rate":uncertain/len(rows) if rows else 0},"coverage":sum(y!="UNCERTAIN" for y in predicted)/len(rows) if rows else 0,"denominators":{"result_metrics":"one-vs-rest per result; support is expected count","known_defect_fp_fn":"positive means expected/predicted NON_CONFORMING","anomaly":"expected ANOMALY only; not counted as UNCERTAIN"}}
    report["proveniencia"] = {"predictions_sha256": file_hash(a.input),
        "manifest_sha256": inventory["manifest_sha256"] if inventory else None,
        "artifacts_sha256": rows[0].get("artifacts_sha256"),
        "estado": "RASTREAVEL_AO_MANIFESTO" if inventory else "SEM_MANIFESTO_NAO_REPRODUZIVEL"}
    report["bloqueios"] = [] if anomaly_actual else ["ANOMALY sem suporte; quatro resultados reais não demonstrados."]
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False); print(text)
    if a.output: a.output.write_text(text+"\n",encoding="utf-8")
if __name__=="__main__": main()
