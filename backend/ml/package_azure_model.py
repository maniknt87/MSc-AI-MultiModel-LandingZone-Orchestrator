import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


MODELS = {
    "sentiment": {
        "model_id": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        "files": [
            "config.json",
            "model.safetensors",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.txt",
        ],
    },
    "ner": {
        "model_id": "dslim/bert-base-NER",
        "files": [
            "config.json",
            "model.safetensors",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.txt",
        ],
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_archive(model_name, output_path):
    definition = MODELS[model_name]
    model_id = definition["model_id"]
    revision = HfApi().model_info(model_id).sha
    snapshot = Path(snapshot_download(
        repo_id=model_id,
        revision=revision,
        allow_patterns=definition["files"],
    ))
    with tempfile.TemporaryDirectory(prefix=f"azure-{model_name}-") as directory:
        staging = Path(directory)
        for source in snapshot.iterdir():
            if source.is_file():
                shutil.copy2(source, staging / source.name)
        (staging / "model-manifest.json").write_text(
            json.dumps({"model_id": model_id, "revision": revision}, indent=2),
            encoding="utf-8",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as archive:
            for source in sorted(staging.iterdir()):
                archive.add(source, arcname=source.name)
    return model_id, revision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model_id, revision = build_archive(args.model, args.output)
    print(json.dumps({
        "model": args.model,
        "model_id": model_id,
        "revision": revision,
        "sha256": sha256(args.output),
        "size_bytes": args.output.stat().st_size,
        "path": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
