import argparse
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import boto3
from huggingface_hub import HfApi, snapshot_download

from package_aws_model import ensure_bucket, object_exists, sha256


MODEL_ID = "dslim/bert-base-NER"
MODEL_FILES = [
    "config.json",
    "model.safetensors",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
]

INFERENCE_HANDLER = r'''import json

from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline


def model_fn(model_dir):
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(model_dir, local_files_only=True)
    recognizer = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")
    return recognizer


def input_fn(request_body, content_type="application/json"):
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    payload = json.loads(request_body)
    text = payload.get("inputs") or payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Request must contain a non-empty 'inputs' or 'text' field")
    return text


def predict_fn(text, recognizer):
    return [
        {
            "text": item["word"],
            "label": item["entity_group"],
            "score": float(item["score"]),
            "start": int(item["start"]),
            "end": int(item["end"]),
        }
        for item in recognizer(text)
    ]


def output_fn(prediction, accept="application/json"):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return prediction
'''


def build_archive(output_path):
    revision = HfApi().model_info(MODEL_ID).sha
    snapshot = Path(snapshot_download(
        repo_id=MODEL_ID, revision=revision, allow_patterns=MODEL_FILES
    ))
    with tempfile.TemporaryDirectory(prefix="ner-model-") as directory:
        staging = Path(directory)
        for source in snapshot.iterdir():
            if source.is_file():
                shutil.copy2(source, staging / source.name)
        (staging / "model-manifest.json").write_text(
            json.dumps({"model_id": MODEL_ID, "revision": revision}, indent=2),
            encoding="utf-8",
        )
        code_directory = staging / "code"
        code_directory.mkdir()
        (code_directory / "inference.py").write_text(INFERENCE_HANDLER, encoding="utf-8")
        with tarfile.open(output_path, "w:gz") as archive:
            for source in sorted(staging.iterdir()):
                archive.add(source, arcname=source.name)
    return revision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    s3 = boto3.client("s3", region_name=args.region)
    ensure_bucket(s3, args.bucket, args.region)
    if object_exists(s3, args.bucket, args.key):
        return
    with tempfile.TemporaryDirectory(prefix="ner-package-") as directory:
        archive_path = Path(directory) / "model.tar.gz"
        revision = build_archive(archive_path)
        checksum = sha256(archive_path)
        s3.upload_file(
            str(archive_path), args.bucket, args.key,
            ExtraArgs={
                "ServerSideEncryption": "AES256",
                "Metadata": {
                    "model-id": "dslim-bert-base-ner",
                    "model-revision": revision,
                    "sha256": checksum,
                },
            },
        )
        print(json.dumps({
            "uri": f"s3://{args.bucket}/{args.key}",
            "model_id": MODEL_ID,
            "revision": revision,
            "sha256": checksum,
            "size_bytes": archive_path.stat().st_size,
        }, indent=2))


if __name__ == "__main__":
    main()
