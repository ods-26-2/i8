"""Inventaria dados locais, inclusive ignorados pelo Git; não certifica realidade dos dados."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from scripts.prepare_dataset import file_hash

IMAGES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".ppm"}


def inventory(root, *, exclude=None):
    root = Path(root).resolve()
    errors, files = [], []
    tracked = set(subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"], text=True).split("\0"))
    for current, directories, names in os.walk(root, onerror=lambda e: errors.append(str(e))):
        directories[:] = [d for d in directories if d != ".git"]
        for name in sorted(names):
            path = Path(current) / name
            if path.resolve() == exclude or path.suffix.lower() not in IMAGES | {".csv", ".json", ".jsonl"}:
                continue
            relative = path.relative_to(root).as_posix()
            try:
                ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative]).returncode == 0
                files.append({"path": relative, "sha256": file_hash(path), "bytes": path.stat().st_size,
                              "git": "versionado" if relative in tracked else "ignorado" if ignored else "local_nao_versionado"})
            except OSError as exc:
                errors.append(str(exc))
    images = [f for f in files if Path(f["path"]).suffix.lower() in IMAGES]
    manifests = [f for f in files if Path(f["path"]).suffix.lower() == ".csv" and ".example." not in f["path"].lower()]
    return {"base_git": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "escopo": "repositório I8 completo, inclusive ignorados; lista imagens, CSV, JSON e JSONL; exclui metadados .git e o arquivo de saída",
            "status": "BLOQUEADO_SEM_DADOS" if not images or not manifests else "REQUER_VALIDACAO_DO_MANIFESTO",
            "imagens_locais": len(images), "csvs_nao_exemplo": len(manifests),
            "natureza": "não inferida pelos nomes; mocks e relatórios não comprovam imagens reais",
            "arquivos": sorted(files, key=lambda f: f["path"]), "erros_acesso": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.root, exclude=args.output.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "imagens_locais", "csvs_nao_exemplo", "erros_acesso")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
